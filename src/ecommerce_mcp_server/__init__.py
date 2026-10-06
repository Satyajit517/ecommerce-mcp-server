"""E-Commerce MCP Server Package."""

import os
from .auth import ECommerceTokenVerifier, authenticated_context
from .server import get_product, mcp, search_products


def main() -> None:
    """Run the FastMCP server with HTTP transport."""
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(transport="http", host=host, port=port)


__all__ = [
    "mcp",
    "main",
    "search_products",
    "get_product",
    "ECommerceTokenVerifier",
    "authenticated_context",
]
