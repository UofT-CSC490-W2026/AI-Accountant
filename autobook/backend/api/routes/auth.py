from __future__ import annotations

from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status

from auth.deps import AuthContext, get_current_user
from config import Settings, get_settings
from schemas.auth import (
    AuthLoginUrlResponse,
    AuthLogoutUrlResponse,
    AuthMeResponse,
    AuthRefreshRequest,
    AuthTokenExchangeRequest,
    AuthTokenResponse,
    AuthValidateResponse,
)

router = APIRouter(prefix="/api/v1")


@router.get("/auth/login-url", response_model=AuthLoginUrlResponse)
async def get_login_url(
    redirect_uri: str = Query(...),
    code_challenge: str = Query(...),
    state: str | None = Query(default=None),
):
    settings = get_settings()
    cognito_domain = _get_cognito_domain(settings)
    params = {
        "response_type": "code",
        "client_id": settings.COGNITO_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": settings.COGNITO_SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
    }
    if state:
        params["state"] = state
    return AuthLoginUrlResponse(login_url=f"{cognito_domain}/login?{urlencode(params)}")


@router.get("/auth/logout-url", response_model=AuthLogoutUrlResponse)
async def get_logout_url(logout_uri: str = Query(...)):
    settings = get_settings()
    cognito_domain = _get_cognito_domain(settings)
    params = {
        "client_id": settings.COGNITO_CLIENT_ID,
        "logout_uri": logout_uri,
    }
    return AuthLogoutUrlResponse(logout_url=f"{cognito_domain}/logout?{urlencode(params)}")


@router.post("/auth/token", response_model=AuthTokenResponse)
async def exchange_code_for_token(body: AuthTokenExchangeRequest):
    payload = await _exchange_token(
        {
            "grant_type": "authorization_code",
            "client_id": get_settings().COGNITO_CLIENT_ID,
            "code": body.code,
            "redirect_uri": body.redirect_uri,
            "code_verifier": body.code_verifier,
        }
    )
    return AuthTokenResponse(**payload)


@router.post("/auth/refresh", response_model=AuthTokenResponse)
async def refresh_token(body: AuthRefreshRequest):
    payload = await _exchange_token(
        {
            "grant_type": "refresh_token",
            "client_id": get_settings().COGNITO_CLIENT_ID,
            "refresh_token": body.refresh_token,
        }
    )
    return AuthTokenResponse(**payload)


@router.get("/auth/validate", response_model=AuthValidateResponse)
async def validate_token(current_user: AuthContext = Depends(get_current_user)):
    return AuthValidateResponse(
        authenticated=True,
        user=_serialize_auth_me(current_user),
    )


@router.get("/auth/me", response_model=AuthMeResponse)
async def get_me(current_user: AuthContext = Depends(get_current_user)):
    return _serialize_auth_me(current_user)


def _serialize_auth_me(current_user: AuthContext) -> AuthMeResponse:
    return AuthMeResponse(
        id=str(current_user.user.id),
        cognito_sub=current_user.user.cognito_sub,
        email=current_user.user.email,
        role=current_user.role.value,
        role_source=current_user.role_source,
        token_use=current_user.claims.token_use,
    )


def _get_cognito_domain(settings: Settings) -> str:
    if not settings.COGNITO_DOMAIN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cognito hosted UI is not configured.",
        )
    if settings.COGNITO_DOMAIN.startswith("http://") or settings.COGNITO_DOMAIN.startswith("https://"):
        return settings.COGNITO_DOMAIN.rstrip("/")
    return f"https://{settings.COGNITO_DOMAIN.rstrip('/')}"


async def _exchange_token(form_data: dict[str, str]) -> dict[str, object]:  # pragma: no cover
    settings = get_settings()
    cognito_domain = _get_cognito_domain(settings)
    token_url = f"{cognito_domain}/oauth2/token"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                token_url,
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach Cognito token endpoint.",
        ) from exc

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Cognito token exchange failed.",
        )

    payload = response.json()
    payload.setdefault("token_type", "Bearer")
    return payload
