from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.dependencies import CurrentUser, NotificationServiceDependency
from app.schemas.notification import (
    NotificationCreateRequest, NotificationResponse, NotificationUpdateRequest,
)
from app.services.delivery.sender import DeliveryValidationError
from app.services.notifications import NotificationNotFoundError


router = APIRouter(
    prefix="/notifications", tags=["Notifications"],
    responses={401: {"description": "Token de acceso ausente o inválido."}},
)
NOT_FOUND_RESPONSE = {404: {
    "description": "Notificación inexistente o ajena al usuario autenticado.",
    "content": {"application/json": {"example": {"detail": "Notificación no encontrada."}}},
}}
CREATE_ERROR_RESPONSE = {500: {
    "description": "No se pudo completar la creación de la notificación.",
    "content": {"application/json": {"example": {
        "detail": "No se pudo completar la creación de la notificación.",
    }}},
}}


@router.post(
    "", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED,
    summary="Crear una notificación propia",
    description=(
        "Ejecuta una simulación local antes de guardar; no acredita recepción real. El "
        "destinatario es obligatorio, efímero y no se devuelve; SMS admite como máximo "
        "160 caracteres de contenido. Si el guardado ya se confirmó y después falla la "
        "preparación de la respuesta, se devuelve 500 y la fila puede existir."
    ),
    responses=CREATE_ERROR_RESPONSE,
)
def create_notification(
    data: NotificationCreateRequest, user: CurrentUser, service: NotificationServiceDependency
):
    try:
        notification = service.create(
            user.id,
            title=data.title,
            content=data.content,
            channel=data.channel,
            recipient=data.recipient,
        )
        response = NotificationResponse.model_validate(notification)
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=response.model_dump(mode="json"),
        )
    except DeliveryValidationError as error:
        raise RequestValidationError([{
            "type": error.code,
            "loc": ("body", error.field),
        }]) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo completar la creación de la notificación.",
        ) from None


@router.get(
    "", response_model=list[NotificationResponse], summary="Listar todas las notificaciones propias",
    description="Devuelve una lista sin orden garantizado; si no hay notificaciones, devuelve [].",
)
def list_notifications(user: CurrentUser, service: NotificationServiceDependency):
    return service.list_own(user.id)


@router.patch(
    "/{notification_id}", response_model=NotificationResponse, responses=NOT_FOUND_RESPONSE,
    summary="Modificar parcialmente una notificación propia",
)
def update_notification(
    notification_id: UUID, data: NotificationUpdateRequest,
    user: CurrentUser, service: NotificationServiceDependency,
):
    try:
        return service.update(user.id, notification_id, data.model_dump(exclude_unset=True))
    except NotificationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notificación no encontrada."
        ) from None


@router.delete(
    "/{notification_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND_RESPONSE,
    summary="Eliminar definitivamente una notificación propia",
)
def delete_notification(
    notification_id: UUID, user: CurrentUser, service: NotificationServiceDependency
) -> Response:
    try:
        service.delete(user.id, notification_id)
    except NotificationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notificación no encontrada."
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
