import secrets
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from apps.api.src.config import settings

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """
    Validates API key using constant-time string comparison.
    Prevents timing attacks against authentication.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_KEY_MISSING", "message": "X-API-Key header is required"},
        )
    
    # Constant-time comparison
    is_valid = secrets.compare_digest(api_key, settings.API_KEY)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "AUTH_INVALID_KEY", "message": "Provided API key is invalid"},
        )
    return api_key

