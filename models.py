"""Strict request models for optical operations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


LensType = Literal["plano_convex", "bi_convex", "plano_concave", "bi_concave"]
OptimizationVariable = Literal[
    "radius_1_mm", "radius_2_mm", "center_thickness_mm", "image_distance_mm"
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SingletSpec(StrictModel):
    lens_type: LensType
    glass: str = Field(default="N-BK7", min_length=1, max_length=64)
    radius_1_mm: float | None = None
    radius_2_mm: float | None = None
    center_thickness_mm: float = Field(ge=0.2, le=100)
    diameter_mm: float = Field(ge=1, le=200)

    @field_validator("radius_1_mm", "radius_2_mm")
    @classmethod
    def validate_radius(cls, value: float | None) -> float | None:
        if value is not None and not 1 <= abs(value) <= 10_000:
            raise ValueError("non-planar radius magnitude must be in [1, 10000] mm")
        return value

    @model_validator(mode="after")
    def validate_shape(self) -> "SingletSpec":
        planar = {
            "plano_convex": (True, False),
            "bi_convex": (False, False),
            "plano_concave": (True, False),
            "bi_concave": (False, False),
        }[self.lens_type]
        radii = (self.radius_1_mm, self.radius_2_mm)
        for index, (must_be_planar, value) in enumerate(zip(planar, radii), start=1):
            if must_be_planar and value is not None:
                raise ValueError(f"radius_{index}_mm must be omitted for the planar surface")
            if not must_be_planar and value is None:
                raise ValueError(f"radius_{index}_mm is required for a curved surface")
        return self


class SystemConfiguration(StrictModel):
    wavelengths_um: list[float] = Field(default_factory=lambda: [0.4861, 0.5461, 0.6563], min_length=1, max_length=10)
    field_angles_deg: list[float] = Field(default_factory=lambda: [0.0], min_length=1, max_length=10)
    entrance_pupil_diameter_mm: float = Field(ge=1, le=200)
    image_distance_mm: float | None = Field(default=None, gt=0, le=100_000)

    @field_validator("wavelengths_um")
    @classmethod
    def wavelengths_in_range(cls, values: list[float]) -> list[float]:
        if any(not 0.2 <= value <= 20 for value in values):
            raise ValueError("wavelengths must be in [0.2, 20] um")
        return values

    @field_validator("field_angles_deg")
    @classmethod
    def fields_in_range(cls, values: list[float]) -> list[float]:
        if any(abs(value) > 90 for value in values):
            raise ValueError("field angle magnitude cannot exceed 90 degrees")
        return values


class SpotRequest(StrictModel):
    field_deg: float = Field(default=0, ge=-90, le=90)
    wavelength_um: float = Field(default=0.5461, ge=0.2, le=20)


class MTFRequest(SpotRequest):
    frequencies_lp_per_mm: list[float] = Field(default_factory=lambda: [10, 30, 50], min_length=1, max_length=20)

    @field_validator("frequencies_lp_per_mm")
    @classmethod
    def frequencies_in_range(cls, values: list[float]) -> list[float]:
        if any(not 0 <= value <= 500 for value in values):
            raise ValueError("frequencies must be in [0, 500] lp/mm")
        return values


class OptimizationRequest(StrictModel):
    target_efl_mm: float = Field(ge=5, le=1000)
    variable_names: list[OptimizationVariable] = Field(min_length=1, max_length=4)
    max_iterations: int = Field(default=50, ge=1, le=100)

    @field_validator("variable_names")
    @classmethod
    def variables_unique(cls, values: list[OptimizationVariable]) -> list[OptimizationVariable]:
        if len(values) != len(set(values)):
            raise ValueError("variable_names must be unique")
        return values
