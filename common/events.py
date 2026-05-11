"""
Domain event publishing helper.

Events are wrapped in a small envelope (event_type, event_id, occurred_at,
payload) so consumers can dispatch without unpacking SNS attributes. The same
shape is used in both services.
"""
import json
import logging
import uuid
from typing import Optional

from django.utils import timezone

from common.aws import aws_client

logger = logging.getLogger(__name__)


def build_envelope(event_type: str, payload: dict) -> dict:
    return {
        "event_type": event_type,
        "event_id": str(uuid.uuid4()),
        "occurred_at": timezone.now().isoformat(),
        "payload": payload,
    }


def publish(topic_arn: Optional[str], event_type: str, payload: dict) -> Optional[str]:
    if not topic_arn:
        logger.warning("No SNS topic_arn configured; dropping event %s", event_type)
        return None
    envelope = build_envelope(event_type, payload)
    sns = aws_client("sns")
    response = sns.publish(
        TopicArn=topic_arn,
        Message=json.dumps(envelope),
        MessageAttributes={
            "event_type": {"DataType": "String", "StringValue": event_type},
        },
    )
    logger.info("Published %s with message_id=%s", event_type, response.get("MessageId"))
    return response.get("MessageId")
