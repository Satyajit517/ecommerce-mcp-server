"""Unit tests for data models and input validation."""

import unittest
from decimal import Decimal
from ecommerce_mcp_server.models import (
    CategorySummary,
    ProductItem,
    ProductSearchFilter,
    ProductSearchResult,
    validate_uuid,
)


class TestModels(unittest.TestCase):
    def test_validate_uuid_success(self):
        valid = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.assertEqual(validate_uuid(valid), valid)

    def test_validate_uuid_invalid(self):
        with self.assertRaises(ValueError):
            validate_uuid("invalid-uuid")
        with self.assertRaises(ValueError):
            validate_uuid("")

    def test_search_filter_defaults(self):
        filter_criteria = ProductSearchFilter()
        self.assertEqual(filter_criteria.page, 0)
        self.assertEqual(filter_criteria.size, 10)
        params = filter_criteria.to_query_params()
        self.assertEqual(params, {"page": 0, "size": 10})

    def test_search_filter_valid_params(self):
        cat_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        filter_criteria = ProductSearchFilter(
            search="phone",
            categoryId=cat_id,
            minPrice=Decimal("100.00"),
            maxPrice=Decimal("500.00"),
            brand="Samsung",
            status="ACTIVE",
            page=2,
            size=20,
        )
        params = filter_criteria.to_query_params()
        self.assertEqual(params["search"], "phone")
        self.assertEqual(params["categoryId"], cat_id)
        self.assertEqual(params["minPrice"], "100.00")
        self.assertEqual(params["maxPrice"], "500.00")
        self.assertEqual(params["brand"], "Samsung")
        self.assertEqual(params["status"], "ACTIVE")
        self.assertEqual(params["page"], 2)
        self.assertEqual(params["size"], 20)

    def test_search_filter_min_greater_than_max_raises(self):
        with self.assertRaises(ValueError):
            ProductSearchFilter(minPrice=Decimal("500.0"), maxPrice=Decimal("100.0"))

    def test_search_filter_invalid_category_uuid(self):
        with self.assertRaises(ValueError):
            ProductSearchFilter(categoryId="not-a-uuid")

    def test_search_filter_negative_page_or_size(self):
        with self.assertRaises(ValueError):
            ProductSearchFilter(page=-1)
        with self.assertRaises(ValueError):
            ProductSearchFilter(size=0)
        with self.assertRaises(ValueError):
            ProductSearchFilter(size=101)

    def test_product_item_from_api_data_with_decimal_price(self):
        api_data = {
            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "sellerId": "d3b07384-d113-4cd0-93cb-b7b51b75960d",
            "category": {
                "id": "4f9d2c88-1234-5678-90ab-cdef12345678",
                "name": "Smartphones",
                "code": "TECH-PHONE",
                "description": "Mobile phones and devices",
            },
            "productName": "Galaxy S24",
            "brand": "Samsung",
            "description": "Flagship smartphone",
            "price": "799.99",
            "sku": "SAM-S24",
            "status": "ACTIVE",
            "creationTimestamp": "2026-01-01T00:00:00Z",
            "updateTimestamp": "2026-01-02T00:00:00Z",
        }
        item = ProductItem.from_api_data(api_data)
        self.assertEqual(item.product_id, "3fa85f64-5717-4562-b3fc-2c963f66afa6")
        self.assertEqual(item.name, "Galaxy S24")
        self.assertIsInstance(item.price, Decimal)
        self.assertEqual(item.price, Decimal("799.99"))
        self.assertEqual(item.category_id, "4f9d2c88-1234-5678-90ab-cdef12345678")
        self.assertIsNotNone(item.category)
        self.assertEqual(item.category.name, "Smartphones")
        self.assertEqual(item.category.code, "TECH-PHONE")
        self.assertEqual(item.category.description, "Mobile phones and devices")
        self.assertEqual(item.status, "ACTIVE")

    def test_price_no_float_precision_loss(self):
        # 0.1 + 0.2 in binary float is 0.30000000000000004
        # Decimal ensures exact representation
        api_data = {
            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "name": "Micro-transaction item",
            "price": "0.30",
        }
        item = ProductItem.from_api_data(api_data)
        self.assertEqual(item.price, Decimal("0.30"))
        self.assertEqual(str(item.price), "0.30")


if __name__ == "__main__":
    unittest.main()
