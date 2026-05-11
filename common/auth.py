"""
JWT stub middleware + DRF permission classes.

The middleware decodes a JWT from the Authorization header WITHOUT signature
verification. When real signed tokens arrive from auth-identity-service, swap
the decode call for a JWKS-backed verifier — no other code changes.
"""
import logging
from typing import Iterable

import jwt
from django.conf import settings
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


class JWTStubMiddleware:
    BYPASS_PATHS: Iterable[str] = (
        "/health/",
        "/api/schema/",
        "/api/docs/",
        "/admin/",
        "/static/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user_id = None
        request.user_role = None
        request.is_internal = (
            request.headers.get("X-Internal-Token") == settings.INTERNAL_SHARED_TOKEN
        )

        if any(request.path.startswith(p) for p in self.BYPASS_PATHS):
            return self.get_response(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):].strip()
            try:
                payload = jwt.decode(
                    token,
                    options={"verify_signature": False, "verify_exp": False},
                )
                request.user_id = payload.get("sub")
                request.user_role = payload.get("role")
            except jwt.PyJWTError as exc:
                logger.warning("Failed to decode JWT: %s", exc)

        return self.get_response(request)


class IsAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(getattr(request, "user_id", None)) or getattr(request, "is_internal", False)


class _HasRole(BasePermission):
    required_roles: tuple = ()

    def has_permission(self, request, view):
        if getattr(request, "is_internal", False):
            return True
        return getattr(request, "user_role", None) in self.required_roles


class IsPatient(_HasRole):
    required_roles = ("patient",)


class IsDoctor(_HasRole):
    required_roles = ("doctor",)


class IsReceptionist(_HasRole):
    required_roles = ("receptionist",)


class IsAdmin(_HasRole):
    required_roles = ("admin",)


class IsAdminOrDoctor(_HasRole):
    required_roles = ("admin", "doctor")


class IsInternal(BasePermission):
    def has_permission(self, request, view):
        return getattr(request, "is_internal", False)
