from pydantic import BaseModel, ConfigDict


class ValidationErrorItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    field: str | None
    message: str


class ValidationErrorResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "detail": [{
                "type": "invalid_email",
                "field": "email",
                "message": "Ingresá un email válido.",
            }]
        }
    })

    detail: list[ValidationErrorItem]
