import os
from mcp.server.fastmcp import FastMCP

host =  os.getenv("MCP_HOST", "127.0.0.1")
port = int(os.getenv("MCP_PORT", "8000"))

mcp = FastMCP(
    "GLPI MCP",
    host = host,
    port=port,
)

@mcp.tool()
def server_status() -> dict[str, str]:
    """"Verifica se o servidor esta funcionando."""
    return {
        "status": "ok",
        "server_status": "glip-mcp",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")