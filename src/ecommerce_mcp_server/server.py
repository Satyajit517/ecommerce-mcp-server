"""FastMCP server and tool registrations for the E-Commerce MCP Server."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

from fastmcp import FastMCP

from .client import (
    ProductNotFoundError,
    ProductServiceClient,
    ProductServiceError,
    ProductServiceUnavailableError,
)
from .models import (
    ProductSearchFilter,
    validate_uuid,
)

logger = logging.getLogger("ecommerce_mcp_server")

# Initialize FastMCP Server
mcp = FastMCP("ecommerce_mcp_server")

# Global Product Service client instance (can be overridden via set_client for testing)
_client: Optional[ProductServiceClient] = None


def get_client() -> ProductServiceClient:
    """Return the active ProductServiceClient instance."""
    global _client
    if _client is None:
        _client = ProductServiceClient()
    return _client


def set_client(client: Optional[ProductServiceClient]) -> None:
    """Set or override the ProductServiceClient instance (useful for unit testing)."""
    global _client
    if _client is not None and _client != client:
        _client.close()
    _client = client


@mcp.tool()
def search_products(
    search: Optional[str] = None,
    categoryId: Optional[str] = None,
    minPrice: Optional[Decimal] = None,
    maxPrice: Optional[Decimal] = None,
    brand: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 0,
    size: int = 10,
) -> dict[str, Any]:
    """Search and filter products using the existing Product Service.

    All filtering parameters are optional. Results are paginated with a default size of 10.

    Args:
        search: Free-text search keyword across product name, brand, and description.
        categoryId: Filter by category UUID (e.g., '3fa85f64-5717-4562-b3fc-2c963f66afa6').
        minPrice: Minimum product price filter (must be >= 0).
        maxPrice: Maximum product price filter (must be >= 0 and >= minPrice).
        brand: Filter by brand name (e.g., 'Apple', 'Dell').
        status: Filter by product status (e.g., 'ACTIVE').
        page: Page index (0-indexed, default is 0).
        size: Number of items per page (default is 10, max 100).

    Returns:
        A dictionary containing the list of products and pagination details:
        {
            "products": [...],
            "page": 0,
            "size": 10,
            "totalElements": 100,
            "totalPages": 10,
            "isLast": false
        }
    """
    try:
        filter_criteria = ProductSearchFilter(
            search=search,
            categoryId=categoryId,
            minPrice=minPrice,
            maxPrice=maxPrice,
            brand=brand,
            status=status,
            page=page,
            size=size,
        )
    except Exception as exc:
        logger.warning("Input validation failed for search_products: %s", exc)
        return {
            "error": "Validation Error",
            "message": str(exc),
            "products": [],
            "page": page,
            "size": size,
            "totalElements": 0,
            "totalPages": 0,
            "isLast": True,
        }

    client = get_client()
    try:
        result = client.search_products(filter_criteria)
        return result.model_dump(by_alias=True)
    except ProductServiceUnavailableError as exc:
        logger.error("Product Service unavailable during search: %s", exc)
        return {
            "error": "Product Service Unavailable",
            "message": "Product Service is currently unreachable. Please try again later.",
            "products": [],
            "page": page,
            "size": size,
            "totalElements": 0,
            "totalPages": 0,
            "isLast": True,
        }
    except ProductServiceError as exc:
        logger.error("Product Service error during search: %s", exc)
        return {
            "error": "Product Service Error",
            "message": "Product Service request failed. Please check your query or try again later.",
            "products": [],
            "page": page,
            "size": size,
            "totalElements": 0,
            "totalPages": 0,
            "isLast": True,
        }


@mcp.tool()
def get_product(
    productId: str,
) -> dict[str, Any]:
    """Retrieve details of a specific product by its unique UUID.

    Args:
        productId: The UUID of the product to retrieve (required).

    Returns:
        A dictionary containing the product details:
        {
            "productId": "...",
            "sellerId": "...",
            "categoryId": "...",
            "category": {"id": "...", "name": "..."},
            "name": "...",
            "brand": "...",
            "description": "...",
            "price": "299.99",
            "sku": "...",
            "status": "ACTIVE",
            "createdAt": "...",
            "updatedAt": "..."
        }
    """
    if not productId or not isinstance(productId, str) or not productId.strip():
        return {
            "error": "Validation Error",
            "message": "Missing required parameter 'productId'.",
        }

    try:
        valid_id = validate_uuid(productId, "productId")
    except ValueError as exc:
        logger.warning("Input validation failed for get_product: %s", exc)
        return {
            "error": "Validation Error",
            "message": str(exc),
        }

    client = get_client()
    try:
        item = client.get_product(valid_id)
        return item.model_dump(by_alias=True)
    except ProductNotFoundError as exc:
        logger.info("Product not found: %s", exc)
        return {
            "error": "Not Found",
            "message": f"Product with ID '{valid_id}' was not found.",
        }
    except ProductServiceUnavailableError as exc:
        logger.error("Product Service unavailable: %s", exc)
        return {
            "error": "Product Service Unavailable",
            "message": "Product Service is currently unreachable. Please try again later.",
        }
    except ProductServiceError as exc:
        logger.error("Product Service error: %s", exc)
        return {
            "error": "Product Service Error",
            "message": "Product Service request failed. Please check your query or try again later.",
        }
