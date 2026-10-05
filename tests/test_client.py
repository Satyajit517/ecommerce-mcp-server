"""Unit tests for ProductServiceClient."""

import unittest
from decimal import Decimal
from unittest.mock import MagicMock

import httpx

from ecommerce_mcp_server.client import (
    ProductNotFoundError,
    ProductServiceClient,
    ProductServiceError,
    ProductServiceUnavailableError,
)
from ecommerce_mcp_server.models import ProductSearchFilter


class TestProductServiceClient(unittest.TestCase):
    def setUp(self):
        self.mock_http = MagicMock()
        self.client = ProductServiceClient(
            base_url="http://test-product-service:8082",
            http_client=self.mock_http,
        )

    def test_client_lifecycle_and_context_manager(self):
        # Verify custom client is not closed automatically if injected
        with ProductServiceClient(http_client=self.mock_http) as client:
            self.assertEqual(client._client, self.mock_http)
        self.mock_http.close.assert_not_called()

        # Verify internal client is closed if owned
        real_client = ProductServiceClient()
        self.assertTrue(real_client._owns_client)
        self.assertFalse(real_client._client.is_closed)
        real_client.close()
        self.assertTrue(real_client._client.is_closed)

    def test_get_product_success(self):
        product_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "message": "Product retrieved successfully",
            "data": {
                "productId": product_id,
                "name": "Mechanical Keyboard",
                "brand": "Keychron",
                "price": "99.50",
                "category": {
                    "id": "4f9d2c88-1234-5678-90ab-cdef12345678",
                    "name": "Peripherals",
                },
                "status": "ACTIVE",
            },
            "timestamp": "2026-10-05T12:00:00Z",
        }
        self.mock_http.get.return_value = mock_resp

        product = self.client.get_product(product_id)
        self.mock_http.get.assert_called_once_with(
            f"http://test-product-service:8082/api/products/{product_id}"
        )
        self.assertEqual(product.product_id, product_id)
        self.assertEqual(product.name, "Mechanical Keyboard")
        self.assertEqual(product.price, Decimal("99.50"))
        self.assertIsNotNone(product.category)
        self.assertEqual(product.category.name, "Peripherals")

    def test_get_product_not_found(self):
        product_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"message": "Product does not exist"}
        self.mock_http.get.return_value = mock_resp

        with self.assertRaises(ProductNotFoundError) as ctx:
            self.client.get_product(product_id)
        self.assertIn("not found", str(ctx.exception).lower())

    def test_get_product_service_unavailable(self):
        product_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_http.get.side_effect = httpx.ConnectError("Connection refused")

        with self.assertRaises(ProductServiceUnavailableError):
            self.client.get_product(product_id)

    def test_search_products_success_unwraps_api_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "message": "Products retrieved successfully",
            "data": {
                "content": [
                    {
                        "productId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "name": "Wireless Mouse",
                        "price": "29.99",
                        "category": {"name": "Accessories"},
                    }
                ],
                "pageNumber": 0,
                "pageSize": 10,
                "totalElements": 1,
                "totalPages": 1,
                "last": True,
            },
            "timestamp": "2026-10-05T12:00:00Z",
        }
        self.mock_http.get.return_value = mock_resp

        filter_criteria = ProductSearchFilter(search="mouse", page=0, size=10)
        result = self.client.search_products(filter_criteria)

        self.mock_http.get.assert_called_once_with(
            "http://test-product-service:8082/api/products/search",
            params={"page": 0, "size": 10, "search": "mouse"},
        )
        self.assertEqual(len(result.products), 1)
        self.assertEqual(result.products[0].name, "Wireless Mouse")
        self.assertEqual(result.products[0].price, Decimal("29.99"))
        self.assertEqual(result.products[0].category.name, "Accessories")
        self.assertEqual(result.total_elements, 1)
        self.assertTrue(result.is_last)

    def test_search_products_server_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"message": "Internal Database Error"}
        self.mock_http.get.return_value = mock_resp

        filter_criteria = ProductSearchFilter()
        with self.assertRaises(ProductServiceError):
            self.client.search_products(filter_criteria)


if __name__ == "__main__":
    unittest.main()
