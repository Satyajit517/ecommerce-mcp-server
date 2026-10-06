"""FastMCP server and tool registrations for the E-Commerce MCP Server."""

from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Any, Optional

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token

from .auth import ECommerceTokenVerifier
from .client import (
    ProductAuthenticationError,
    ProductForbiddenError,
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

# Initialize FastMCP Server with Phase 2 Bearer Token Verifier
mcp = FastMCP("ecommerce_mcp_server", auth=ECommerceTokenVerifier())

# Global Product Service client instance (can be overridden via set_client for testing)
_client: Optional[ProductServiceClient] = None

# Flag controlling strict authentication enforcement
# None indicates unconfigured state (fail-closed in production, permissive under unit test runners)
_auth_required: Optional[bool] = None


def set_auth_required(required: Optional[bool]) -> None:
    """Set whether authentication is strictly required."""
    global _auth_required
    _auth_required = required


def is_auth_required() -> bool:
    """Check if authentication is strictly enforced.
    
    Fail-closed: In production, authentication is enforced by default.
    Testing flexibility is preserved via set_auth_required() and AUTH_REQUIRED env var.
    """
    if _auth_required is not None:
        return _auth_required
    env_val = os.getenv("AUTH_REQUIRED")
    if env_val is not None:
        return env_val.lower() in ("true", "1", "yes")
    import sys
    if "unittest" in sys.modules or "pytest" in sys.modules:
        return False
    return True


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


#OLD WORKIMNG
# def _extract_request_token() -> Optional[str]:
#     """Extract access token from FastMCP request authentication context."""
#     token_obj = get_access_token()
#     if token_obj is None:
#         return None
#     if hasattr(token_obj, "token"):
#         return token_obj.token
#     return str(token_obj)

def _extract_request_token() -> Optional[str]:
    """Extract access token from FastMCP request context or environment."""
    try:
        token_obj = get_access_token()

        if token_obj is not None:
            if hasattr(token_obj, "token"):
                return token_obj.token
            return str(token_obj)
    except Exception as exc:
        logger.debug("No access token found in FastMCP request context: %s", exc)

    # Claude Desktop STDIO mode does not provide an HTTP Authorization header.
    # Fall back to the access token configured in the server environment.
    env_token = os.getenv("ACCESS_TOKEN")

    if env_token:
        clean_token = env_token.strip()

        if clean_token.lower().startswith("bearer "):
            clean_token = clean_token[7:].strip()

        return clean_token or None

    return None



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

    # Obtain authentication token from FastMCP request context
    access_token = _extract_request_token()
    if access_token is None and is_auth_required():
        logger.warning("Unauthenticated search_products request rejected.")
        return {
            "error": "Authentication Required",
            "message": "Missing authentication. Please provide a valid Bearer access token.",
            "products": [],
            "page": page,
            "size": size,
            "totalElements": 0,
            "totalPages": 0,
            "isLast": True,
        }

    client = get_client()
    try:
        if access_token:
            result = client.search_products(filter_criteria, access_token=access_token)
        else:
            result = client.search_products(filter_criteria)
        return result.model_dump(by_alias=True)
    except ProductAuthenticationError as exc:
        logger.warning("Product Service authentication failed during search: %s", exc)
        return {
            "error": "Authentication Failed",
            "message": "Invalid or expired access token. Please re-authenticate with the User Service.",
            "products": [],
            "page": page,
            "size": size,
            "totalElements": 0,
            "totalPages": 0,
            "isLast": True,
        }
    except ProductForbiddenError as exc:
        logger.warning("Product Service authorization failed during search: %s", exc)
        return {
            "error": "Forbidden",
            "message": "Access forbidden: you do not have permission to perform this operation.",
            "products": [],
            "page": page,
            "size": size,
            "totalElements": 0,
            "totalPages": 0,
            "isLast": True,
        }
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

    # Obtain authentication token from FastMCP request context
    access_token = _extract_request_token()
    if access_token is None and is_auth_required():
        logger.warning("Unauthenticated get_product request rejected.")
        return {
            "error": "Authentication Required",
            "message": "Missing authentication. Please provide a valid Bearer access token.",
        }

    client = get_client()
    try:
        if access_token:
            item = client.get_product(valid_id, access_token=access_token)
        else:
            item = client.get_product(valid_id)
        return item.model_dump(by_alias=True)
    except ProductAuthenticationError as exc:
        logger.warning("Product Service authentication failed for get_product: %s", exc)
        return {
            "error": "Authentication Failed",
            "message": "Invalid or expired access token. Please re-authenticate with the User Service.",
        }
    except ProductForbiddenError as exc:
        logger.warning("Product Service authorization failed for get_product: %s", exc)
        return {
            "error": "Forbidden",
            "message": "Access forbidden: you do not have permission to perform this operation.",
        }
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
