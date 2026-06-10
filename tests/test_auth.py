import pytest

from app.auth import BearerAuthMiddleware

EXPECTED_TOKEN = "token-correto"


async def protected_app(scope, receive, send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        }
    )

    await send(
        {
            "type": "http.response.body",
            "body": b"ok",
        }
    )


async def empty_receive() -> dict:
    return {
        "type": "http.request",
        "body": b"",
        "more_body": False,
    }


async def execute_request(
    authorization: str | None = None,
) -> list[dict]:
    headers = []

    if authorization is not None:
        headers.append(
            (
                b"authorization",
                authorization.encode("latin-1"),
            )
        )

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": headers,
    }

    messages = []

    async def capture_send(message: dict) -> None:
        messages.append(message)

    middleware = BearerAuthMiddleware(
        app=protected_app,
        expected_token=EXPECTED_TOKEN,
    )

    await middleware(
        scope,
        empty_receive,
        capture_send,
    )

    return messages


@pytest.mark.anyio
async def test_rejects_missing_token() -> None:
    messages = await execute_request()

    assert messages[0]["status"] == 401


@pytest.mark.anyio
async def test_rejects_invalid_token() -> None:
    messages = await execute_request("Bearer token-errado")

    assert messages[0]["status"] == 401


@pytest.mark.anyio
async def test_accepts_valid_token() -> None:
    messages = await execute_request(f"Bearer {EXPECTED_TOKEN}")

    assert messages[0]["status"] == 200
    assert messages[1]["body"] == b"ok"
