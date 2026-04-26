from app.models.schemas import SvgData
from parser.parser import SVGParser
from parser.schemas import ChartRepresentation, ChartContext


def parse_svg_to_chart(svg_data: SvgData) -> ChartRepresentation | None:
    """
    Parse SvgData into structured ChartRepresentation.
    Returns None if parsing fails.
    """
    try:
        context = ChartContext(
            ariaLabel=svg_data.ariaLabel,
            ariaDescribedBy=svg_data.ariaDescribedBy,
            parentContext=svg_data.parentContext
        )

        parser = SVGParser(svg_data.html)
        chart = parser.parse(context)

        return chart
    except Exception as e:
        print(f"SVG parsing failed: {e}")
        return None
