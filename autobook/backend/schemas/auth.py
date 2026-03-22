from pydantic import BaseModel


class AuthMeResponse(BaseModel):
    id: str
    cognito_sub: str
    email: str
    role: str
    role_source: str
    token_use: str
