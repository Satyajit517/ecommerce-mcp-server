"""E-Commerce MCP Server Package."""

from .server import get_product, mcp, search_products


def main() -> None:
    """Run the FastMCP server."""
    mcp.run()


__all__ = ["mcp", "main", "search_products", "get_product"]
