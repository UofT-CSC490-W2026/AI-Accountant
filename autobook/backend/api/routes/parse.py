import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status

from auth.deps import AuthContext, get_current_user
from queues import sqs
from schemas.parse import DEFAULT_POST_STAGES, DEFAULT_STAGES, ParseAccepted, ParseRequest, ParseStatusResponse
from services.shared.parse_status import load_status, set_status

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
    request: Request,
    current_user: AuthContext = Depends(get_current_user),
):
    if body.post_stages and not body.store:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="post_stages requires store to be true",
        )
    parse_id = f"parse_{uuid.uuid4().hex[:12]}"
    sqs.enqueue.normalization(
        parse_id=parse_id,
        input_text=body.input_text,
        source=body.source,
        currency=body.currency,
        user_id=str(current_user.user.id),
        submitted_at=datetime.now(timezone.utc).isoformat(),
        stages=body.stages,
        store=body.store,
        post_stages=body.post_stages,
    )
    await set_status(
        request.app.state.redis,
        parse_id=parse_id,
        user_id=str(current_user.user.id),
        status="accepted",
        stage="queued",
        input_text=body.input_text,
    )
    return ParseAccepted(parse_id=parse_id)


@router.post("/parse/upload", response_model=ParseAccepted)
async def parse_upload(
    file: UploadFile,
    request: Request,
    source: str | None = Form(default=None),
    store: bool = Form(default=True),
    stages: list[str] | None = Form(default=None),
    post_stages: list[str] | None = Form(default=None),
    current_user: AuthContext = Depends(get_current_user),
):
    if post_stages and not store:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="post_stages requires store to be true",
        )
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
        stages=stages if stages is not None else list(DEFAULT_STAGES),
        store=store,
        post_stages=post_stages if post_stages is not None else list(DEFAULT_POST_STAGES),
    )
    await set_status(
        request.app.state.redis,
        parse_id=parse_id,
        user_id=str(current_user.user.id),
        status="accepted",
        stage="queued",
        input_text=file.filename,
    )
    return ParseAccepted(parse_id=parse_id)


@router.get("/parse/{parse_id}", response_model=ParseStatusResponse)
async def get_parse_status(
    parse_id: str,
    request: Request,
    current_user: AuthContext = Depends(get_current_user),
):
    payload = await load_status(request.app.state.redis, parse_id)
    if payload is None or payload.get("user_id") != str(current_user.user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="parse not found")
    return ParseStatusResponse(**payload)
