# Validates brand aesthetic descriptor data with Pydantic.
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from pydantic import ValidationError
from src.models.descriptor import BrandAestheticDescriptor


@dataclass
class FieldValidationError:
    field: str
    reason: str


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[FieldValidationError] = field(default_factory=list)


# Validates a raw dictionary and collects field level errors.
def validate_descriptor(data: dict[str, Any]) -> ValidationResult:
    errors: list[FieldValidationError] = []

    try:
        BrandAestheticDescriptor(**data)
    except ValidationError as e:
        for error in e.errors():
            field_path = ".".join(str(loc) for loc in error["loc"])
            errors.append(FieldValidationError(field=field_path, reason=error["msg"]))
        return ValidationResult(is_valid=False, errors=errors)

    return ValidationResult(is_valid=True, errors=errors)


# Re validates an existing descriptor instance by round trip parsing.
def validate_descriptor_instance(descriptor: BrandAestheticDescriptor) -> ValidationResult:
    try:
        BrandAestheticDescriptor.model_validate(descriptor.model_dump())
    except ValidationError as e:
        errors = [
            FieldValidationError(
                field=".".join(str(loc) for loc in error["loc"]),
                reason=error["msg"],
            )
            for error in e.errors()
        ]
        return ValidationResult(is_valid=False, errors=errors)

    return ValidationResult(is_valid=True)
