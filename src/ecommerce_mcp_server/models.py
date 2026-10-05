"""Data models and input validation for the E-Commerce MCP Server."""

from __future__ import annotations

import re
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


UUID_REGEX = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def validate_uuid(value: str, field_name: str = "id") -> str:
    """Validate that a string is a valid UUID."""
    if not value or not isinstance(value, str):
        raise ValueError(f"{field_name} must be a non-empty string.")
    cleaned = value.strip()
    if not UUID_REGEX.match(cleaned):
        try:
            uuid.UUID(cleaned)
        except (ValueError, AttributeError):
            raise ValueError(f"{field_name} must be a valid UUID format (e.g., '3fa85f64-5717-4562-b3fc-2c963f66afa6').")
    return cleaned


class CategorySummary(BaseModel):
    """Preserved category summary information from the Product Service."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: Optional[str] = Field(None, description="Category unique identifier (UUID).")
    name: Optional[str] = Field(None, description="Category display name.")
    code: Optional[str] = Field(None, description="Category code if available.")
    description: Optional[str] = Field(None, description="Category description if available.")


class ProductSearchFilter(BaseModel):
    """Validated input parameters for searching products."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    search: Optional[str] = Field(None, description="Free-text search query across product name, brand, and description.")
    category_id: Optional[str] = Field(None, alias="categoryId", description="Filter by category UUID.")
    min_price: Optional[Decimal] = Field(None, alias="minPrice", ge=Decimal("0.0"), description="Minimum price filter (>= 0).")
    max_price: Optional[Decimal] = Field(None, alias="maxPrice", ge=Decimal("0.0"), description="Maximum price filter (>= 0).")
    brand: Optional[str] = Field(None, description="Filter by product brand.")
    status: Optional[str] = Field(None, description="Filter by product status (e.g., ACTIVE).")
    page: int = Field(0, ge=0, description="Page index (0-indexed, default is 0).")
    size: int = Field(10, gt=0, le=100, description="Number of items per page (default is 10, max 100).")

    @field_validator("category_id")
    @classmethod
    def validate_category_uuid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            return validate_uuid(v, "categoryId")
        return None

    @model_validator(mode="after")
    def validate_price_range(self) -> ProductSearchFilter:
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError(
                    f"minPrice ({self.min_price}) cannot be greater than maxPrice ({self.max_price})."
                )
        return self

    def to_query_params(self) -> dict[str, Any]:
        """Convert non-None filter criteria into HTTP query parameters."""
        params: dict[str, Any] = {
            "page": self.page,
            "size": self.size,
        }
        if self.search:
            params["search"] = self.search
        if self.category_id:
            params["categoryId"] = self.category_id
        if self.min_price is not None:
            params["minPrice"] = str(self.min_price)
        if self.max_price is not None:
            params["maxPrice"] = str(self.max_price)
        if self.brand:
            params["brand"] = self.brand
        if self.status:
            params["status"] = self.status
        return params


class ProductItem(BaseModel):
    """Normalized product information representation for MCP clients."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    product_id: str = Field(..., alias="productId", description="Unique product UUID.")
    seller_id: Optional[str] = Field(None, alias="sellerId", description="Seller UUID.")
    category_id: Optional[str] = Field(None, alias="categoryId", description="Category UUID.")
    category: Optional[CategorySummary] = Field(None, description="Preserved category summary information.")
    name: str = Field(..., description="Product name.")
    brand: Optional[str] = Field(None, description="Brand name.")
    description: Optional[str] = Field(None, description="Product description.")
    price: Optional[Decimal] = Field(None, description="Product price as a decimal-safe value.")
    sku: Optional[str] = Field(None, description="Stock Keeping Unit code.")
    status: Optional[str] = Field(None, description="Product status (e.g. ACTIVE).")
    created_at: Optional[str] = Field(None, alias="createdAt", description="Creation timestamp.")
    updated_at: Optional[str] = Field(None, alias="updatedAt", description="Last update timestamp.")

    @classmethod
    def from_api_data(cls, data: dict[str, Any]) -> ProductItem:
        """Construct ProductItem from API response dictionary, handling naming variations and preserving category."""
        product_id = (
            data.get("productId")
            or data.get("id")
            or data.get("product_id")
            or ""
        )
        seller_id = (
            data.get("sellerId")
            or data.get("seller_id")
            or (data.get("seller") if isinstance(data.get("seller"), str) else None)
        )

        category_data = data.get("category")
        category_summary: Optional[CategorySummary] = None
        category_id = data.get("categoryId") or data.get("category_id")

        if isinstance(category_data, dict):
            cat_id = category_data.get("id") or category_data.get("categoryId") or category_id
            category_summary = CategorySummary(
                id=str(cat_id) if cat_id else None,
                name=category_data.get("name") or category_data.get("categoryName"),
                code=category_data.get("code"),
                description=category_data.get("description"),
            )
            if not category_id and cat_id:
                category_id = cat_id
        elif isinstance(category_data, str) and category_data.strip():
            category_summary = CategorySummary(name=category_data.strip())

        name = data.get("name") or data.get("productName") or data.get("title") or "Unnamed Product"
        brand = data.get("brand")
        description = data.get("description")

        # Decimal-safe price parsing (avoids binary floating-point inaccuracy)
        price_raw = data.get("price")
        price: Optional[Decimal] = None
        if price_raw is not None:
            try:
                price = Decimal(str(price_raw))
            except (InvalidOperation, TypeError, ValueError):
                price = None

        sku = data.get("sku")
        status = data.get("status")
        created_at = (
            data.get("createdAt")
            or data.get("created_at")
            or data.get("creationTimestamp")
            or data.get("createdDate")
        )
        updated_at = (
            data.get("updatedAt")
            or data.get("updated_at")
            or data.get("updateTimestamp")
            or data.get("lastModifiedDate")
        )

        return cls(
            productId=str(product_id),
            sellerId=str(seller_id) if seller_id is not None else None,
            categoryId=str(category_id) if category_id is not None else None,
            category=category_summary,
            name=name,
            brand=brand,
            description=description,
            price=price,
            sku=sku,
            status=status,
            createdAt=str(created_at) if created_at is not None else None,
            updatedAt=str(updated_at) if updated_at is not None else None,
        )


class ProductSearchResult(BaseModel):
    """Paginated search response for MCP clients."""
    model_config = ConfigDict(populate_by_name=True)

    products: list[ProductItem] = Field(default_factory=list, description="List of matched products.")
    page: int = Field(0, description="Current page index.")
    size: int = Field(10, description="Page size.")
    total_elements: int = Field(0, alias="totalElements", description="Total number of matched products.")
    total_pages: int = Field(0, alias="totalPages", description="Total number of available pages.")
    is_last: bool = Field(True, alias="isLast", description="Whether this is the last page.")
