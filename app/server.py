import contextlib
import os
import re
from time import perf_counter

import mariadb
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from app.auth import BearerAuthMiddleware
from app.database import database_connection, query_timeout
from app.sql_guard import validate_select

host = os.getenv("MCP_HOST", "127.0.0.1")
port = int(os.getenv("MCP_PORT", "8000"))
bearer_token = os.getenv("MCP_BEARER_TOKEN")

if not bearer_token:
    raise ValueError("MCP_BEARER_TOKEN não foi definido")

allowed_hosts = [
    item.strip()
    for item in os.getenv(
        "MCP_ALLOWED_HOSTS",
        "127.0.0.1:8000,localhost:8000",
    ).split(",")
    if item.strip()
]

allowed_origins = [
    item.strip()
    for item in os.getenv(
        "MCP_ALLOWED_ORIGINS",
        "http://127.0.0.1:6274,http://localhost:6274",
    ).split(",")
    if item.strip()
]

transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=allowed_hosts,
    allowed_origins=allowed_origins,
)

mcp = FastMCP(
    "GLPI MCP",
    host=host,
    port=port,
    stateless_http=True,
    json_response=True,
    transport_security=transport_security,
)

SQL_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")


def validate_table_name(table_name: str) -> str:
    normalized_name = table_name.strip()

    if not normalized_name:
        raise ValueError("O nome da tabela não pode estar vazio")

    if not SQL_IDENTIFIER_PATTERN.fullmatch(normalized_name):
        raise ValueError("O nome da tabela contém caracteres não permitidos")

    return normalized_name


@mcp.tool()
def server_status() -> dict[str, str]:
    """Verifica se o servidor esta funcionando."""
    return {
        "status": "ok",
        "server_status": "glpi-mcp",
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


@mcp.tool()
def describe_table(table_name: str) -> dict[str, object]:
    """Descreve colunas e índices de uma tabela do banco atual."""

    with database_connection() as connection:
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                SELECT
                    COLUMN_NAME,
                    COLUMN_TYPE,
                    IS_NULLABLE,
                    COLUMN_KEY,
                    COLUMN_DEFAULT,
                    EXTRA,
                    COLUMN_COMMENT
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
                """,
                (table_name,),
            )

            columns = [
                {
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2] == "YES",
                    "key": row[3] or None,
                    "default": row[4],
                    "extra": row[5] or None,
                    "comment": row[6] or None,
                }
                for row in cursor.fetchall()
            ]

            if not columns:
                return {
                    "found": False,
                    "table": table_name,
                    "error": "Tabela não encontrada no banco atual.",
                }

            cursor.execute(
                """
                SELECT
                    INDEX_NAME,
                    NON_UNIQUE,
                    SEQ_IN_INDEX,
                    COLUMN_NAME,
                    INDEX_TYPE
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = ?
                ORDER BY INDEX_NAME, SEQ_IN_INDEX
                """,
                (table_name,),
            )

            indexes = [
                {
                    "name": row[0],
                    "unique": row[1] == 0,
                    "position": row[2],
                    "column": row[3],
                    "type": row[4],
                }
                for row in cursor.fetchall()
            ]

            return {
                "found": True,
                "table": table_name,
                "column_count": len(columns),
                "columns": columns,
                "indexes": indexes,
            }
        finally:
            cursor.close()


@mcp.tool()
def search_columns(
    search: str,
    limit: int = 100,
) -> dict[str, object]:
    """Pesquisa colunas pelo nome em todas as tabelas do banco atual."""

    normalized_search = search.strip()

    if not normalized_search:
        return {
            "search": search,
            "count": 0,
            "columns": [],
            "error": "Informe um texto para pesquisar.",
        }

    bounded_limit = max(1, min(limit, 200))
    search_pattern = f"%{normalized_search}%"

    with database_connection() as connection:
        cursor = connection.cursor()

        try:
            cursor.execute(
                f"""
                SELECT
                    TABLE_NAME,
                    COLUMN_NAME,
                    COLUMN_TYPE,
                    IS_NULLABLE,
                    COLUMN_KEY,
                    COLUMN_COMMENT
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND COLUMN_NAME LIKE ?
                ORDER BY TABLE_NAME, ORDINAL_POSITION
                LIMIT {bounded_limit}
                """,
                (search_pattern,),
            )

            columns = [
                {
                    "table": row[0],
                    "name": row[1],
                    "type": row[2],
                    "nullable": row[3] == "YES",
                    "key": row[4] or None,
                    "comment": row[5] or None,
                }
                for row in cursor.fetchall()
            ]

            return {
                "search": normalized_search,
                "limit": bounded_limit,
                "count": len(columns),
                "columns": columns,
            }
        finally:
            cursor.close()


@mcp.tool()
def preview_table(
    table_name: str,
    limit: int = 10,
) -> dict[str, object]:
    """Retorna uma pequena amostra de registros de uma tabela."""

    try:
        safe_table_name = validate_table_name(table_name)
    except ValueError as error:
        return {
            "found": False,
            "table": table_name,
            "rows": [],
            "error": str(error),
        }

    bounded_limit = max(1, min(limit, 20))

    with database_connection() as connection:
        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = ?
                """,
                (safe_table_name,),
            )

            table_exists = cursor.fetchone()["COUNT(*)"] > 0

            if not table_exists:
                return {
                    "found": False,
                    "table": safe_table_name,
                    "rows": [],
                    "error": "Tabela não encontrada no banco atual.",
                }

            cursor.execute(
                f"""
                SELECT *
                FROM `{safe_table_name}`
                LIMIT {bounded_limit}
                """
            )

            rows = cursor.fetchall()

            return {
                "found": True,
                "table": safe_table_name,
                "limit": bounded_limit,
                "count": len(rows),
                "rows": rows,
            }
        finally:
            cursor.close()


