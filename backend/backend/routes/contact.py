from __future__ import annotations

import logging
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, EmailStr, TypeAdapter
from pymongo.asynchronous.database import AsyncDatabase

from backend.db import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

_email_validator = TypeAdapter(EmailStr)

DbDep = Annotated[AsyncDatabase[dict[str, Any]], Depends(get_db)]

ALLOWED_SUBJECTS = {
    "General Inquiry",
    "Ticketing Issue",
    "Payment Problem",
    "Event Creation Help",
    "Account Issue",
    "Bug Report",
    "Feature Request",
}

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB
CONTACT_RATE_LIMIT_WINDOW_SECONDS = 10 * 60
CONTACT_RATE_LIMIT_MAX_REQUESTS = 10
ALLOWED_ATTACHMENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "application/pdf",
    "text/plain",
}


class ContactResponse(BaseModel):
    id: str
    message: str


class ContactRateLimiter:
    def __init__(self, *, max_requests: int, window_seconds: float) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, client_key: str) -> bool:
        now = monotonic()
        cutoff = now - self._window_seconds

        with self._lock:
            bucket = self._requests[client_key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self._max_requests:
                return False

            bucket.append(now)
            return True


def _get_contact_rate_limiter(request: Request) -> ContactRateLimiter:
    limiter = getattr(request.app.state, "contact_rate_limiter", None)
    if isinstance(limiter, ContactRateLimiter):
        return limiter

    limiter = ContactRateLimiter(
        max_requests=CONTACT_RATE_LIMIT_MAX_REQUESTS,
        window_seconds=CONTACT_RATE_LIMIT_WINDOW_SECONDS,
    )
    request.app.state.contact_rate_limiter = limiter
    return limiter


def _client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@router.post("/", response_model=ContactResponse, status_code=201)
async def submit_contact(
    request: Request,
    db: DbDep,
    subject: Annotated[str, Form()],
    email: Annotated[str, Form()],
    message: Annotated[str, Form()],
    attachment: UploadFile | None = None,
) -> ContactResponse:
    """Accept a support contact form submission."""
    if not _get_contact_rate_limiter(request).allow(_client_key(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many contact submissions. Please try again later.",
        )

    if subject not in ALLOWED_SUBJECTS:
        raise HTTPException(status_code=422, detail="Invalid subject selected.")

    try:
        _email_validator.validate_python(email)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid email address.") from exc

    if not message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    attachment_name: str | None = None
    if attachment and attachment.filename:
        try:
            if (
                attachment.content_type
                and attachment.content_type not in ALLOWED_ATTACHMENT_TYPES
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid attachment type. Allowed: JPG, PNG, GIF, PDF, TXT.",
                )

            total_size = 0
            while chunk := await attachment.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > MAX_ATTACHMENT_SIZE:
                    raise HTTPException(
                        status_code=400,
                        detail="Attachment too large. Max size is 10MB.",
                    )

            attachment_name = attachment.filename
        finally:
            await attachment.close()

    doc: dict[str, Any] = {
        "subject": subject,
        "email": email,
        "message": message.strip(),
        "attachment_filename": attachment_name,
    }
    result = await db["contact_submissions"].insert_one(doc)

    logger.info("Contact submission %s from %s", result.inserted_id, email)

    return ContactResponse(
        id=str(result.inserted_id),
        message="Your message has been received. We'll get back to you within 24 hours.",
    )
