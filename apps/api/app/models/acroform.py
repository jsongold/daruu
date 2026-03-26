"""AcroForm field models for PDF form field extraction."""

from pydantic import BaseModel, Field

from app.models.common import BBox


class AcroFormFieldInfo(BaseModel):
    """Information about a single AcroForm field."""

    field_name: str = Field(..., description="Name of the form field")
    field_type: str = Field(
        ..., description="Type of field (text, checkbox, radio, combobox, etc.)"
    )
    value: str = Field(default="", description="Current value of the field")
    readonly: bool = Field(default=False, description="Whether the field is read-only")
    bbox: BBox = Field(..., description="Bounding box of the field on the page")

    model_config = {
        "frozen": True,
        "json_schema_extra": {
            "examples": [
                {
                    "field_name": "氏名",
                    "field_type": "text",
                    "value": "",
                    "readonly": False,
                    "bbox": {
                        "x": 100.0,
                        "y": 200.0,
                        "width": 150.0,
                        "height": 20.0,
                        "page": 1,
                    },
                }
            ]
        },
    }


class PageDimensions(BaseModel):
    """Dimensions of a single page in the PDF."""

    page: int = Field(..., ge=1, description="Page number (1-indexed)")
    width: float = Field(..., gt=0, description="Page width in points")
    height: float = Field(..., gt=0, description="Page height in points")

    model_config = {
        "frozen": True,
        "json_schema_extra": {
            "examples": [
                {
                    "page": 1,
                    "width": 595.0,
                    "height": 842.0,
                }
            ]
        },
    }


class AcroFormFieldsResponse(BaseModel):
    """Response containing AcroForm fields and page information."""

    has_acroform: bool = Field(..., description="Whether the PDF has AcroForm fields")
    page_dimensions: list[PageDimensions] = Field(
        default_factory=list, description="Dimensions of each page"
    )
    fields: list[AcroFormFieldInfo] = Field(
        default_factory=list, description="List of AcroForm fields"
    )
    preview_scale: int = Field(
        default=2,
        description="Scale factor used for preview images (default 2x)",
    )

    model_config = {
        "frozen": True,
        "json_schema_extra": {
            "examples": [
                {
                    "has_acroform": True,
                    "page_dimensions": [{"page": 1, "width": 595.0, "height": 842.0}],
                    "fields": [
                        {
                            "field_name": "氏名",
                            "field_type": "text",
                            "value": "",
                            "readonly": False,
                            "bbox": {
                                "x": 100.0,
                                "y": 200.0,
                                "width": 150.0,
                                "height": 20.0,
                                "page": 1,
                            },
                        }
                    ],
                    "preview_scale": 2,
                }
            ]
        },
    }
