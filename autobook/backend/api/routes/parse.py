import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Form, Request, UploadFile

from schemas.parse import ParseRequest, ParseAccepted
from config import get_settings
from queues import enqueue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


def _infer_upload_source(filename: str | None) -> str:
    if not filename:
        return "upload"

    lowered = filename.lower()
    if lowered.endswith(".csv"):
        return "csv_upload"
    if lowered.endswith(".pdf"):
        return "pdf_upload"
    return "upload"


@router.post("/parse", response_model=ParseAccepted)
async def parse(body: ParseRequest, request: Request):
    parse_id = f"parse_{uuid.uuid4().hex[:12]}"
    enqueue(get_settings().SQS_QUEUE_NORMALIZER, {
        "parse_id": parse_id,
        "input_text": body.input_text,
        "source": body.source,
        "currency": body.currency,
        "user_id": body.user_id,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    })
    return ParseAccepted(parse_id=parse_id)


@router.post("/parse/upload", response_model=ParseAccepted)
async def parse_upload(
    file: UploadFile,
    request: Request,
    user_id: str | None = Form(default=None),
    source: str | None = Form(default=None),
):
    parse_id = f"parse_{uuid.uuid4().hex[:12]}"
    contents = await file.read()
    logger.info("Received file %s (%d bytes), stub S3 upload", file.filename, len(contents))
    # TODO: upload to S3, put S3 key in queue message
    enqueue(get_settings().SQS_QUEUE_NORMALIZER, {
        "parse_id": parse_id,
        "source": source or _infer_upload_source(file.filename),
        "filename": file.filename,
        "user_id": user_id,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    })
    return ParseAccepted(parse_id=parse_id)
