from pydantic import BaseModel


class AuthMeResponse(BaseModel):
    id: str
    cognito_sub: str
    email: str
    role: str
    role_source: str
    token_use: str


class AuthLoginUrlResponse(BaseModel):
    login_url: str


class AuthLogoutUrlResponse(BaseModel):
    logout_url: str


class AuthTokenExchangeRequest(BaseModel):
    code: str
    redirect_uri: str
    code_verifier: str


class AuthRefreshRequest(BaseModel):
    refresh_token: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    id_token: str | None = None
    refresh_token: str | None = None


class AuthValidateResponse(BaseModel):
    authenticated: bool
    user: AuthMeResponse
