from lxml import etree
from typing import Optional, Literal
import re
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

class VizParser:
    """Parse Parent Component of SVGs"""
    def __init__(self, container_string: str, svg_string: str):
        self.container_string = container_string
        self.svg_string = svg_string

    def parse_svg(self, svg_string: str, context: Optional[ChartContext] = None) -> ChartRepresentation:
        """Convenience function to parse SVG string"""
        parser = SVGParser(svg_string)
        return parser.parse(context)

        

class SVGParser:
    """Parse SVG visualizations into structured chart representations"""

    def __init__(self, svg_string: str):
        self.svg_string = svg_string
        self.root = etree.fromstring(svg_string.encode())
        self.ns = {'svg': 'http://www.w3.org/2000/svg'}
        self._has_ns = bool(self.root.nsmap)

    def parse(self, context: Optional[ChartContext] = None) -> ChartRepresentation:
        """Main parsing function"""
        # Extract all elements
        text_elements = self._extract_text_elements()
        rects = self._extract_rects()
        paths = self._extract_paths()
        circles = self._extract_circles()
        lines = self._extract_lines()

        # Parse chart components
        title = self._extract_title(text_elements)
        axes = self._parse_axes(text_elements, lines)
        chart_type = self._infer_chart_type(rects, paths, circles, lines)
        data = self._extract_data(rects, paths, circles, lines, chart_type, axes)

        metadata = ChartMetadata(
            title=title,
            chartType=chart_type,
            inferredType=None
        )

        return ChartRepresentation(
            metadata=metadata,
            axes=axes,
            data=data,
            legend=None,  # TODO: implement legend extraction
            annotations=None,  # TODO: implement annotation extraction
            context=context
        )

    def _xpath(self, tag: str) -> list:
        if self._has_ns:
            return self.root.xpath(f'.//svg:{tag}', namespaces=self.ns)
        return self.root.xpath(f'.//*[local-name()="{tag}"]')

    def _extract_text_elements(self) -> list[dict]:
        texts = []
        for text in self._xpath('text'):
            content = ''.join(text.itertext()).strip()
            if not content:
                continue

            try:
                x = self._parse_number(text.get('x', '0'))
                y = self._parse_number(text.get('y', '0'))
            except (ValueError, TypeError):
                x, y = 0.0, 0.0
            font_size = self._parse_font_size(text.get('font-size', '12'))
            font_weight = text.get('font-weight', 'normal')

            texts.append({
                'content': content,
                'x': x,
                'y': y,
                'fontSize': font_size,
                'fontWeight': font_weight,
                'element': text
            })

        return texts

    def _extract_rects(self) -> list[dict]:
        """Extract rectangle elements (common for bar charts)"""
        rects = []
        for rect in self._xpath('rect'):
            try:
                x = self._parse_number(rect.get('x', '0'))
                y = self._parse_number(rect.get('y', '0'))
                width = self._parse_number(rect.get('width', '0'))
                height = self._parse_number(rect.get('height', '0'))
            except (ValueError, TypeError):
                # Skip rects with invalid dimensions (percentages, etc.)
                continue

            fill = rect.get('fill', 'none')

            # Skip background/frame rects or tiny rects
            if fill in ['none', 'transparent', 'white', '#fff', '#ffffff'] or width < 1 or height < 1:
                continue

            rects.append({
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'fill': fill,
                'element': rect
            })

        return rects

    def _extract_paths(self) -> list[dict]:
        """Extract path elements (common for line charts)"""
        paths = []
        for path in self._xpath('path'):
            d = path.get('d', '')
            stroke = path.get('stroke', 'none')
            fill = path.get('fill', 'none')

            # Skip if no visible stroke or fill
            if stroke == 'none' and fill == 'none':
                continue

            paths.append({
                'd': d,
                'stroke': stroke,
                'fill': fill,
                'strokeWidth': self._safe_float(path.get('stroke-width', '1')),
                'element': path
            })

        return paths

    def _extract_circles(self) -> list[dict]:
        """Extract circle elements (common for scatter plots)"""
        circles = []
        for circle in self._xpath('circle'):
            try:
                cx = self._parse_number(circle.get('cx', '0'))
                cy = self._parse_number(circle.get('cy', '0'))
                r = self._parse_number(circle.get('r', '0'))
            except (ValueError, TypeError):
                continue

            fill = circle.get('fill', 'none')

            # Skip tiny circles (likely decorative)
            if r < 1:
                continue

            circles.append({
                'cx': cx,
                'cy': cy,
                'r': r,
                'fill': fill,
                'element': circle
            })

        return circles

    def _extract_lines(self) -> list[dict]:
        """Extract line elements (for axes, grids)"""
        lines = []
        for line in self._xpath('line'):
            try:
                x1 = self._parse_number(line.get('x1', '0'))
                y1 = self._parse_number(line.get('y1', '0'))
                x2 = self._parse_number(line.get('x2', '0'))
                y2 = self._parse_number(line.get('y2', '0'))
            except (ValueError, TypeError):
                continue
            stroke = line.get('stroke', 'black')

            lines.append({
                'x1': x1,
                'y1': y1,
                'x2': x2,
                'y2': y2,
                'stroke': stroke,
                'strokeWidth': self._safe_float(line.get('stroke-width', '1')),
                'element': line
            })

        return lines

    def _extract_title(self, text_elements: list[dict]) -> Optional[str]:
        """Extract chart title (usually largest/boldest text at top)"""
        if not text_elements:
            return None

        # Find text with largest font size or bold weight
        title_candidates = sorted(
            text_elements,
            key=lambda t: (t['fontWeight'] == 'bold', t['fontSize']),
            reverse=True
        )

        if title_candidates:
            return title_candidates[0]['content']

        return None

    def _parse_axes(self, text_elements: list[dict], lines: list[dict]) -> dict[str, AxisInfo]:
        """Parse axis information from text and line elements"""
        axes = {}

        # Simple heuristic: horizontal text at bottom = x-axis, vertical text at left = y-axis
        # Group texts by position
        sorted_by_y = sorted(text_elements, key=lambda t: t['y'])
        sorted_by_x = sorted(text_elements, key=lambda t: t['x'])

        # X-axis: texts at bottom
        if len(sorted_by_y) > 3:
            bottom_texts = sorted_by_y[-5:]  # Last 5 texts
            x_ticks = [t['content'] for t in bottom_texts if self._is_numeric_or_temporal(t['content'])]

            if x_ticks:
                x_type = self._infer_axis_type(x_ticks)
                axes['x'] = AxisInfo(
                    label=None,  # TODO: extract axis label
                    type=x_type,
                    scale='linear' if x_type == 'quantitative' else 'time' if x_type == 'temporal' else None,
                    domain=self._extract_domain(x_ticks) if x_type == 'quantitative' else None,
                    ticks=x_ticks
                )

        # Y-axis: texts at left
        if len(sorted_by_x) > 3:
            left_texts = sorted_by_x[:5]  # First 5 texts
            y_ticks = [t['content'] for t in left_texts if self._is_numeric_or_temporal(t['content'])]

            if y_ticks:
                y_type = self._infer_axis_type(y_ticks)
                axes['y'] = AxisInfo(
                    label=None,  # TODO: extract axis label
                    type=y_type,
                    scale='linear' if y_type == 'quantitative' else None,
                    domain=self._extract_domain(y_ticks) if y_type == 'quantitative' else None,
                    ticks=y_ticks
                )

        return axes

    def _is_numeric_or_temporal(self, text: str) -> bool:
        """Check if text is numeric or temporal"""
        # Try to parse as number
        try:
            float(text)
            return True
        except ValueError:
            pass

        # Check for year pattern
        if re.match(r'^\d{4}$', text):
            return True

        # Check for date patterns
        if re.match(r'\d{1,2}/\d{1,2}', text) or re.match(r'\d{4}-\d{2}', text):
            return True

        return False

    def _infer_axis_type(self, ticks: list[str]) -> Literal["quantitative", "temporal", "nominal", "ordinal"]:
        """Infer axis type from tick values"""
        if not ticks:
            return 'nominal'

        # Check if all numeric
        try:
            [float(t) for t in ticks]
            return 'quantitative'
        except ValueError:
            pass

        # Check if temporal (years)
        if all(re.match(r'^\d{4}$', str(t)) for t in ticks):
            return 'temporal'

        # Check if ordinal (could be ordered categories)
        # For now, default to nominal
        return 'nominal'

    def _extract_domain(self, ticks: list[str]) -> Optional[tuple[float, float]]:
        """Extract numeric domain from ticks"""
        try:
            numeric_ticks = [float(t) for t in ticks]
            return (min(numeric_ticks), max(numeric_ticks))
        except ValueError:
            return None

    def _infer_chart_type(self, rects: list, paths: list, circles: list, lines: list) -> str:
        """Infer chart type from visual marks"""
        # Simple heuristics
        if len(rects) > 3:
            return 'bar'

        # Check for line chart (path with stroke, no fill)
        line_paths = [p for p in paths if p['stroke'] != 'none' and p['fill'] == 'none']
        if line_paths:
            return 'line'

        # Check for scatter (multiple circles)
        if len(circles) > 5:
            return 'scatter'

        # Check for area chart (path with fill)
        area_paths = [p for p in paths if p['fill'] != 'none']
        if area_paths:
            return 'area'

        return 'unknown'

    def _extract_data(self, rects: list, paths: list, circles: list,
                     lines: list, chart_type: str, axes: dict) -> ChartData:
        """Extract data points based on chart type"""
        if chart_type == 'bar':
            return self._extract_bar_data(rects, axes)
        elif chart_type == 'line':
            return self._extract_line_data(paths, axes)
        elif chart_type == 'scatter':
            return self._extract_scatter_data(circles, axes)
        else:
            # Return empty data
            return ChartData(series=[])

    def _extract_bar_data(self, rects: list, axes: dict) -> ChartData:
        """Extract data from bar chart rectangles"""
        data_points = []

        for i, rect in enumerate(rects):
            # For vertical bars: x position = category, height = value
            x_val = rect['x'] + rect['width'] / 2  # Center of bar
            y_val = rect['height']  # Height represents value

            data_points.append(DataPoint(
                x=i,  # Use index for now
                y=y_val,
                label=None
            ))

        style = SeriesStyle(
            color=rects[0]['fill'] if rects else None,
            strokeWidth=None,
            markType='bar'
        )

        series = DataSeries(
            name=None,
            encoding={'x': 'category', 'y': 'value'},
            values=data_points,
            style=style
        )

        return ChartData(series=[series])

    def _extract_line_data(self, paths: list, axes: dict) -> ChartData:
        """Extract data from line chart paths"""
        # Parse path 'd' attribute to extract points
        # This is simplified - real implementation would need robust path parsing
        series_list = []

        for path in paths:
            if path['stroke'] == 'none':
                continue

            points = self._parse_path_points(path['d'])

            data_points = [
                DataPoint(x=p[0], y=p[1], label=None)
                for p in points
            ]

            style = SeriesStyle(
                color=path['stroke'],
                strokeWidth=path['strokeWidth'],
                markType='line'
            )

            series = DataSeries(
                name=None,
                encoding={'x': 'x', 'y': 'y'},
                values=data_points,
                style=style
            )

            series_list.append(series)

        return ChartData(series=series_list)

    def _extract_scatter_data(self, circles: list, axes: dict) -> ChartData:
        """Extract data from scatter plot circles"""
        data_points = []

        for circle in circles:
            data_points.append(DataPoint(
                x=circle['cx'],
                y=circle['cy'],
                label=None
            ))

        style = SeriesStyle(
            color=circles[0]['fill'] if circles else None,
            strokeWidth=None,
            markType='point'
        )

        series = DataSeries(
            name=None,
            encoding={'x': 'x', 'y': 'y'},
            values=data_points,
            style=style
        )

        return ChartData(series=[series])

    def _parse_path_points(self, d: str) -> list[tuple[float, float]]:
        """Parse SVG path 'd' attribute to extract x,y points"""
        points = []
        current_x, current_y = 0.0, 0.0

        # Split path into commands and coordinates
        # Handle M, L, H, V, C (cubic bezier), Q (quadratic), S, T
        commands = re.findall(r'([MLHVCQSTA])\s*([\d.,\s-]+)', d, re.IGNORECASE)

        for cmd, coords in commands:
            cmd_upper = cmd.upper()
            is_relative = cmd.islower()

            # Parse coordinate numbers
            nums = re.findall(r'([\d.-]+)', coords)
            if not nums:
                continue

            try:
                floats = [float(n) for n in nums]
            except ValueError:
                continue

            if cmd_upper == 'M':  # Moveto
                if len(floats) >= 2:
                    x, y = floats[0], floats[1]
                    if is_relative:
                        current_x += x
                        current_y += y
                    else:
                        current_x, current_y = x, y
                    points.append((current_x, current_y))

            elif cmd_upper == 'L':  # Lineto
                for i in range(0, len(floats) - 1, 2):
                    x, y = floats[i], floats[i + 1]
                    if is_relative:
                        current_x += x
                        current_y += y
                    else:
                        current_x, current_y = x, y
                    points.append((current_x, current_y))

            elif cmd_upper == 'H':  # Horizontal line
                for x in floats:
                    if is_relative:
                        current_x += x
                    else:
                        current_x = x
                    points.append((current_x, current_y))

            elif cmd_upper == 'V':  # Vertical line
                for y in floats:
                    if is_relative:
                        current_y += y
                    else:
                        current_y = y
                    points.append((current_x, current_y))

            elif cmd_upper == 'C':  # Cubic bezier - take endpoint
                for i in range(0, len(floats) - 5, 6):
                    # Skip control points, take endpoint
                    x, y = floats[i + 4], floats[i + 5]
                    if is_relative:
                        current_x += x
                        current_y += y
                    else:
                        current_x, current_y = x, y
                    points.append((current_x, current_y))

            elif cmd_upper == 'Q':  # Quadratic bezier - take endpoint
                for i in range(0, len(floats) - 3, 4):
                    x, y = floats[i + 2], floats[i + 3]
                    if is_relative:
                        current_x += x
                        current_y += y
                    else:
                        current_x, current_y = x, y
                    points.append((current_x, current_y))

            elif cmd_upper in ['S', 'T']:  # Smooth bezier - take endpoint
                for i in range(0, len(floats) - 1, 2):
                    x, y = floats[i], floats[i + 1]
                    if is_relative:
                        current_x += x
                        current_y += y
                    else:
                        current_x, current_y = x, y
                    points.append((current_x, current_y))

        return points

    def _safe_float(self, value: str, default: float = 1.0) -> float:
        try:
            return self._parse_number(str(value))
        except (ValueError, TypeError):
            return default

    def _parse_number(self, value: str) -> float:
        """Parse numeric value, handling percentages and units"""
        if not value:
            return 0.0
        # Remove units but raise error for percentages
        value_str = str(value).strip()
        if '%' in value_str:
            raise ValueError(f"Percentage values not supported: {value_str}")
        # Remove common units
        value_str = re.sub(r'(px|pt|rem|em)', '', value_str, flags=re.IGNORECASE)
        return float(value_str)

    def _parse_font_size(self, font_size_str: str) -> float:
        """Parse font size from string (handles 'px', 'pt', etc.)"""
        try:
            return self._parse_number(font_size_str)
        except (ValueError, TypeError):
            return 12.0



