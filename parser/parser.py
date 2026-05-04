from lxml import etree
from typing import Literal, Optional, cast
import re
import json
from parser.schemas import (
    ChartRepresentation,
    ChartMetadata,
    AxisInfo,
    DataSeries,
    DataPoint,
    SeriesStyle,
    ChartData,
    ChartContext,
)
import re
from bs4 import Tag

VIZ_KEYWORDS = ['linechart','chart', 'graph', 'plot', 'visualization', 'viz']

class SvgContainer:
    def __init__(self, svg_tag):
        self.svg = svg_tag
        self.ancestors = self._walk_up()
    
    def _walk_up(self):
        result = []
        for parent in self.svg.parents:
            if parent.name in ('body', 'html', '[document]', None):
                break
            result.append({
                'tag': parent.name,
                'class': ' '.join(parent.get('class', [])),
                'id': parent.get('id', ''),
                'aria-label': parent.get('aria-label', ''),
                'attrs': dict(parent.attrs),
                'title': parent.get('title', ''),
                'alt-text': parent.get('alt-text', ''),
            })
        return result
    
    def _get_tag_context(self) -> dict:

        aria = self.svg.get('aria-label') or ''
        alt= self.svg.get('alt-text') or ''
        out = {}

        out['aria-label'] = aria
        out['described-by'] = alt

        return out
    

    def _get_parent_context(self) -> str:
        parts = []

        fig = self.svg.find_parent('figure')
        if fig:
            cap = fig.find('figcaption')
            if cap: parts.append(cap.get_text(strip=True))

        for ancestor in self.svg.parents:
            label = ancestor.get('aria-label') or ancestor.get('title')
            if label:
                parts.append(label)
                break

        # first heading + first paragraph in the nearest section-like ancestor
        for ancestor in self.svg.find_parents(['section', 'article', 'div']):
            headings = ancestor.find_all(['h1', 'h2', 'h3'])
            paras = ancestor.find_all('p')
            if headings or paras:
                parts += [h.get_text(strip=True) for h in headings]
                parts += [p.get_text(strip=True) for p in paras]
                break

        return ' | '.join(p for p in parts if p)

    def _get_page_context(self) -> str:
        """Page-level context: <title> tag + headings from article/main ancestors only (no siblings)."""
        parts = []

        html_root = self.svg.find_parent('html')
        if html_root:
            title_tag = html_root.find('title')
            if title_tag:
                parts.append(title_tag.get_text(strip=True))

        seen = set()
        for ancestor in self.svg.find_parents(['article', 'main']):
            for h in ancestor.find_all(['h1', 'h2', 'h3']):
                text = h.get_text(strip=True)
                if text and text not in seen:
                    parts.append(text)
                    seen.add(text)
            break  

        return ' | '.join(p for p in parts if p)

    def _check_svg_tag(self) -> bool:
        """Check the <svg> element's own attributes."""
        attrs = (self.svg.get('aria-label') or '').lower() + ''.join((self.svg.get('class') or '')).lower() 
        if any(k in attrs for k in VIZ_KEYWORDS):
            return True
        data_comp = (self.svg.get('data-component') or '').lower()
        if any(k in data_comp for k in VIZ_KEYWORDS):
            return True
        return False

    def _check_svg_internals(self) -> bool:
        """Check elements inside the SVG for chart signals."""
        for tag in ('title', 'desc'):
            el = self.svg.find(tag)
            if el and any(k in el.get_text().lower() for k in VIZ_KEYWORDS):
                return True
            
        
        for g in self.svg.find_all('g'):
            clas = ' '.join(g.get('class', [])).lower()
            if any(k in clas for k in ['tick', 'axis', 'legend', 'marks']):
                return True
            data_comp = (g.get('data-component') or '').lower()
            if any(k in data_comp for k in ['axis', 'tick', 'legend', 'chart', 'grid', 'mark']):
                return True
            
        # numeric text elements (tick labels like "100", "$1.2M", "+18%")
        texts = [t.get_text().strip() for t in self.svg.find_all('text')]
        # just match a bunch of different patterns and pray
        numeric_texts = sum(1 for t in texts if re.match(r'^-?[\d,.$%+KMB]+$', t))
        if self.svg.find('path') and numeric_texts >= 2:
            return True
        return False

    def _check_structure(self) -> bool:
        """Heuristic: charts always have tick labels as <text> + data marks.
        """
        text_count = len(self.svg.find_all('text'))
        if text_count < 3:
            return False

        has_marks = bool(self.svg.find(['path', 'rect', 'line', 'circle', 'polyline']))
        transformed_groups = sum(1 for g in self.svg.find_all('g') if g.get('transform'))
        has_viewbox = bool(self.svg.get('viewBox'))

        # D3 axis pattern: multiple translated groups + marks + text labels
        if transformed_groups >= 2 and has_marks:
            return True

        g_count = len(self.svg.find_all('g', recursive=False))
        if has_viewbox and g_count >= 2 and has_marks:
            return True

    

        return False

    def _check_ancestors(self) -> bool:
        """Walk up the DOM checking ancestor class/id/attrs for viz keywords."""
        for a in self.ancestors:
            if any(kw in a['class'] for kw in VIZ_KEYWORDS):
                return True
            if any(kw in a['id'] for kw in VIZ_KEYWORDS):
                return True
            for k, v in a['attrs'].items():
                haystack = (k + ' ' + str(v)).lower()
                if any(kw in haystack for kw in VIZ_KEYWORDS):
                    return True
        return False
    
    def is_icon(self):

        if "icon" in self.svg.get('role',"") or "icon" in " ".join(self.svg.get("class",[])):
            return True
        return False

    def is_data_viz(self) -> bool:

        if self.is_icon():
            return False
        
        return (
            self._check_svg_tag()
            or self._check_svg_internals()
            or self._check_structure()
        )

    def parse_attrs(self):
        result = {}
        for a in self.ancestors:
            for k, v in a['attrs'].items():
                if not k.startswith('data-'):
                    continue
                try:
                    parsed = json.loads(v)
                    result[k] = parsed
                except (json.JSONDecodeError, TypeError):
                    if v:
                        result[k] = v
        return result

    def _get_attr(self, tag, attr):
        if attr == 'class':
            values = tag.get(attr, [])
            return ', '.join(values)
        return tag.get(attr, '')

    def external_data(self):
        for a in self.ancestors:
            state = a['attrs'].get('data-state')
            if state:
                try:
                    return json.loads(state)
                except (json.JSONDecodeError, TypeError):
                    pass
        return None

    def chart_type_from_context(self):
        state = self.external_data()
        if state:
            variation = state.get('componentVariation', '').lower()
            for t in ('bar', 'line', 'scatter', 'area', 'pie'):
                if t in variation:
                    return t
        for a in self.ancestors:
            haystack = (a['class'] + ' ' + a['id']).lower()
            for t in ('bar', 'line', 'scatter', 'area', 'pie'):
                if t in haystack:
                    return t
        return None

    def show_container(self, height=3):
        height = min(len(self.ancestors) - 1, height)
        print(f"<svg> class='{self._get_attr(self.svg, 'class')}' id='{self._get_attr(self.svg, 'id')}' </svg>")
        for i, a in enumerate(self.ancestors[:height]):
            indent = '  ' * (i + 1)
            print(f"{indent}↑ <{a['tag']}> class='{a['class']}' id='{a['id']}' title='{a['title']}'")
            for k, v in a['attrs'].items():
                if k not in ('class', 'id'):
                    print(f"{indent}    {k}: {v}")

    def show_hierarchy(self):
        print("SVG")
        for i, a in enumerate(self.ancestors):
            indent = '  ' * (i + 1)
            print(f"{indent}↑ <{a['tag']}>")
            for k, v in a['attrs'].items():
                print(f"{indent}    {k}: {v}")

    def debug_is_data_viz(self):
        """Print which checks pass/fail — call this on any SVG you suspect is a miss."""
        results = {
            'svg_tag':   self._check_svg_tag(),
            'internals': self._check_svg_internals(),
            'structure': self._check_structure(),
            'ancestors': self._check_ancestors(),
        }
        print(f"is_data_viz → {any(results.values())}")
        for name, val in results.items():
            print(f"  {name:12s}: {'✓' if val else '✗'}")


