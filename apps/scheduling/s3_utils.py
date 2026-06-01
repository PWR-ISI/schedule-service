"""S3 file upload utilities for appointments."""
import logging
from uuid import uuid4

from django.conf import settings

from common.aws import aws_client

logger = logging.getLogger(__name__)


def upload_appointment_file(file_obj, appointment_id: str) -> str:
    """Upload file to S3, return s3_key. Returns empty string if no bucket configured."""
    if not settings.AWS_S3_BUCKET:
        logger.warning("AWS_S3_BUCKET not configured; skipping S3 upload")
        return ""

    key = f"appointments/{appointment_id}/{uuid4()}/{file_obj.name}"
    try:
        s3 = aws_client("s3")
        s3.upload_fileobj(
            file_obj,
            settings.AWS_S3_BUCKET,
            key,
            ExtraArgs={"ContentType": getattr(file_obj, "content_type", "application/octet-stream")},
        )
        logger.info("Uploaded file to S3: %s", key)
        return key
    except Exception as exc:
        logger.error("Failed to upload file to S3: %s", exc)
        raise


def presigned_url(s3_key: str, expiry: int = 3600) -> str:
    """Generate presigned download URL for a file."""
    if not settings.AWS_S3_BUCKET:
        return ""

    s3 = aws_client("s3")
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.AWS_S3_BUCKET, "Key": s3_key},
            ExpiresIn=expiry,
        )
        return url
    except Exception as exc:
        logger.error("Failed to generate presigned URL: %s", exc)
        return ""
