"""
boto3 client factory.

In real AWS, `AWS_ENDPOINT_URL` is empty and boto3 uses the standard endpoint
resolution + IAM credentials. Locally against LocalStack, the env var points
at http://localstack:4566 and we inject dummy static credentials so boto3
doesn't try to walk the credential chain.
"""
import boto3
from django.conf import settings


def aws_client(service: str):
    kwargs = {"region_name": settings.AWS_REGION}
    if settings.AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
        kwargs["aws_access_key_id"] = "test"
        kwargs["aws_secret_access_key"] = "test"
    return boto3.client(service, **kwargs)
