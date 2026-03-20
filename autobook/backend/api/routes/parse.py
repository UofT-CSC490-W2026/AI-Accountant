import uuid
import logging

from fastapi import APIRouter, Request, UploadFile

from schemas.parse import (
    ParseRequest,
    ParseResponse,
    Confidence,
    JournalLine,
    ProposedEntry,
)
from config import get_settings
from queues import enqueue

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


def _mock_parse_response(parse_id: str) -> ParseResponse:
    # TODO: replace with real pipeline result via WebSocket
    threshold = get_settings().AUTO_POST_THRESHOLD
    return ParseResponse(
        parse_id=parse_id,
        status="auto_posted",
        explanation="Posted to equipment and cash.",
        confidence=Confidence(overall=0.94, auto_post_threshold=threshold),
        parse_time_ms=42,
        proposed_entry=ProposedEntry(
            journal_entry_id=f"je_{uuid.uuid4().hex[:8]}",
            lines=[
                JournalLine(account_code="1500", account_name="Equipment", type="debit", amount=2400),
                JournalLine(account_code="1000", account_name="Cash", type="credit", amount=2400),
            ],
        ),
        clarification_id=None,
    )


@router.post("/parse", response_model=ParseResponse)
async def parse(body: ParseRequest, request: Request):
    parse_id = f"parse_{uuid.uuid4().hex[:12]}"
    enqueue(get_settings().SQS_QUEUE_NORMALIZER, {
        "parse_id": parse_id,
        "input_text": body.input_text,
        "source": body.source,
        "currency": body.currency,
    })
    return _mock_parse_response(parse_id)


@router.post("/parse/upload", response_model=ParseResponse)
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
    return _mock_parse_response(parse_id)
