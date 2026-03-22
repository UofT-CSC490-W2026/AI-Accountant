import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, UploadFile

from auth.deps import AuthContext, get_current_user
from schemas.parse import ParseRequest, ParseAccepted
from config import get_settings
from queues import enqueue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


@router.post("/parse", response_model=ParseAccepted)
async def parse(
    body: ParseRequest,
    request: Request,
    current_user: AuthContext = Depends(get_current_user),
):
    parse_id = f"parse_{uuid.uuid4().hex[:12]}"
    enqueue(get_settings().SQS_QUEUE_NORMALIZER, {
        "parse_id": parse_id,
        "input_text": body.input_text,
        "source": body.source,
        "currency": body.currency,
        "user_id": str(current_user.user.id),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    })
    return ParseAccepted(parse_id=parse_id)


@router.post("/parse/upload", response_model=ParseAccepted)
async def parse_upload(
    file: UploadFile,
    request: Request,
    current_user: AuthContext = Depends(get_current_user),
):
    parse_id = f"parse_{uuid.uuid4().hex[:12]}"
    contents = await file.read()
    logger.info("Received file %s (%d bytes), stub S3 upload", file.filename, len(contents))
    # TODO: upload to S3, put S3 key in queue message
    enqueue(get_settings().SQS_QUEUE_NORMALIZER, {
        "parse_id": parse_id,
        "source": "upload",
        "filename": file.filename,
        "user_id": str(current_user.user.id),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    })
    return ParseAccepted(parse_id=parse_id)
