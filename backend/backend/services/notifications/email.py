import logging
import os

import resend
from fastapi import Request
from resend.exceptions import ResendError

from backend.models.event import Event

REMINDER_LEAD_TIME_MINUTES = 60


class EmailNotificationService:
    def __init__(self, resend_api_key: str, from_email: str | None = None) -> None:
        resend.api_key = resend_api_key  # insane
        self.from_email = from_email or os.environ.get(
            "EMAIL_FROM", "Acme <onboarding@resend.dev>"
        )

    async def send_event_creation_confirmation(
        self, recipient_email: str, event: Event
    ) -> None:
        try:
            await resend.Emails.send_async(
                {
                    "from": self.from_email,
                    "to": [recipient_email],
                    "subject": "Evently - Event Creation Confirmation",
                    "html": f"<h1>Registration Confirmed</h1><p>You registered for {event.title}</p>",
                },
            )
        except ResendError as e:
            logging.getLogger(__name__).exception(
                "Failed to send event creation confirmation email, error: %s", e
            )


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
