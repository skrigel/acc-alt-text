from pydantic import BaseModel
from typing import Optional, Literal


class AxisInfo(BaseModel):
    label: Optional[str] = None
    type: Optional[str]
    domain: Optional[tuple[float, float]] = None
    ticks: Optional[list[str | float]] = None


class DataPoint(BaseModel):
    x: float | str
    y: float | str
    label: Optional[str] = None
    value_x: Optional[float | str] = None  # semantic value along x (tick label or data attribute)
    value_y: Optional[float | str] = None  # semantic value along y


class SeriesStyle(BaseModel):
    color: Optional[str] = None
    strokeWidth: Optional[float] = None
    markType: str  # "line", "point", "bar", "area"


class DataSeries(BaseModel):
    name: Optional[str] = None
    encoding: dict[str, str]  # e.g. {"x": "year", "y": "price"}
    values: list[DataPoint]
    style: SeriesStyle


class ChartData(BaseModel):
    series: list[DataSeries]


class ChartContext(BaseModel):
    ariaLabel: Optional[str] = None
    pageContext: Optional[str] = None
    parentContext: Optional[str] = None

    def to_dict(self):
        return {
            "ariaLabel": self.ariaLabel,
            "pageContext": self.pageContext,
            "parentContext": self.parentContext
        }




class ChartMetadata(BaseModel):
    title: Optional[str] = None
    chartType: str  # "line", "bar", "scatter", "pie", etc.

class ChartRepresentation(BaseModel):
    """Structured representation of a chart for LLM consumption"""
    context: Optional[ChartContext] = None
    metadata: ChartMetadata
    axes: dict[str, AxisInfo]  # "x" and "y" keys
    data: ChartData

    def to_dict(self):

        context  = self.model_dump().get('context')
        md  = self.model_dump().get('metadata')

        return {"context": context,
               "metadata": md,
                "axes":"", 
                "data":""}

# from pydantic import BaseModel
# from typing import Optional, Literal


# # class AxisInfo(BaseModel):
# #     label: Optional[str] = None
# #     type: Literal["quantitative", "temporal", "nominal", "ordinal"]  
# #     scale: Optional[Literal["linear", "log", "time"]] = None
# #     domain: Optional[tuple[float, float]] = None
# #     ticks: Optional[list[str | float]] = None


# # class DataPoint(BaseModel):
# #     x: float | str
# #     y: float | str
# #     label: Optional[str] = None


# # class SeriesStyle(BaseModel):
# #     color: Optional[str] = None
# #     strokeWidth: Optional[float] = None
# #     markType: str  # "line", "point", "bar", "area"


# # class DataSeries(BaseModel):
# #     name: Optional[str] = None
# #     encoding: dict[str, str]  # e.g. {"x": "year", "y": "price"}
# #     values: list[DataPoint]
# #     style: SeriesStyle


# # class ChartData(BaseModel):
# #     series: list[DataSeries]


# # class LegendItem(BaseModel):
# #     label: str
# #     color: str
# #     shape: Optional[str] = None


# # class Legend(BaseModel):
# #     position: Optional[str] = None
# #     items: list[LegendItem]


# # class Annotation(BaseModel):
# #     type: Literal["text", "arrow", "callout"]
# #     text: str
# #     position: Optional[dict[str, float]] = None
# #     target: Optional[str] = None


# # class ChartContext(BaseModel):
# #     ariaLabel: Optional[str] = None
# #     ariaDescribedBy: Optional[str] = None
# #     parentContext: Optional[str] = None


# # class ChartMetadata(BaseModel):
# #     title: Optional[str] = None
# #     chartType: str  # "line", "bar", "scatter", "pie", etc.
# #     inferredType: Optional[str] = None


# # class ChartRepresentation(BaseModel):
# #     """Structured representation of a chart for LLM consumption"""
# #     metadata: ChartMetadata
# #     axes: dict[str, AxisInfo]  # "x" and "y" keys
# #     data: ChartData
# #     legend: Optional[Legend] = None
# #     annotations: Optional[list[Annotation]] = None
# #     context: Optional[ChartContext] = None
