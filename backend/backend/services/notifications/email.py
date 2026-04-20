import json
import logging
import os
from collections.abc import Mapping
from html import escape
from typing import Protocol

import resend
from fastapi import Request
from resend.exceptions import ResendError, raise_for_code_and_type
from resend.http_client_async import AsyncHTTPClient
from resend.version import get_version

from backend.models.event import Event

REMINDER_LEAD_TIME_MINUTES = 60


def _html_text(value: object) -> str:
    return escape(str(value), quote=True)


class EmailSender(Protocol):
    async def send_async(self, params: Mapping[str, object]) -> None: ...


class ResendEmailSender:
    def __init__(
        self,
        api_key: str,
        api_url: str | None = None,
        http_client: AsyncHTTPClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_url = (
            api_url or os.environ.get("RESEND_API_URL") or resend.api_url
        ).rstrip("/")

        async_http_client = http_client or resend.default_async_http_client
        if async_http_client is None:
            raise RuntimeError("No async Resend HTTP client configured")
        self._http_client = async_http_client

    async def send_async(self, params: Mapping[str, object]) -> None:
        try:
            content, status_code, headers = await self._http_client.request(
                method="post",
                url=f"{self._api_url}/emails",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                    "User-Agent": f"resend-python:{get_version()}",
                },
                json=dict(params),
            )
        except ResendError:
            raise
        except Exception as e:
            raise ResendError(
                code=500,
                error_type="HttpClientError",
                message=str(e),
                suggested_action="Request failed, please try again.",
            ) from e

        if status_code >= 400:
            self._raise_for_error_response(content, status_code, headers)

    @staticmethod
    def _raise_for_error_response(
        content: bytes, status_code: int, headers: Mapping[str, str]
    ) -> None:
        code: str | int = status_code
        error_type = "InternalServerError"
        message = "Unknown error"

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            decoded = content.decode(errors="replace").strip()
            if decoded:
                message = decoded
        else:
            if isinstance(data, dict):
                response_code = data.get("statusCode")
                if isinstance(response_code, (str, int)):
                    code = response_code

                response_error_type = data.get("name") or data.get("type")
                if isinstance(response_error_type, str):
                    error_type = response_error_type

                response_message = data.get("message")
                if isinstance(response_message, str):
                    message = response_message
            elif data is not None:
                message = str(data)

        raise_for_code_and_type(
            code=code,
            error_type=error_type,
            message=message,
            headers=dict(headers),
        )


class EmailNotificationService:
    def __init__(
        self,
        resend_api_key: str,
        from_email: str | None = None,
        email_sender: EmailSender | None = None,
    ) -> None:
        self._email_sender = email_sender or ResendEmailSender(resend_api_key)
        self.from_email = from_email or os.environ.get(
            "EMAIL_FROM", "Acme <onboarding@resend.dev>"
        )

    async def send_event_creation_confirmation(
        self, recipient_email: str, event: Event
    ) -> None:
        event_title = _html_text(event.title)

        try:
            await self._email_sender.send_async(
                {
                    "from": self.from_email,
                    "to": [recipient_email],
                    "subject": "Evently - Event Creation Confirmation",
                    "html": f"<h1>Event Created</h1><p>You created '{event_title}'</p>",
                },
            )
        except ResendError as e:
            logging.getLogger(__name__).exception(
                "Failed to send event creation confirmation email, error: %s", e
            )

    async def send_registration_confirmation(
        self, recipient_email: str, event: Event
    ) -> None:
        event_title = _html_text(event.title)

        try:
            await self._email_sender.send_async(
                {
                    "from": self.from_email,
                    "to": [recipient_email],
                    "subject": "Evently - Registration Confirmation",
                    "html": f"<h1>Registration Confirmed</h1><p>You registered for {event_title}</p>",
                },
            )
        except ResendError as e:
            logging.getLogger(__name__).exception(
                "Failed to send registration confirmation email, error: %s", e
            )

    async def send_event_reminder(self, recipient_email: str, event: Event) -> None:
        event_title = _html_text(event.title)
        start_time = _html_text(event.start_time)

        try:
            await self._email_sender.send_async(
                {
                    "from": self.from_email,
                    "to": [recipient_email],
                    "subject": "Evently - Event Reminder",
                    "html": f"<h1>Event Reminder</h1><p>{event_title} starts at {start_time}</p>",
                },
            )
        except ResendError as e:
            logging.getLogger(__name__).exception(
                "Failed to send event reminder email, error: %s", e
            )


class DisabledEmailNotificationService(EmailNotificationService):
    def __init__(self) -> None:
        self.from_email = os.environ.get("EMAIL_FROM", "Acme <onboarding@resend.dev>")
        self._logger = logging.getLogger(__name__)

    async def _log_disabled_send(
        self, notification_type: str, recipient_email: str, event: Event
    ) -> None:
        self._logger.info(
            "Email notifications disabled; skipping %s email to %s for event %s",
            notification_type,
            recipient_email,
            event.id,
        )

    async def send_event_creation_confirmation(
        self, recipient_email: str, event: Event
    ) -> None:
        await self._log_disabled_send(
            "event creation confirmation", recipient_email, event
        )

    async def send_registration_confirmation(
        self, recipient_email: str, event: Event
    ) -> None:
        await self._log_disabled_send(
            "registration confirmation", recipient_email, event
        )

    async def send_event_reminder(self, recipient_email: str, event: Event) -> None:
        await self._log_disabled_send("event reminder", recipient_email, event)


def create_email_notification_service(
    resend_api_key: str | None = None,
    *,
    allow_missing: bool = False,
) -> EmailNotificationService:
    """Create an EmailNotificationService instance using the provided Resend API key or the `RESEND_API_KEY` environment variable."""
    api_key = resend_api_key or os.getenv("RESEND_API_KEY")
    if not api_key:
        if allow_missing:
            logging.getLogger(__name__).warning(
                "RESEND_API_KEY is not set; email notifications are disabled"
            )
            return DisabledEmailNotificationService()
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
