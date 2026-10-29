import pytest
from fastapi import HTTPException
from apps.api.src.auth import verify_api_key
from apps.api.src.config import settings


@pytest.mark.asyncio
async def test_auth_valid_key():
    key = await verify_api_key(api_key=settings.API_KEY)
    assert key == settings.API_KEY


@pytest.mark.asyncio
async def test_auth_missing_key():
    with pytest.raises(HTTPException) as excinfo:
        await verify_api_key(api_key=None)
    assert excinfo.value.status_code == 401
    assert excinfo.value.detail["code"] == "AUTH_KEY_MISSING"


@pytest.mark.asyncio
async def test_auth_invalid_key():
    with pytest.raises(HTTPException) as excinfo:
        await verify_api_key(api_key="completely_wrong_key_1234567890123456")
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["code"] == "AUTH_INVALID_KEY"

