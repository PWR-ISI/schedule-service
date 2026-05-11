import pytest


@pytest.fixture(autouse=True)
def _no_sns_publish(settings):
    """Tests should not require a configured SNS topic ARN."""
    settings.SCHEDULE_SNS_TOPIC_ARN = ""
    yield
