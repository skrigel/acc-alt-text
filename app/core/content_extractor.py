from bs4 import BeautifulSoup, Tag
from app.models.schemas import SvgData, ImgData
from parser.parser import SVGParser, SvgContainer
from parser.schemas import ChartRepresentation
import json
import re

VIZ_KEYWORDS = ['linechart','chart', 'graph', 'plot', 'visualization', 'viz']

def to_compressed_scenegraph(chart: ChartRepresentation, canvas_width: int = 200, canvas_height: int = 200) -> str:
    """Convert ChartRepresentation to the VisText compressed scenegraph string format.

    Format mirrors data/vistext_train_test/data_train.json "scenegraph" field:
      title <text> x <cx> y <y>
      x-axis x <cx> y <y> <label>
      y-axis x <x> y <cy> <label>
      xtick x <x1> val <v1> x <x2> val <v2> ...
      ytick y <y1> val <v1> y <y2> val <v2> ...
      marks <type> XY <x> <y> [width <w> H <h>] desc [<value>] ...
    """
    series = chart.data.series
    values = series[0].values if series else []
    chart_type = chart.metadata.chartType
    title_text = chart.metadata.title or ''
    x_info = chart.axes.get('x')
    y_info = chart.axes.get('y')
    x_ticks = (x_info.ticks if x_info else None) or []
    y_ticks = (y_info.ticks if y_info else None) or []
    x_label = (x_info.label if x_info else None) or ''
    y_label = (y_info.label if y_info else None) or ''

    parts = []

    if title_text:
        parts.append(f'title {title_text} x {canvas_width // 2} y -40')
    if x_label:
        parts.append(f'x-axis x {canvas_width // 2} y 35 {x_label}')
    if y_label:
        parts.append(f'y-axis x -30 y {canvas_height // 2} {y_label}')

    if x_ticks:
        n = len(x_ticks)
        positions = [round(canvas_width * i / (n - 1)) if n > 1 else canvas_width // 2 for i in range(n)]
        parts.append('xtick ' + ' '.join(f'x {pos} val {tick}' for pos, tick in zip(positions, x_ticks)))

    if y_ticks:
        n = len(y_ticks)
        positions = [round(canvas_height - canvas_height * i / (n - 1)) if n > 1 else canvas_height // 2 for i in range(n)]
        parts.append('ytick ' + ' '.join(f'y {pos} val {tick}' for pos, tick in zip(positions, y_ticks)))

    def _desc(p):
        if p.value_x is not None and p.value_y is not None:
            return f'desc {p.value_x}: {p.value_y}'
        if p.value_y is not None:
            return f'desc {p.value_y}'
        return 'desc'

    if values:
        entries = []

        if chart_type == 'bar':
            max_h = max((float(p.y) for p in values if isinstance(p.y, (int, float))), default=1) or 1
            n = len(values)
            slot = canvas_width / n
            bar_w = round(slot * 0.8, 3)
            for i, p in enumerate(values):
                norm_h = round((float(p.y) / max_h) * canvas_height, 3)
                bar_x = round(slot * i + slot * 0.1, 3)
                bar_y = round(canvas_height - norm_h, 3)
                entries.append(f'XY {bar_x} {bar_y} width {bar_w} H {norm_h} {_desc(p)}')
            parts.append(f'marks bar {" ".join(entries)}')

        elif chart_type == 'area':
            xs = [float(p.x) for p in values if isinstance(p.x, (int, float))]
            ys = [float(p.y) for p in values if isinstance(p.y, (int, float))]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            x_span, y_span = x_max - x_min or 1, y_max - y_min or 1
            for p in values:
                nx = round((float(p.x) - x_min) / x_span * canvas_width, 3)
                ny = round((float(p.y) - y_min) / y_span * canvas_height, 3)
                h = round(canvas_height - ny, 3)
                entries.append(f'XY {nx} {ny} H {h} {_desc(p)}')
            parts.append(f'marks area {" ".join(entries)}')

        else:  # line / scatter
            xs = [float(p.x) for p in values if isinstance(p.x, (int, float))]
            ys = [float(p.y) for p in values if isinstance(p.y, (int, float))]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            x_span, y_span = x_max - x_min or 1, y_max - y_min or 1
            for i in range(0,len(values), 3):
                p = values[i]
                nx = round((float(p.x) - x_min) / x_span * canvas_width, 3)
                ny = round((float(p.y) - y_min) / y_span * canvas_height, 3)
                entries.append(f'XY {nx} {ny} {_desc(p)}')
            parts.append(f'marks line {" ".join(entries)}')

    return ' '.join(parts)



def extract_visualizations(html_text: str, base_url: str = "") -> tuple[list[tuple[SvgData,ChartRepresentation]], list[ImgData]]:
    soup = BeautifulSoup(html_text, 'html.parser')
    page_title = get_page_title(soup)

    svgs = soup.find_all("svg")

    viz = []
    for svg in svgs:
        cont = SvgContainer(svg)
        svg_data = extract_svg(svg)
        parser = SVGParser(cont)
        rep = parser.parse()
        if cont.is_data_viz():
            viz.append((svg_data, rep))
  
    return viz, []

def get_page_title(soup: BeautifulSoup) -> str | None:
    return soup.title.get_text(strip=True) if soup.title else None


def extract_svg(tag: Tag) -> SvgData:
    ariaLabel = tag.get('aria-label')
    return SvgData(
        html=str(tag),
        ariaLabel=ariaLabel[0] if ariaLabel else '',
        ariaDescribedBy='',
        parentContext=''
    )
