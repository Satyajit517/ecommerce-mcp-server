"""Client for communicating with the Product Service microservice."""

from __future__ import annotations

import os
from typing import Any, Optional

try:
    import httpx
except ImportError:
    import httpx2 as httpx  # type: ignore

from .models import (
    ProductItem,
    ProductSearchFilter,
    ProductSearchResult,
    validate_uuid,
)


class ProductServiceError(Exception):
    """Base exception for errors communicating with the Product Service."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class ProductNotFoundError(ProductServiceError):
    """Raised when a requested product does not exist (HTTP 404)."""


class ProductServiceUnavailableError(ProductServiceError):
    """Raised when the Product Service is unreachable, timed out, or returning 503."""


class ProductServiceClient:
    """REST client for the e-commerce Product Service microservice."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
        http_client: Optional[httpx.Client] = None,
    ):
        """Initialize the client.

        Args:
            base_url: Base URL of the Product Service (defaults to PRODUCT_SERVICE_URL env var or http://localhost:8082).
            timeout: Request timeout in seconds.
            http_client: Optional pre-configured httpx Client (useful for dependency injection and testing).
        """
        raw_url = base_url or os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8082")
        self.base_url = raw_url.rstrip("/")
        self.timeout = timeout
        self._custom_client = http_client

    def _get_client(self) -> httpx.Client:
        if self._custom_client is not None:
            return self._custom_client
        return httpx.Client(timeout=self.timeout)

    def _extract_error_message(self, response: httpx.Response) -> str:
        """Extract user-friendly error message from an HTTP error response."""
        try:
            data = response.json()
            if isinstance(data, dict):
                return (
                    data.get("message")
                    or data.get("error")
                    or data.get("detail")
                    or response.text
                )
        except Exception:
            pass
        return response.text or f"HTTP {response.status_code}"

    def get_product(self, product_id: str) -> ProductItem:
        """Retrieve details of a specific product by its UUID.

        Args:
            product_id: UUID of the product.

        Returns:
            ProductItem containing normalized product information.

        Raises:
            ValueError: If product_id is invalid.
            ProductNotFoundError: If product is not found (404).
            ProductServiceUnavailableError: If Product Service is down.
            ProductServiceError: On other HTTP/server errors.
        """
        valid_id = validate_uuid(product_id, "productId")
        url = f"{self.base_url}/api/products/{valid_id}"

        try:
            client = self._get_client()
            response = client.get(url)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProductServiceUnavailableError(
                f"Product Service is unavailable at {self.base_url}. Error: {exc}"
            ) from exc
        except Exception as exc:
            raise ProductServiceError(f"Unexpected error communicating with Product Service: {exc}") from exc

        if response.status_code == 404:
            err_msg = self._extract_error_message(response)
            raise ProductNotFoundError(f"Product not found with ID '{valid_id}': {err_msg}", status_code=404)

        if response.status_code >= 400:
            err_msg = self._extract_error_message(response)
            if response.status_code == 503:
                raise ProductServiceUnavailableError(f"Product Service unavailable: {err_msg}", status_code=503)
            raise ProductServiceError(
                f"Product Service request failed (HTTP {response.status_code}): {err_msg}",
                status_code=response.status_code,
            )

        data = response.json()
        # Unpack ApiResponse<T> if wrapped
        if isinstance(data, dict) and "data" in data and ("success" in data or "status" in data):
            data = data.get("data") or {}

        if not isinstance(data, dict):
            raise ProductServiceError("Invalid response format received from Product Service.")

        return ProductItem.from_api_data(data)

    def search_products(self, filter_criteria: ProductSearchFilter) -> ProductSearchResult:
        """Search and filter products using the Product Service search endpoint.

        Args:
            filter_criteria: Validated search and pagination parameters.

        Returns:
            ProductSearchResult containing matched products and pagination info.

        Raises:
            ProductServiceUnavailableError: If Product Service is down.
            ProductServiceError: On other HTTP/server errors.
        """
        url = f"{self.base_url}/api/products/search"
        params = filter_criteria.to_query_params()

        try:
            client = self._get_client()
            response = client.get(url, params=params)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProductServiceUnavailableError(
                f"Product Service is unavailable at {self.base_url}. Error: {exc}"
            ) from exc
        except Exception as exc:
            raise ProductServiceError(f"Unexpected error communicating with Product Service: {exc}") from exc

        if response.status_code >= 400:
            err_msg = self._extract_error_message(response)
            if response.status_code == 503:
                raise ProductServiceUnavailableError(f"Product Service unavailable: {err_msg}", status_code=503)
            raise ProductServiceError(
                f"Product search failed (HTTP {response.status_code}): {err_msg}",
                status_code=response.status_code,
            )

        data = response.json()
        # Unpack ApiResponse<PageResponse<T>> if wrapped
        if isinstance(data, dict) and "data" in data and ("success" in data or "status" in data):
            data = data.get("data") or {}

        # Handle Spring PageResponse structure
        items_raw: list[Any] = []
        total_elements = 0
        total_pages = 0
        is_last = True
        page_num = filter_criteria.page
        page_size = filter_criteria.size

        if isinstance(data, dict):
            if "content" in data and isinstance(data["content"], list):
                items_raw = data["content"]
            elif "items" in data and isinstance(data["items"], list):
                items_raw = data["items"]
            elif "products" in data and isinstance(data["products"], list):
                items_raw = data["products"]

            total_elements = data.get("totalElements") or data.get("total_elements") or len(items_raw)
            total_pages = data.get("totalPages") or data.get("total_pages") or (1 if items_raw else 0)
            page_num = data.get("pageNumber") or data.get("page_number") or data.get("page") or page_num
            page_size = data.get("pageSize") or data.get("page_size") or data.get("size") or page_size
            is_last = data.get("last") if "last" in data else data.get("isLast", (page_num + 1 >= total_pages))
        elif isinstance(data, list):
            items_raw = data
            total_elements = len(items_raw)
            total_pages = 1
            is_last = True

        products = [ProductItem.from_api_data(item) for item in items_raw if isinstance(item, dict)]

        return ProductSearchResult(
            products=products,
            page=int(page_num),
            size=int(page_size),
            totalElements=int(total_elements),
            totalPages=int(total_pages),
            isLast=bool(is_last),
        )
