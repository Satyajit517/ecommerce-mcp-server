"""Unit tests for FastMCP server tools and error translation."""

import inspect
import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from ecommerce_mcp_server.client import (
    ProductNotFoundError,
    ProductServiceError,
    ProductServiceUnavailableError,
)
from ecommerce_mcp_server.models import CategorySummary, ProductItem, ProductSearchResult
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
        self.assertEqual(len(tool_names), 2)
        self.assertIn("search_products", tool_names)
        self.assertIn("get_product", tool_names)

    def test_get_product_parameter_schema(self):
        # Verify get_product only exposes productId as a required parameter
        sig = inspect.signature(get_product)
        params = list(sig.parameters.keys())
        self.assertEqual(params, ["productId"])
        self.assertEqual(sig.parameters["productId"].default, inspect.Parameter.empty)
        # Verify product_id alias is NOT exposed
        self.assertNotIn("product_id", params)

    def test_search_products_parameter_schema(self):
        # Verify search_products only exposes the approved public parameters
        sig = inspect.signature(search_products)
        params = list(sig.parameters.keys())
        expected_params = [
            "search",
            "categoryId",
            "minPrice",
            "maxPrice",
            "brand",
            "status",
            "page",
            "size",
        ]
        self.assertEqual(params, expected_params)
        # Verify snake_case aliases are NOT exposed
        self.assertNotIn("category_id", params)
        self.assertNotIn("min_price", params)
        self.assertNotIn("max_price", params)

    def test_get_product_success(self):
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_client.get_product.return_value = ProductItem(
            productId=valid_id,
            name="Gaming Monitor",
            brand="Dell",
            price=Decimal("349.99"),
            category=CategorySummary(id="cat-1", name="Displays"),
            status="ACTIVE",
        )

        res = get_product(productId=valid_id)
        self.assertEqual(res["productId"], valid_id)
        self.assertEqual(res["name"], "Gaming Monitor")
        self.assertEqual(res["price"], Decimal("349.99"))
        self.assertIn("category", res)
        self.assertEqual(res["category"]["name"], "Displays")
        self.mock_client.get_product.assert_called_once_with(valid_id)

    def test_get_product_invalid_uuid(self):
        res = get_product(productId="not-valid-uuid")
        self.assertEqual(res["error"], "Validation Error")
        self.assertIn("valid UUID format", res["message"])
        self.mock_client.get_product.assert_not_called()

    def test_get_product_blank_id(self):
        res = get_product(productId="   ")
        self.assertEqual(res["error"], "Validation Error")
        self.mock_client.get_product.assert_not_called()

    def test_get_product_not_found_handled_gracefully(self):
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_client.get_product.side_effect = ProductNotFoundError("Not found", 404)

        res = get_product(productId=valid_id)
        self.assertEqual(res["error"], "Not Found")
        self.assertIn("was not found", res["message"])
        self.assertNotIn("details", res)

    def test_get_product_service_down_handled_gracefully_no_internal_details(self):
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_client.get_product.side_effect = ProductServiceUnavailableError(
            "Connection refused to http://internal-cluster:8082/db"
        )

        res = get_product(productId=valid_id)
        self.assertEqual(res["error"], "Product Service Unavailable")
        self.assertEqual(
            res["message"],
            "Product Service is currently unreachable. Please try again later.",
        )
        # Ensure sensitive connection details and URLs are NOT exposed
        self.assertNotIn("details", res)
        self.assertNotIn("internal-cluster", str(res))

    def test_get_product_server_error_no_internal_details(self):
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_client.get_product.side_effect = ProductServiceError(
            "Raw SQL syntax error at line 42", status_code=500
        )

        res = get_product(productId=valid_id)
        self.assertEqual(res["error"], "Product Service Error")
        self.assertNotIn("SQL", res["message"])
        self.assertNotIn("details", res)

    def test_search_products_success(self):
        self.mock_client.search_products.return_value = ProductSearchResult(
            products=[
                ProductItem(
                    productId="3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    name="Coffee Maker",
                    brand="Philips",
                    price=Decimal("49.99"),
                    category=CategorySummary(name="Kitchen Appliances"),
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
        self.assertEqual(res["products"][0]["price"], Decimal("49.99"))
        self.assertEqual(res["products"][0]["category"]["name"], "Kitchen Appliances")
        self.assertEqual(res["totalElements"], 1)
        self.assertTrue(res["isLast"])

    def test_search_products_validation_error(self):
        # minPrice > maxPrice
        res = search_products(minPrice=Decimal("500.00"), maxPrice=Decimal("100.00"))
        self.assertEqual(res["error"], "Validation Error")
        self.assertIn("cannot be greater than maxPrice", res["message"])
        self.mock_client.search_products.assert_not_called()

    def test_search_products_invalid_category_id(self):
        res = search_products(categoryId="invalid-uuid")
        self.assertEqual(res["error"], "Validation Error")
        self.mock_client.search_products.assert_not_called()

    def test_search_products_service_unavailable_no_internal_details(self):
        self.mock_client.search_products.side_effect = ProductServiceUnavailableError(
            "ConnectError to http://internal-cluster:8082"
        )

        res = search_products(search="laptop")
        self.assertEqual(res["error"], "Product Service Unavailable")
        self.assertEqual(
            res["message"],
            "Product Service is currently unreachable. Please try again later.",
        )
        self.assertNotIn("details", res)
        self.assertNotIn("internal-cluster", str(res))
        self.assertEqual(res["products"], [])


if __name__ == "__main__":
    unittest.main()
