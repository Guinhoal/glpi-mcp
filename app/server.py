import contextlib
import os

import mariadb
import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from app.auth import BearerAuthMiddleware
from app.database import database_connection

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
    """Verifica se o servidor esta funcionando."""
    return {
        "status": "ok",
        "server_status": "glip-mcp",
    }


@mcp.tool()
def database_status() -> dict[str, str | int | bool]:
    """Verifica a conexão somente leitura com o banco MariaDB do GLPI"""

    try:
        with database_connection() as connection:
            cursor = connection.cursor()

            try:
                cursor.execute(
                    """
                    SELECT
                        DATABASE(),
                        VERSION(),
                        CURRENT_USER()
                    """
                )

                database, version, current_user = cursor.fetchone()

                return {
                    "connected": True,
                    "database": database,
                    "version": version,
                    "current_user": current_user,
                }
            finally:
                cursor.close()
    except mariadb.Error as error:
        return {
            "connected": False,
            "error": str(error),
        }


@mcp.tool()
def search_tables(
    search: str = "",
    limit: int = 100,
) -> dict[str, object]:
    """Pesquisa tabelas do banco atual pelo nome ou comentário."""

    bounded_limit = max(1, min(limit, 250))
    search_pattern = f"%{search}%"

    with database_connection() as connection:
        cursor = connection.cursor()

        try:
            cursor.execute(
                f"""
                SELECT
                    TABLE_NAME,
                    TABLE_TYPE,
                    ENGINE,
                    TABLE_ROWS,
                    TABLE_COMMENT
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND (
                      TABLE_NAME LIKE ?
                      OR TABLE_COMMENT LIKE ?
                  )
                ORDER BY TABLE_NAME
                LIMIT {bounded_limit}
                """,
                (search_pattern, search_pattern),
            )

            tables = [
                {
                    "name": row[0],
                    "type": row[1],
                    "engine": row[2],
                    "estimated_rows": row[3],
                    "comment": row[4],
                }
                for row in cursor.fetchall()
            ]

            return {
                "search": search,
                "limit": bounded_limit,
                "count": len(tables),
                "tables": tables,
            }
        finally:
            cursor.close()


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
