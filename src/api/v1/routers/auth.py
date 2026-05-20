from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.schemas.auth import (
    AuthChangePasswordRequest,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthStatusResponse,
    AuthUserModel,
)
from src.api.v1._state import load_config
from src.api.v1.deps import require_api_key
from src.auth import (
    get_dashboard_auth_state,
    hash_dashboard_password,
    validate_new_password,
    verify_dashboard_login,
    verify_dashboard_password,
)

router = APIRouter(tags=["Authentication"])


def _build_auth_status_response(message: Optional[str] = None) -> AuthStatusResponse:
    config = load_config()
    auth_state = get_dashboard_auth_state(config)
    return AuthStatusResponse(
        success=True,
        auth_enabled=auth_state.enabled,
        password_configured=auth_state.password_configured,
        bootstrap_password_enabled=auth_state.bootstrap_password_enabled,
        session_ttl_minutes=auth_state.session_ttl_minutes,
        user=AuthUserModel(username=auth_state.username),
        message=message,
    )


@router.get("/v1/auth/status", response_model=AuthStatusResponse)
async def get_auth_status() -> AuthStatusResponse:
    return _build_auth_status_response()


@router.post("/v1/auth/login", response_model=AuthLoginResponse)
async def login_dashboard_user(payload: AuthLoginRequest) -> AuthLoginResponse:
    config = load_config()
    auth_state = get_dashboard_auth_state(config)

    if not auth_state.enabled:
        return AuthLoginResponse(
            success=False,
            message="Dashboard authentication is disabled.",
            user=None,
        )

    if not verify_dashboard_login(config, payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid dashboard credentials",
        )

    return AuthLoginResponse(
        success=True,
        message="Dashboard login successful",
        user=AuthUserModel(username=auth_state.username),
    )


@router.post(
    "/v1/auth/change-password",
    response_model=AuthStatusResponse,
    dependencies=[Depends(require_api_key)],
)
async def change_dashboard_password(
    payload: AuthChangePasswordRequest,
) -> AuthStatusResponse:
    config = load_config()
    validation_error = validate_new_password(payload.new_password)
    if validation_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_error,
        )

    if not verify_dashboard_password(config, payload.current_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is invalid",
        )

    config.security.dashboard_password_hash = hash_dashboard_password(
        payload.new_password
    )
    config.save()
    return _build_auth_status_response(
        message="Dashboard password updated successfully",
    )
