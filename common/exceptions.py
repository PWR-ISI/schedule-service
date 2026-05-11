from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Domain error."

    def __init__(self, detail: str = None):
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class SlotUnavailable(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Slot is not available for reservation."


class InvalidTransition(DomainError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Status transition not permitted."


def exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response({"detail": exc.detail}, status=exc.status_code)
    return drf_exception_handler(exc, context)
