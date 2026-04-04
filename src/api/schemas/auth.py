"""
Schemas for dashboard authentication flows.
"""

from typing import Optional

from pydantic import BaseModel, Field


class AuthLoginRequest(BaseModel):
    username: str = Field(..., description="Dashboard username")
    password: str = Field(..., description="Dashboard password")


class AuthChangePasswordRequest(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")


class AuthUserModel(BaseModel):
    username: str = Field(..., description="Authenticated dashboard username")


class AuthStatusResponse(BaseModel):
    success: bool
    auth_enabled: bool
    password_configured: bool
    bootstrap_password_enabled: bool
    session_ttl_minutes: int
    user: Optional[AuthUserModel] = None
    message: Optional[str] = None


class AuthLoginResponse(BaseModel):
    success: bool
    message: str
    user: Optional[AuthUserModel] = None

