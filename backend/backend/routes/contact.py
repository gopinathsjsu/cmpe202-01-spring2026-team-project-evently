from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
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


@router.post("/", response_model=ContactResponse, status_code=201)
async def submit_contact(
    db: DbDep,
    subject: Annotated[str, Form()],
    email: Annotated[str, Form()],
    message: Annotated[str, Form()],
    attachment: UploadFile | None = None,
) -> ContactResponse:
    """Accept a support contact form submission."""
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
        if (
            attachment.content_type
            and attachment.content_type not in ALLOWED_ATTACHMENT_TYPES
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid attachment type. Allowed: JPG, PNG, GIF, PDF, TXT.",
            )
        content = await attachment.read()
        if len(content) > MAX_ATTACHMENT_SIZE:
            raise HTTPException(
                status_code=400,
                detail="Attachment too large. Max size is 10MB.",
            )
        attachment_name = attachment.filename

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
