import hmac
import json
from collections.abc import Awaitable, Callable
from typing import Any


Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


class BearerAuthMiddleware:
    def __init__(self, app: Callable, expected_token: str) -> None:
        self.app = app
        self.expected_token = expected_token

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }

        authorization = headers.get("authorization", "")
        scheme, separator, supplied_token = authorization.partition(" ")

        valid_token = (
            bool(separator)
            and scheme.lower() == "bearer"
            and hmac.compare_digest(supplied_token, self.expected_token)
        )

        if not valid_token:
            await self._send_unauthorized(send)
            return

        await self.app(scope, receive, send)

    async def _send_unauthorized(self, send: Send) -> None:
        body = json.dumps({"error": "unauthorized"}).encode("utf-8")

        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"cache-control", b"no-store"),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )