import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, status

from auth.deps import AuthContext, get_current_user
from queues import sqs
from schemas.parse import DEFAULT_POST_STAGES, DEFAULT_STAGES, ParseAccepted, ParseRequest, ParseStatusResponse
from services.shared.parse_status import load_status, set_status
from services.shared.ingestion import IngestedStatement, parse_uploaded_statements, split_manual_statements

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


def _build_batch_payload(statements: list[IngestedStatement]) -> dict:
    return {
        "total_statements": len(statements),
        "completed_statements": 0,
        "pending_statements": len(statements),
        "auto_posted_count": 0,
        "needs_clarification_count": 0,
        "resolved_count": 0,
        "rejected_count": 0,
        "failed_count": 0,
        "status": "accepted",
        "items": [],
    }


def _enqueue_statement_batch(
    *,
    parse_id: str,
    statements: list[IngestedStatement],
    user_id: str,
    submitted_at: str,
    stages: list[str],
    store: bool,
    post_stages: list[str],
) -> None:
    is_batch = len(statements) > 1
    for index, statement in enumerate(statements):
        child_parse_id = parse_id if not is_batch else f"{parse_id}_s{index + 1}"
        sqs.enqueue.normalization(
            parse_id=child_parse_id,
            parent_parse_id=parse_id if is_batch else None,
            statement_index=index,
            statement_total=len(statements),
            input_text=statement.input_text,
            source=statement.source,
            currency=statement.currency,
            filename=statement.filename,
            transaction_date=statement.transaction_date,
            amount=statement.amount,
            counterparty=statement.counterparty,
            user_id=user_id,
            submitted_at=submitted_at,
            stages=stages,
            store=store,
            post_stages=post_stages,
        )


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
    statements = split_manual_statements(body.input_text, source=body.source, currency=body.currency)
    if not statements:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="input_text must contain at least one statement",
        )
    submitted_at = datetime.now(timezone.utc).isoformat()
    _enqueue_statement_batch(
        parse_id=parse_id,
        statements=statements,
        user_id=str(current_user.user.id),
        submitted_at=submitted_at,
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
        batch=_build_batch_payload(statements) if len(statements) > 1 else None,
    )
    return ParseAccepted(parse_id=parse_id, statement_count=len(statements))


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
    inferred_source = source or _infer_upload_source(file.filename)
    logger.info("Received file %s (%d bytes), extracting statements", file.filename, len(contents))
    statements = parse_uploaded_statements(
        contents=contents,
        filename=file.filename,
        source=inferred_source,
    )
    if not statements:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="uploaded file did not contain any statements",
        )
    submitted_at = datetime.now(timezone.utc).isoformat()
    _enqueue_statement_batch(
        parse_id=parse_id,
        statements=statements,
        user_id=str(current_user.user.id),
        submitted_at=submitted_at,
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
        input_text=file.filename or "Uploaded file",
        batch=_build_batch_payload(statements) if len(statements) > 1 else None,
    )
    return ParseAccepted(parse_id=parse_id, statement_count=len(statements))


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
