"""Unit tests for ProductServiceClient."""

import unittest
from unittest.mock import MagicMock

try:
    import httpx
except ImportError:
    import httpx2 as httpx  # type: ignore

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
            base_url="http://test-product-service:8080",
            http_client=self.mock_http,
        )

    def test_get_product_success(self):
        product_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "data": {
                "productId": product_id,
                "name": "Mechanical Keyboard",
                "brand": "Keychron",
                "price": 99.50,
                "status": "ACTIVE",
            },
        }
        self.mock_http.get.return_value = mock_resp

        product = self.client.get_product(product_id)
        self.mock_http.get.assert_called_once_with(
            f"http://test-product-service:8080/api/products/{product_id}"
        )
        self.assertEqual(product.product_id, product_id)
        self.assertEqual(product.name, "Mechanical Keyboard")
        self.assertEqual(product.price, 99.50)

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

    def test_search_products_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "data": {
                "content": [
                    {
                        "productId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                        "name": "Wireless Mouse",
                        "price": 29.99,
                    }
                ],
                "pageNumber": 0,
                "pageSize": 10,
                "totalElements": 1,
                "totalPages": 1,
                "last": True,
            },
        }
        self.mock_http.get.return_value = mock_resp

        filter_criteria = ProductSearchFilter(search="mouse", page=0, size=10)
        result = self.client.search_products(filter_criteria)

        self.mock_http.get.assert_called_once_with(
            "http://test-product-service:8080/api/products/search",
            params={"page": 0, "size": 10, "search": "mouse"},
        )
        self.assertEqual(len(result.products), 1)
        self.assertEqual(result.products[0].name, "Wireless Mouse")
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