import re

class SVGParser:
    def __init__(self, container: SvgContainer):
        self.container = container
        self.svg = container.svg
        self.axes = self._extract_axes()
        self.chart_type = self._chart_type()
        self.data = self._extract_data()
        self.parent_context = container._get_parent_context()
        self.page_context = container._get_page_context()

    def parse(self):
        title = self.svg.get('aria-label') or ''
        context = ChartContext(ariaLabel=title, pageContext=self.page_context, parentContext=self.parent_context)
        return ChartRepresentation(
            context=context,
            metadata=ChartMetadata(title=title, chartType=self.chart_type or 'unknown'),
            axes=self.axes,
            data=self.data,
        )

    def _chart_type(self):
        rects = self._extract_rects()
        if len(rects) > 2:
            return 'bar'
        path = self.svg.find('path')
        if path:
            if path.get('fill', '').lower() == 'none' and path.get('stroke'):
                return 'line'
            return 'line'
        if self.svg.find('circle'):
            return 'scatter'
        return self.container.chart_type_from_context() or 'unknown'

    def _classify_by_ticks(self, g):
        children = g.find_all('g', recursive=False)
        xs, ys = [], []
        for cg in children:
            m = re.match(r'translate\(([^,]+),\s*([^)]+)\)', cg.get('transform', ''))
            if m:
                xs.append(float(m.group(1)))
                ys.append(float(m.group(2)))
        if len(xs) < 2:
            return None
        if all(abs(y) < 1 for y in ys):
            return 'x'
        if all(abs(x) < 1 for x in xs):
            return 'y'
        return None

    def _axis_by_label(self):
        groups = {'x': None, 'y': None}
        for g in self.svg.find_all('g'):
            label = ((g.get('data-component') or '') + ' ' + ' '.join(g.get('class', []))).lower()
            if ('x-axis' in label or 'xaxis' in label) and not groups['x']:
                groups['x'] = g
            elif ('y-axis' in label or 'yaxis' in label) and not groups['y']:
                groups['y'] = g
        return groups

    def _axis_by_class_and_direction(self):
        groups = {'x': None, 'y': None}
        for g in self.svg.find_all('g'):
            if 'axis' not in ' '.join(g.get('class', [])).lower():
                continue
            d = self._classify_by_ticks(g)
            if d and not groups[d]:
                groups[d] = g
        return groups

    def _axis_by_d3_translate(self):
        groups = {'x': None, 'y': None}
        for g in self.svg.find_all('g'):
            d = self._classify_by_ticks(g)
            if d and not groups[d]:
                groups[d] = g
        return groups

    def _find_axis_groups(self):
        for strategy in (self._axis_by_label, self._axis_by_class_and_direction, self._axis_by_d3_translate):
            groups = strategy()
            if groups['x'] or groups['y']:
                return groups
        return {'x': None, 'y': None}

    def _extract_ticks(self, axis_g):
        ticks = []
        for child in axis_g.find_all('g'):
            text_el = child.find('text')
            if text_el:
                t = text_el.get_text().strip()
                if t:
                    ticks.append(t)
        if not ticks:
            for text_el in axis_g.find_all('text'):
                t = text_el.get_text().strip()
                if t:
                    ticks.append(t)
        return ticks

    def _infer_axis_type(self, ticks):
        if not ticks:
            return 'unknown'
        numeric = sum(1 for t in ticks if re.match(r'^-?[\d,.$%+KMBk]+$', t))
        return 'quantitative' if numeric > len(ticks) / 2 else 'nominal'

    def _extract_axes(self):
        axes = {}
        for key, g in self._find_axis_groups().items():
            if g is None:
                continue
            ticks = self._extract_ticks(g)
            axes[key] = AxisInfo(
                label=g.get('aria-label') or ' '.join(g.get('class',[])),
                type=self._infer_axis_type(ticks),
                ticks=ticks or None,
            )
        if not axes:
            axes = self._extract_axes_flat()
        return axes

    def _extract_axes_flat(self):
        axes = {}
        best_g = max(
            self.svg.find_all('g'),
            key=lambda g: len(g.find_all('text', recursive=False)),
            default=None,
        )
        if best_g is None:
            return axes
        texts = best_g.find_all('text', recursive=False)
        if len(texts) < 2:
            return axes
        by_y, by_x = {}, {}
        for t in texts:
            try:
                if t.get('y'):
                    by_y.setdefault(round(float(t['y'])), []).append(t)
                if t.get('x'):
                    by_x.setdefault(round(float(t['x'])), []).append(t)
            except ValueError:
                continue
        if by_y:
            x_group = max(by_y.values(), key=len)
            if len(x_group) >= 2:
                ticks = [t.get_text().strip() for t in x_group if t.get_text().strip()]
                axes['x'] = AxisInfo(label=None, type=self._infer_axis_type(ticks), ticks=ticks or None)
        if by_x:
            y_group = max(by_x.values(), key=len)
            if len(y_group) >= 2:
                ticks = [t.get_text().strip() for t in y_group if t.get_text().strip()]
                axes['y'] = AxisInfo(label=None, type=self._infer_axis_type(ticks), ticks=ticks or None)
        return axes

    def _extract_rects(self):
        """Bar chart: <rect> elements. Populates value_x/value_y from data-bar-values when present."""
        points = []
        for rect in self.svg.find_all('rect'):
            cls = ' '.join(rect.get('class', [])).lower()
            if any(k in cls for k in ['overlay', 'background', 'bg', 'clip', 'hover', 'mouseover']):
                continue
            try:
                w, h = float(rect.get('width', 0)), float(rect.get('height', 0))
                if w < 1 or h < 1:
                    continue

                value_x, value_y = None, None
                parent_g = rect.find_parent('g')
                if parent_g and parent_g.get('data-bar-values'):
                    try:
                        bar_vals = json.loads(parent_g['data-bar-values'])
                        bar_rects = [r for r in parent_g.find_all('rect')
                                     if 'bar' in ' '.join(r.get('class', [])).lower()
                                     and 'mouseover' not in ' '.join(r.get('class', [])).lower()]
                        idx = bar_rects.index(rect) if rect in bar_rects else -1
                        if 0 <= idx < len(bar_vals):
                            value_x = bar_vals[idx].get('type')
                            value_y = bar_vals[idx].get('value')
                    except (json.JSONDecodeError, ValueError):
                        pass

                points.append(DataPoint(x=float(rect.get('x', 0)), y=h,
                                        value_x=value_x, value_y=value_y))
            except (ValueError, TypeError):
                continue
        return points

    def _extract_paths(self):
        """Line chart: parse data points from the longest <path> (M/L or cubic bezier)."""
        candidates = [p for p in self.svg.find_all('path') if len(p.get('d', '')) > 20]
        if not candidates:
            return []
        main = max(candidates, key=lambda p: len(p.get('d', '')))
        d = main.get('d', '')
        n = r'[-\d.]+'
        pts = []
        for m in re.finditer(rf'[ML]\s*({n})[,\s]+({n})', d):
            try:
                pts.append((m.start(), float(m.group(1)), float(m.group(2))))
            except ValueError:
                pass
        for m in re.finditer(rf'C\s*{n}[,\s]+{n}[,\s]+{n}[,\s]+{n}[,\s]+({n})[,\s]+({n})', d):
            try:
                pts.append((m.start(), float(m.group(1)), float(m.group(2))))
            except ValueError:
                pass
        pts.sort(key=lambda p: p[0])
        return [DataPoint(x=x, y=y,value_x=x, value_y=y) for _, x, y in pts]

    def _extract_circles(self):
        points = []
        for c in self.svg.find_all('circle'):
            try:
                points.append(DataPoint(
                    x=float(c.get('cx', 0)),
                    y=float(c.get('cy', 0)),
                    label=c.get('data-key') or None,
                    value_x=c.get('cx', 0), value_y=c.get('cx', 0)
                ))
            except (ValueError, TypeError):
                continue
        return points

    def _extract_line_segments(self):
        lines = self.svg.find_all(['line', 'svg:line'])
        data_lines = []
        for ln in lines:
            try:
                x1, y1 = float(ln.get('x1', 0)), float(ln.get('y1', 0))
                x2, y2 = float(ln.get('x2', 0)), float(ln.get('y2', 0))
            except (ValueError, TypeError):
                continue
            dx, dy = abs(x2 - x1), abs(y2 - y1)
            if dx < 2 and dy < 20:
                continue
            if dx == 0 or dy == 0:
                continue
            data_lines.append((x1, y1, x2, y2))
        if not data_lines:
            return []
        points_set = {}
        for x1, y1, x2, y2 in data_lines:
            points_set[x1] = y1
            points_set[x2] = y2
        return [DataPoint(x=x, y=y, value_x=x, value_y=y) for x, y in sorted(points_set.items())]

    def _extract_data(self):
        rects = self._extract_rects()
        if len(rects) > 3:
            return ChartData(series=[DataSeries(
                encoding={'x': 'index', 'y': 'height'}, values=rects,
                style=SeriesStyle(markType='bar'),
            )])
        paths = self._extract_paths()
        if paths:
            return ChartData(series=[DataSeries(
                encoding={'x': 'x', 'y': 'y'}, values=paths,
                style=SeriesStyle(markType='line'),
            )])
        segments = self._extract_line_segments()
        if segments:
            return ChartData(series=[DataSeries(
                encoding={'x': 'x', 'y': 'y'}, values=segments,
                style=SeriesStyle(markType='line'),
            )])
        circles = self._extract_circles()
        if circles:
            return ChartData(series=[DataSeries(
                encoding={'x': 'cx', 'y': 'cy'}, values=circles,
                style=SeriesStyle(markType='point'),
            )])
        return ChartData(series=[])

