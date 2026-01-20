from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ValidationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=0)
    regex: str | None = None


class FontPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: str | None = None
    size: float = Field(..., gt=0)
    min_size: float = Field(..., gt=0)

    @field_validator("min_size")
    @classmethod
    def _min_size_not_greater(cls, value: float, info) -> float:
        size = info.data.get("size")
        if size is not None and value > size:
            raise ValueError("min_size must be <= size")
        return value


class Placement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(..., ge=0)
    x: float
    y: float
    max_width: float = Field(..., gt=0)
    height: float | None = None
    align: Literal["left", "center", "right"] = "left"
    font_policy: FontPolicy


class FieldDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    type: Literal["string"]
    required: bool = True
    section: str | None = None
    notes: str | None = None
    validation: ValidationRule | None = None
    placement: Placement


class TemplateSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal["v1"] = "v1"
    name: str = Field(..., min_length=1)
    fields: list[FieldDefinition]


class DraftTemplate(TemplateSchema):
    model_config = ConfigDict(extra="forbid")


def default_template_schema() -> TemplateSchema:
    return TemplateSchema(
        name="default-template",
        fields=[
            FieldDefinition(
                id="name",
                key="name",
                label="Name",
                type="string",
                required=True,
                validation=ValidationRule(min_length=1),
                placement=Placement(
                    page_index=0,
                    x=72,
                    y=720,
                    max_width=240,
                    align="left",
                    font_policy=FontPolicy(size=12, min_size=8),
                ),
            ),
            FieldDefinition(
                id="address",
                key="address",
                label="Address",
                type="string",
                required=True,
                validation=ValidationRule(min_length=1),
                placement=Placement(
                    page_index=0,
                    x=72,
                    y=700,
                    max_width=320,
                    align="left",
                    font_policy=FontPolicy(size=12, min_size=8),
                ),
            ),
            FieldDefinition(
                id="phone",
                key="phone",
                label="Phone",
                type="string",
                required=False,
                placement=Placement(
                    page_index=0,
                    x=72,
                    y=680,
                    max_width=200,
                    align="left",
                    font_policy=FontPolicy(size=12, min_size=8),
                ),
            ),
            FieldDefinition(
                id="email",
                key="email",
                label="Email",
                type="string",
                required=False,
                placement=Placement(
                    page_index=0,
                    x=72,
                    y=660,
                    max_width=260,
                    align="left",
                    font_policy=FontPolicy(size=12, min_size=8),
                ),
            ),
            FieldDefinition(
                id="notes",
                key="notes",
                label="Notes",
                type="string",
                required=False,
                placement=Placement(
                    page_index=0,
                    x=72,
                    y=640,
                    max_width=360,
                    align="left",
                    font_policy=FontPolicy(size=12, min_size=8),
                ),
            ),
        ],
    )
