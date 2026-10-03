"""Unit tests for FastMCP server tools and error translation."""

import unittest
from unittest.mock import MagicMock

from ecommerce_mcp_server.client import (
    ProductNotFoundError,
    ProductServiceUnavailableError,
)
from ecommerce_mcp_server.models import ProductItem, ProductSearchResult
from ecommerce_mcp_server.server import (
    get_product,
    mcp,
    search_products,
    set_client,
)


class TestServerTools(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        set_client(self.mock_client)

    def tearDown(self):
        set_client(None)

    def test_mcp_server_tools_registered(self):
        import asyncio
        tools = asyncio.run(mcp.list_tools())
        tool_names = [tool.name for tool in tools]
        self.assertIn("search_products", tool_names)
        self.assertIn("get_product", tool_names)

    def test_get_product_success(self):
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_client.get_product.return_value = ProductItem(
            productId=valid_id,
            name="Gaming Monitor",
            brand="Dell",
            price=349.99,
            status="ACTIVE",
        )

        res = get_product(productId=valid_id)
        self.assertEqual(res["productId"], valid_id)
        self.assertEqual(res["name"], "Gaming Monitor")
        self.assertEqual(res["price"], 349.99)
        self.mock_client.get_product.assert_called_once_with(valid_id)

    def test_get_product_alias_compatibility(self):
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_client.get_product.return_value = ProductItem(
            productId=valid_id,
            name="Gaming Monitor",
            price=349.99,
        )

        res = get_product(product_id=valid_id)
        self.assertEqual(res["productId"], valid_id)

    def test_get_product_missing_id(self):
        res = get_product()
        self.assertEqual(res["error"], "Validation Error")
        self.assertIn("Missing required parameter", res["message"])

    def test_get_product_invalid_uuid(self):
        res = get_product(productId="not-valid-uuid")
        self.assertEqual(res["error"], "Validation Error")
        self.assertIn("valid UUID format", res["message"])

    def test_get_product_not_found_handled_gracefully(self):
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_client.get_product.side_effect = ProductNotFoundError("Not found", 404)

        res = get_product(productId=valid_id)
        self.assertEqual(res["error"], "Not Found")
        self.assertIn("was not found", res["message"])

    def test_get_product_service_down_handled_gracefully(self):
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_client.get_product.side_effect = ProductServiceUnavailableError("Down")

        res = get_product(productId=valid_id)
        self.assertEqual(res["error"], "Product Service Unavailable")
        self.assertIn("unreachable", res["message"])

    def test_search_products_success(self):
        self.mock_client.search_products.return_value = ProductSearchResult(
            products=[
                ProductItem(
                    productId="3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    name="Coffee Maker",
                    brand="Philips",
                    price=49.99,
                    status="ACTIVE",
                )
            ],
            page=0,
            size=10,
            totalElements=1,
            totalPages=1,
            isLast=True,
        )

        res = search_products(search="Coffee", brand="Philips")
        self.assertEqual(len(res["products"]), 1)
        self.assertEqual(res["products"][0]["name"], "Coffee Maker")
        self.assertEqual(res["totalElements"], 1)
        self.assertTrue(res["isLast"])

    def test_search_products_validation_error(self):
        # minPrice > maxPrice
        res = search_products(minPrice=500.0, maxPrice=100.0)
        self.assertEqual(res["error"], "Validation Error")
        self.assertIn("cannot be greater than maxPrice", res["message"])

    def test_search_products_service_unavailable(self):
        self.mock_client.search_products.side_effect = ProductServiceUnavailableError("Down")

        res = search_products(search="laptop")
        self.assertEqual(res["error"], "Product Service Unavailable")
        self.assertEqual(res["products"], [])


if __name__ == "__main__":
    unittest.main()
