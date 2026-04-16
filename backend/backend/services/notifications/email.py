import os

from fastapi import Request

from backend.models.event import Event

REMINDER_LEAD_TIME_MINUTES = 60


class EmailNotificationService:
    def __init__(self, resend_api_key: str) -> None:
        self._resend_api_key = resend_api_key

    async def send_confirmation(self, recipient_email: str, event: Event) -> None:
        # TODO: implement this
        print(f"Sending email to {recipient_email} regarding '{event.json()}'")


def create_email_notification_service(
    resend_api_key: str | None = None,
) -> EmailNotificationService:
    """Create an EmailNotificationService instance using the provided Resend API key or the `RESEND_API_KEY` environment variable."""
    api_key = resend_api_key or os.getenv("RESEND_API_KEY")
    if not api_key:
        raise ValueError(
            "RESEND_API_KEY environment variable is not set and no API key was provided"
        )
    return EmailNotificationService(api_key)


def get_email_notif_service(request: Request) -> EmailNotificationService:
    """FastAPI dependency that returns the shared EmailNotificationService interface."""
    email_notifs: EmailNotificationService | None = getattr(
        request.app.state, "email_notification_service", None
    )
    if email_notifs is None:
        raise RuntimeError("EmailNotificationService not initialized")
    return email_notifs
