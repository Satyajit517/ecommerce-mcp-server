# E-Commerce MCP Server

Model Context Protocol (MCP) server providing AI clients with standardized, read-only access to product information in the e-commerce platform.

## Architecture

```text
MCP Client
    |
    | Model Context Protocol (stdio/SSE)
    v
FastMCP Server (ecommerce_mcp_server)
    |
    | REST (HTTP GET)
    v
Product Service (Microservice)
    |
    v
Product DB
```

```                         
                         ┌───────────────┐
                         │      User     │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │   MCP Client  │
                         │ Claude/etc.   │
                         └───────┬───────┘
                                 │
                            Access Token
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │       MCP Server       │
                    │                        │
                    │ Authentication         │
                    │ Authorization          │
                    │                        │
                    │ Tools                  │
                    │ ├─ searchProducts      │
                    │ ├─ getMyCart           │
                    │ ├─ getMyOrders         │
                    │ ├─ createOrder         │
                    │ └─ getPaymentStatus    │
                    └───────────┬────────────┘
                                │
                         REST / HTTP
                                │
                                ▼
                       ┌────────────────┐
                       │  API Gateway   │
                       └───────┬────────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
        User Service      Product Service    Order Service
                                                   │
                                          ┌────────┴────────┐
                                          ▼                 ▼
                                    Inventory Service  Payment Service
                                                          │
                                                          ▼
                                                       Razorpay
```

## Initial Phase 1 Tools

### 1. `search_products`
Search and filter products using the Product Service search endpoint (`GET /api/products/search`).

- **Parameters**:
  - `search` *(str, optional)*: Free-text search query across product name, brand, and description.
  - `categoryId` *(str, optional)*: Category UUID filter.
  - `minPrice` *(Decimal/number, optional)*: Minimum price filter (>= 0).
  - `maxPrice` *(Decimal/number, optional)*: Maximum price filter (>= 0, >= minPrice).
  - `brand` *(str, optional)*: Brand name filter.
  - `status` *(str, optional)*: Product status filter (e.g., `ACTIVE`).
  - `page` *(int, default=0)*: Page index (0-indexed).
  - `size` *(int, default=10)*: Page size (default 10, max 100).

### 2. `get_product`
Retrieve details of a specific product by its UUID (`GET /api/products/{id}`).

- **Parameters**:
  - `productId` *(str, required)*: Valid UUID of the product.

## Configuration

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| `PRODUCT_SERVICE_URL` | Base URL of the backend Product Service | `http://localhost:8082` |

## Running the Server

Using `uv` or Python:
```bash
# Run via module entrypoint
python main.py

# Or via installed console script
ecommerce-mcp-server
```

## Running Tests

Execute the automated test suite:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
