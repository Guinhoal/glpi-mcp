import contextlib
import os

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from app.auth import BearerAuthMiddleware

host = os.getenv("MCP_HOST", "127.0.0.1")
port = int(os.getenv("MCP_PORT", "8000"))
bearer_token = os.getenv("MCP_BEARER_TOKEN")

if not bearer_token:
    raise ValueError("MCP_BEARER_TOKEN não foi definido")

mcp = FastMCP(
    "GLPI MCP",
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
def server_status() -> dict[str, str]:
    """ "Verifica se o servidor esta funcionando."""
    return {
        "status": "ok",
        "server_status": "glip-mcp",
    }


async def health_check(request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "glpi-mcp"})


mcp_app = mcp.streamable_http_app()

protected_mcp_app = BearerAuthMiddleware(
    app=mcp_app,
    expected_token=bearer_token,
)


@contextlib.asynccontextmanager
async def lifespan(app: Starlette):
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[
        Route("/health", health_check, methods=["GET"]),
        Mount("/", app=protected_mcp_app),
    ],
    lifespan=lifespan,
)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=host,
        port=port,
    )
