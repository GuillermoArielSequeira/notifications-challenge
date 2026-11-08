from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.core.dependencies import CurrentUser, NotificationServiceDependency
from app.schemas.notification import (
    NotificationCreateRequest, NotificationResponse, NotificationUpdateRequest,
)
from app.services.notifications import NotificationNotFoundError


router = APIRouter(
    prefix="/notifications", tags=["Notifications"],
    responses={401: {"description": "Token de acceso ausente o inválido."}},
)
NOT_FOUND_RESPONSE = {404: {
    "description": "Notificación inexistente o ajena al usuario autenticado.",
    "content": {"application/json": {"example": {"detail": "Notificación no encontrada."}}},
}}


@router.post(
    "", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED,
    summary="Crear una notificación propia",
)
def create_notification(
    data: NotificationCreateRequest, user: CurrentUser, service: NotificationServiceDependency
):
    return service.create(user.id, title=data.title, content=data.content, channel=data.channel)


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
