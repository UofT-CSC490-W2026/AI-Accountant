import uuid
import logging

from fastapi import APIRouter, Request, UploadFile

from schemas.parse import ParseRequest, ParseAccepted
from config import get_settings
from queues import enqueue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


@router.post("/parse", response_model=ParseAccepted)
async def parse(body: ParseRequest, request: Request):
    parse_id = f"parse_{uuid.uuid4().hex[:12]}"
    enqueue(get_settings().SQS_QUEUE_NORMALIZER, {
        "parse_id": parse_id,
        "input_text": body.input_text,
        "source": body.source,
        "currency": body.currency,
    })
    return ParseAccepted(parse_id=parse_id)


@router.post("/parse/upload", response_model=ParseAccepted)
async def parse_upload(file: UploadFile, request: Request):
    parse_id = f"parse_{uuid.uuid4().hex[:12]}"
    contents = await file.read()
    logger.info("Received file %s (%d bytes), stub S3 upload", file.filename, len(contents))
    # TODO: upload to S3, put S3 key in queue message
    enqueue(get_settings().SQS_QUEUE_NORMALIZER, {
        "parse_id": parse_id,
        "source": "upload",
        "filename": file.filename,
    })
    return ParseAccepted(parse_id=parse_id)
