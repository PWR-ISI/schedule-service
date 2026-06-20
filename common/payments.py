"""
Thin client for the payment-service (PayU).

Used by the booking/cancellation flow when settings.PAYMENTS_ENABLED is True.
Cross-service calls are authenticated with the shared internal token. All calls are
best-effort: callers decide how to handle a None/raised result.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 10


def _headers():
    return {
        "Content-Type": "application/json",
        "X-Internal-Token": settings.INTERNAL_SHARED_TOKEN,
    }


def create_order(*, appointment_id, patient_id, amount=None, description="Wizyta lekarska"):
    """Open a PayU order for an appointment. Returns the payment-service order JSON
    (which includes the PayU `redirect_uri`/`redirectUri`) or raises on failure."""
    url = f"{settings.PAYMENT_SERVICE_URL}/api/payments/orders/"
    payload = {
        "appointment_id": str(appointment_id),
        "patient_id": str(patient_id),
        "amount": str(amount or settings.APPOINTMENT_PRICE_PLN),
        "currency": "PLN",
        "description": description,
    }
    resp = requests.post(url, json=payload, headers=_headers(), timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def refund_for_appointment(appointment_id):
    """Best-effort refund of the payment tied to an appointment. Never raises:
    a failed refund must not block a cancellation."""
    try:
        url = f"{settings.PAYMENT_SERVICE_URL}/api/payments/refund"
        resp = requests.post(
            url,
            json={"appointment_id": str(appointment_id)},
            headers=_headers(),
            timeout=_TIMEOUT,
        )
        if resp.status_code >= 400:
            logger.warning("Refund for appointment %s returned %s: %s",
                           appointment_id, resp.status_code, resp.text[:200])
            return None
        return resp.json()
    except Exception as exc:  # noqa: BLE001 - refund is best-effort
        logger.warning("Refund call for appointment %s failed: %s", appointment_id, exc)
        return None
