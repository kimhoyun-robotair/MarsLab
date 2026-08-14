from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class StrictConfigModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        allow_inf_nan=False,
    )


FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
PositiveFloat = Annotated[float, Field(gt=0.0, allow_inf_nan=False)]
NonNegativeFloat = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
PositiveInt = Annotated[int, Field(gt=0)]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Vec2 = tuple[FiniteFloat, FiniteFloat]
Vec3 = tuple[FiniteFloat, FiniteFloat, FiniteFloat]
Rgb = tuple[FiniteFloat, FiniteFloat, FiniteFloat]