@mcp.tool()
def explain_select(query: str) -> dict[str, object]:
    """Analisa o plano de uma consulta SELECT sem retornar seus registros."""

    try:
        safe_query = validate_select(query)
    except ValueError as error:
        return {
            "valid": False,
            "error": str(error),
            "plan": [],
        }

    with database_connection() as connection:
        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute(f"EXPLAIN {safe_query}")
            plan = cursor.fetchall()

            return {
                "valid": True,
                "plan": plan,
            }
        finally:
            cursor.close()


@mcp.tool()
def execute_select(
    query: str,
    max_rows: int = 400,
) -> dict[str, object]:
    """Executa uma consulta SELECT somente leitura com limites de tempo e linhas."""

    try:
        safe_query = validate_select(query)
    except ValueError as error:
        return {
            "success": False,
            "error": str(error),
            "rows": [],
        }

    bounded_max_rows = max(1, min(max_rows, 500))
    started_at = perf_counter()

    try:
        with database_connection() as connection:
            cursor = connection.cursor(dictionary=True)

            try:
                cursor.execute(
                    f"""
                    SET STATEMENT max_statement_time={query_timeout}
                    FOR {safe_query}
                    """
                )

                rows = cursor.fetchmany(bounded_max_rows + 1)
                truncated = len(rows) > bounded_max_rows

                if truncated:
                    rows = rows[:bounded_max_rows]

                elapsed_ms = round(
                    (perf_counter() - started_at) * 1000,
                    2,
                )

                return {
                    "success": True,
                    "row_count": len(rows),
                    "max_rows": bounded_max_rows,
                    "truncated": truncated,
                    "elapsed_ms": elapsed_ms,
                    "rows": rows,
                }
            finally:
                cursor.close()

    except mariadb.Error as error:
        elapsed_ms = round(
            (perf_counter() - started_at) * 1000,
            2,
        )

        return {
            "success": False,
            "error": str(error),
            "elapsed_ms": elapsed_ms,
            "rows": [],
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
