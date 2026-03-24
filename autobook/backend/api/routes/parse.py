import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, UploadFile

from auth.deps import AuthContext, get_current_user
from queues import sqs
from schemas.parse import ParseAccepted, ParseRequest

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
async def parse(
    body: ParseRequest,
    current_user: AuthContext = Depends(get_current_user),
):
    parse_id = f"parse_{uuid.uuid4().hex[:12]}"
    sqs.enqueue.normalization(
        parse_id=parse_id,
        input_text=body.input_text,
        source=body.source,
        currency=body.currency,
        user_id=str(current_user.user.id),
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )
    return ParseAccepted(parse_id=parse_id)


@router.post("/parse/upload", response_model=ParseAccepted)
async def parse_upload(
    file: UploadFile,
    source: str | None = Form(default=None),
    current_user: AuthContext = Depends(get_current_user),
):
    parse_id = f"parse_{uuid.uuid4().hex[:12]}"
    contents = await file.read()
    logger.info("Received file %s (%d bytes), stub S3 upload", file.filename, len(contents))
    # TODO: upload to S3, put S3 key in queue message
    sqs.enqueue.normalization(
        parse_id=parse_id,
        source=source or _infer_upload_source(file.filename),
        filename=file.filename,
        user_id=str(current_user.user.id),
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )
    return ParseAccepted(parse_id=parse_id)
