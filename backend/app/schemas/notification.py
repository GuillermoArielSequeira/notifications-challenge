from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError


def reject_blank_text(value: str) -> str:
    if not value.strip():
        raise PydanticCustomError(
            "blank_text", "El campo no puede contener solo espacios en blanco."
        )
    return value


NotificationTitle = Annotated[
    str, Field(strict=True, min_length=1, max_length=200), AfterValidator(reject_blank_text)
]
NotificationContent = Annotated[
    str, Field(strict=True, min_length=1, max_length=5000), AfterValidator(reject_blank_text)
]
NotificationChannel = Literal["email", "sms", "push"]
NotificationRecipient = Annotated[
    str,
    Field(
        strict=True,
        min_length=1,
        repr=False,
        json_schema_extra={"writeOnly": True},
        description=(
            "Destino efímero para la simulación local. El email es válido hasta 254 "
            "caracteres y normaliza espacios externos y minúsculas; SMS usa + y 8 a 15 "
            "dígitos ASCII sin cero inicial; push usa un token ASCII visible de 1 a 512 "
            "caracteres. El contenido SMS no puede superar 160 caracteres."
        ),
    ),
]


class NotificationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: NotificationTitle
    content: NotificationContent
    channel: NotificationChannel
    recipient: NotificationRecipient


def describe_update_schema(schema: dict[str, Any]) -> None:
    schema["minProperties"] = 1
    # None represents omission internally, not a public default or accepted value.
    for field in schema["properties"].values():
        field.pop("default", None)
        choices = field.pop("anyOf")
        field.update(next(choice for choice in choices if choice.get("type") != "null"))


class NotificationUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra=describe_update_schema)

    # Omitted fields default to None; explicitly supplied None is rejected below.
    title: NotificationTitle | None = None
    content: NotificationContent | None = None
    channel: NotificationChannel | None = None

    @field_validator("title", "content", "channel", mode="before")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise PydanticCustomError("null_not_allowed", "Este campo no admite valores nulos.")
        return value

    @model_validator(mode="after")
    def require_changes(self) -> Self:
        if not self.model_fields_set:
            raise PydanticCustomError("empty_update", "Enviá al menos un campo para modificar.")
        return self


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: NotificationTitle
    content: NotificationContent
    channel: NotificationChannel
