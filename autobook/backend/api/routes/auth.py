from fastapi import APIRouter, Depends

from auth.deps import AuthContext, get_current_user
from schemas.auth import AuthMeResponse

router = APIRouter(prefix="/api/v1")


@router.get("/auth/me", response_model=AuthMeResponse)
async def get_me(current_user: AuthContext = Depends(get_current_user)):
    return AuthMeResponse(
        id=str(current_user.user.id),
        cognito_sub=current_user.user.cognito_sub,
        email=current_user.user.email,
        role=current_user.role.value,
        role_source=current_user.role_source,
        token_use=current_user.claims.token_use,
    )
