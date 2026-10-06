# MCP Integration Specification

## 1. Overview

### 1.1 Purpose

The e-commerce platform shall provide an MCP (Model Context Protocol) server that allows MCP-compatible AI clients to interact with selected capabilities of the e-commerce application through standardized MCP tools.

The MCP server will act as an integration layer between an AI client and the existing e-commerce microservices.

The MCP server shall not replace the existing REST APIs or duplicate business logic implemented within the microservices.

### 1.2 Initial Objective

The initial implementation shall provide AI clients with read-only access to product information.

The first release shall expose the following MCP tools:

* `search_products`

* `get_product`

These tools shall internally communicate with the existing Product Service.

### 1.3 Scope

#### In Scope

* MCP server creation

* MCP protocol integration

* Product search tool

* Product details tool

* Communication between MCP Server and Product Service

* Input validation

* MCP-level error handling

* Initial authentication design

* Initial authorization design

* Security boundaries

* Specification-driven implementation and testing

#### Out of Scope

The following are explicitly excluded from the initial implementation:

* API Gateway integration

* Payment Service integration

* Razorpay integration

* Cart modification tools

* Order creation/modification tools

* Inventory modification tools

* Seller product-management tools

* Administrative tools

* Advanced OAuth/token-exchange architecture

These capabilities may be introduced in future MCP releases.

---

# 2. Existing System Context

The current e-commerce platform contains multiple microservices.

The initial MCP implementation will communicate directly with the Product Service.

```text

                    MCP Client

                        |

                        | MCP

                        v

                 +--------------+

                 | MCP Server   |

                 +------+-------+

                        |

                        | HTTP / REST

                        v

                 +--------------+

                 | Product      |

                 | Service      |

                 +------+-------+

                        |

                        v

                 +--------------+

                 | Product DB   |

                 +--------------+

```

API Gateway is not currently part of this flow because it has not yet been implemented.

Payment Service is also outside the current MCP scope.

---

# 3. Architectural Principles

The MCP implementation shall follow these principles.

## 3.1 MCP as an Adapter

The MCP Server shall act as an adapter between AI clients and existing application capabilities.

It shall not become a replacement for the Product Service.

```text

MCP Client

     |

     v

MCP Server

     |

     v

Product Service

     |

     v

Repository

```

## 3.2 No Business Logic Duplication

Business rules shall remain within the respective microservice.

The MCP Server shall not directly access the Product Service database.

The MCP Server shall not implement product search logic itself.

For example, the MCP Server shall not independently implement:

* Product filtering

* Product persistence

* Seller ownership rules

* Product status rules

* Category validation

These responsibilities remain with the Product Service.

## 3.3 Existing REST APIs Remain the Source of Business Operations

The existing Product Service REST APIs shall continue to be used.

The MCP tools will translate AI tool requests into calls to these APIs.

---

# 4. Initial MCP Tools

The first release shall contain two tools.

## 4.1 `search_products`

### Purpose

Search and filter products using the existing Product Service search functionality.

### Existing REST Endpoint

```http

GET /api/products/search

```

### Existing Supported Parameters

The current Product Service accepts:

\| Parameter    | Type          | Required |

\| ------------ | ------------- | -------- |

\| `search`     | String        | No       |

\| `categoryId` | UUID          | No       |

\| `minPrice`   | BigDecimal    | No       |

\| `maxPrice`   | BigDecimal    | No       |

\| `brand`      | String        | No       |

\| `status`     | ProductStatus | No       |

\| `page`       | Integer       | No       |

\| `size`       | Integer       | No       |

The Product Service currently defaults the page size to 10.

### MCP Tool Input

The MCP tool shall expose equivalent search parameters.

Conceptually:

```json

{

  "search": "laptop",

  "categoryId": "uuid",

  "minPrice": 50000,

  "maxPrice": 100000,

  "brand": "Dell",

  "status": "ACTIVE",

  "page": 0,

  "size": 10

}

```

All filtering parameters shall remain optional.

### MCP Tool Behavior

The MCP Server shall:

1\. Validate the supplied tool arguments.

2\. Construct a request to the Product Service.

3\. Call:

```http

GET /api/products/search

```

4\. Receive the existing `ApiResponse<PageResponse<ProductResponse>>`.

5\. Convert the response into an MCP-compatible tool result.

6\. Return the product information to the MCP client.

### Product Information

The result may contain:

* Product ID

* Seller ID

* Category

* Product name

* Brand

* Description

* Price

* SKU

* Status

* Creation timestamp

* Update timestamp

The MCP response representation shall be finalized during the technical design phase.

---

# 5. `get_product`

## Purpose

Retrieve details of a specific product.

### Existing REST Endpoint

```http

GET /api/products/{id}

```

### MCP Tool Input

```json

{

  "productId": "product-uuid"

}

```

### Required Input

`productId` is required.

### MCP Tool Behavior

The MCP Server shall:

1\. Validate the supplied product ID.

2\. Call the Product Service:

```http

GET /api/products/{id}

```

3\. Receive the existing `ApiResponse<ProductResponse>`.

4\. Convert the response into an MCP-compatible tool result.

5\. Return the product information to the MCP client.

---

# 6. Product Service Contract

The MCP implementation shall use the existing Product Service contract rather than introducing a second Product API.

The current Product Service already provides:

```text

GET /api/products/{id}

GET /api/products

GET /api/products/search

GET /api/products/ids

```

Only the following will initially be consumed by MCP:

```text

GET /api/products/{id}

GET /api/products/search

```

The following are not part of the initial MCP implementation:

```text

POST   /api/products

PUT    /api/products/{id}

DELETE /api/products/{id}

GET    /api/products/ids

```

---

# 7. Authentication

Authentication shall be treated as a separate concern from MCP tool execution.

The MCP Server shall eventually authenticate the caller before executing protected operations.

The current e-commerce application uses JWT-based authentication.

The initial MCP architecture shall therefore be designed to support Bearer-token authentication.

Conceptually:

```text

MCP Client

     |

     | Authorization: Bearer <access-token>

     v

MCP Server

     |

     v

Authentication

     |

     v

MCP Tool

```

The exact token validation mechanism shall be finalized during the authentication design phase.

The MCP Server shall not trust user identity values supplied as arbitrary tool parameters.

For example, future tools such as:

```text

get_my_orders()

get_my_cart()

```

shall derive the user identity from the authenticated security context rather than accepting:

```json

{

  "userId": "..."

}

```

from the AI client.

---

# 8. Authorization

Authentication answers:

> Who is making the request?

Authorization answers:

> What is that user allowed to do?

The MCP implementation shall maintain this distinction.

The underlying Product Service remains responsible for business-level authorization.

For example, the existing Product Service contains:

```java

@PreAuthorize("hasRole('SELLER')")

```

for:

* Product creation

* Product update

* Product deletion

The initial MCP release does not expose these operations.

If seller operations are exposed through MCP in the future, the MCP Server shall perform appropriate authorization checks and the Product Service shall continue enforcing its own authorization rules.

The MCP Server shall not be considered a replacement for service-level authorization.

---

# 9. Security Requirements

## 9.1 No Direct Database Access

The MCP Server shall never access the Product Service database directly.

## 9.2 No User Identity Supplied by the LLM

The MCP Server shall not trust user IDs supplied by an AI model for user-specific operations.

## 9.3 Business Authorization Remains in Microservices

The Product Service shall remain the final authority for Product Service business rules and authorization.

## 9.4 Input Validation

All MCP tool arguments shall be validated before being converted into Product Service requests.

## 9.5 Sensitive Operations

Write operations shall not be exposed through MCP until authentication and authorization requirements have been explicitly specified.

---

# 10. Error Handling

The MCP Server shall translate failures from the Product Service into meaningful MCP tool errors.

The existing Product Service already defines application-level errors such as:

* `ResourceNotFoundException`

* `ConflictException`

* `ForbiddenException`

The MCP layer shall not silently hide these failures.

### Example

If a product does not exist:

```text

MCP Client

    |

    | get_product(productId)

    v

MCP Server

    |

    v

Product Service

    |

    X Product not found

    |

    v

MCP Tool Error

```

The exact MCP error representation will be defined during technical design.

---

# 11. Response Handling

The existing Product Service uses:

```java

ApiResponse<T>

```

and for paginated results:

```java

ApiResponse<PageResponse<T>>

```

The MCP Server shall consume these existing responses.

The MCP layer may transform them into a format optimized for MCP clients, but it shall not modify the underlying Product Service API.

For example:

```text

Product Service

      |

      v

ApiResponse<PageResponse<ProductResponse>>

      |

      v

MCP Adapter

      |

      v

MCP Tool Result

```

The transformation rules shall be defined during implementation design.

---

# 12. Pagination

The Product Service currently uses Spring's `Pageable`.

The MCP `search_products` tool shall expose pagination explicitly.

Initial parameters:

```text

page

size

```

Default behavior shall remain consistent with the Product Service:

```text

size = 10

```

The MCP Server shall not request unlimited product results.

---

# 13. Product Search Filters

The MCP search tool shall initially support the same filtering capabilities as `ProductSearchRequest`:

```text

search

categoryId

minPrice

maxPrice

brand

status

```

The MCP Server shall not introduce additional search semantics that are not supported by the Product Service.

Future enhancements may introduce AI-oriented search capabilities, but those shall be specified separately.

---

# 14. Tool Responsibility Boundary

The MCP Server is responsible for:

```text

MCP protocol

Tool definitions

Tool input validation

Authentication integration

Authorization integration

Microservice communication

Response transformation

Error translation

```

The Product Service is responsible for:

```text

Product business logic

Product persistence

Product filtering

Product validation

Seller ownership

Product authorization

Product status

Category relationship

```

---

# 15. Non-Functional Requirements

## 15.1 Maintainability

The MCP implementation shall be modular so that new tools can be added without modifying existing tools unnecessarily.

## 15.2 Separation of Concerns

MCP protocol handling, authentication, service communication, and business logic shall remain separated.

## 15.3 Extensibility

The architecture shall support future tools for:

```text

Cart

Order

Inventory

Payment

User

```

without requiring a redesign of the MCP foundation.

## 15.4 Security

MCP shall not provide a mechanism to bypass the security controls of the existing microservices.

## 15.5 Failure Handling

A failure in the Product Service shall be represented as a controlled MCP tool failure rather than causing an uncontrolled MCP server failure.

---

# 16. Future MCP Tools

The following tools are planned but are outside the initial implementation.

### Cart

```text

get_my_cart

add_to_cart

update_cart_item

remove_from_cart

clear_cart

```

### Orders

```text

get_my_orders

get_order

create_order

cancel_order

```

### Inventory

```text

check_stock

check_product_availability

```

### Payment

```text

create_payment

get_payment_status

```

Payment-related tools shall only be implemented after the Payment Service and Razorpay integration are available.

### Seller

Potential future tools:

```text

create_product

update_product

delete_product

```

These require explicit role-based authorization.

---

# 17. API Gateway Consideration

API Gateway is currently not implemented.

Therefore, the initial MCP implementation shall communicate directly with the Product Service.

Current:

```text

MCP Server

     |

     v

Product Service

```

Future:

```text

MCP Server

     |

     v

API Gateway

     |

     v

Product Service

```

The introduction of an API Gateway shall be handled as a future architectural change and shall not be assumed by the initial MCP implementation.

---

# 18. Payment Service Consideration

Payment Service and Razorpay integration are currently outside the MCP implementation scope.

The architecture shall nevertheless remain extensible enough to support future payment tools.

No payment-specific implementation shall be introduced during the initial MCP phase.

---

# 19. Initial Implementation Phases

## Phase 1 — Specification

* Define MCP architecture

* Define tool contracts

* Define security requirements

* Define authentication requirements

* Define error behavior

## Phase 2 — MCP Foundation

* Create MCP Server

* Configure MCP SDK

* Configure application properties

* Establish MCP communication

* Implement basic health/connectivity behavior

## Phase 3 — Product Tools

Implement:

```text

search_products

get_product

```

## Phase 4 — Product Service Integration

Connect MCP Server to the existing Product Service.

## Phase 5 — Authentication

Integrate the existing JWT authentication model.

## Phase 6 — Authorization

Introduce role/scope-based access control where required.

## Phase 7 — Testing

Test:

* Successful tool execution

* Invalid input

* Product not found

* Product Service unavailable

* Authentication failure

* Authorization failure

* Pagination

* Search filters

## Phase 8 — Future Expansion

After the initial implementation is stable:

```text

Cart

  ↓

Order

  ↓

Inventory

  ↓

Payment

  ↓

Advanced MCP Authorization

```

---

# 20. Specification Acceptance Criteria

The initial MCP implementation shall be considered complete when:

* An MCP-compatible client can discover the available product tools.

* `search_products` can search products through the existing Product Service.

* `get_product` can retrieve an existing product.

* Product Service business logic remains unchanged.

* MCP does not directly access the Product database.

* Product Service errors are represented as controlled MCP errors.

* Pagination works correctly.

* Existing Product search filters work correctly.

* Authentication requirements are defined before protected tools are introduced.

* The MCP implementation does not depend on the API Gateway.

* The MCP implementation does not depend on the Payment Service.

* The implementation can be extended with additional MCP tools without redesigning the MCP foundation.

---

# 21. Source of Truth

The following existing Product Service components are the source of truth for the initial MCP Product integration:

```text

ProductController

ProductService

ProductServiceImpl

ProductCreateRequest

ProductUpdateRequest

ProductSearchRequest

ProductResponse

ProductInfoResponse

ProductSummaryResponse

ApiResponse

PageResponse

```

The MCP implementation shall adapt these existing contracts rather than introducing duplicate Product business APIs.

---

# 22. Architectural Design — Phase 2 Authentication

## 22.1 Objective

Phase 2 integrates the existing e-commerce JWT authentication model with the MCP architecture.

The MCP Server reuses the existing access token generated by the User Service rather than introducing a separate authentication system.

The Product Service remains responsible for validating the JWT and enforcing its existing security rules.

The architectural goal is:

```text
                         +------------------+
                         |   User Service   |
                         |                  |
                         | /api/auth/login  |
                         +--------+---------+
                                  |
                                  | accessToken
                                  v
                         +------------------+
                         |    MCP Client    |
                         +--------+---------+
                                  |
                                  | Authenticated MCP request
                                  | carrying existing access token
                                  v
                         +------------------+
                         |     FastMCP      |
                         |      Server      |
                         +--------+---------+
                                  |
                                  | HTTP / REST
                                  | Authorization:
                                  | Bearer <same-access-token>
                                  v
                         +------------------+
                         | Product Service  |
                         |                  |
                         | JWT validation   |
                         | Authorization    |
                         | Product logic    |
                         +--------+---------+
                                  |
                                  v
                         +------------------+
                         |   Product DB     |
                         +------------------+
```

## 22.2 Authentication Flow

The authentication flow is:

```text
1. User
   |
   | POST /api/auth/login
   v
2. User Service
   |
   | AuthResponse
   | - accessToken
   | - user
   v
3. MCP Client
   |
   | Authenticated MCP request
   | using the existing access token
   v
4. FastMCP Server
   |
   | Obtain authentication context
   | and access token
   v
5. Product Service
   |
   | Authorization: Bearer <same-access-token>
   v
6. JwtAuthenticationFilter
   |
   | Validate access token
   | establish SecurityContext
   v
7. Product Controller / Service
   |
   v
8. Product response
```

The MCP Server shall not generate a new JWT.

The MCP Server shall not request or store the user's password.

The MCP Server shall not create a second user identity system.

## 22.3 Existing JWT as the Downstream Credential

The existing User Service access token contains the application's established JWT claims:

```text
sub          = user email
userId       = authenticated user UUID
role         = BUYER / SELLER / ADMIN
type         = access
issuedAt     = token issue time
expiration   = token expiration time
```

The MCP Server treats the access token as an opaque credential for downstream propagation.

The MCP Server shall not modify the token or create a replacement token.

The Product Service remains responsible for authoritative JWT validation.

## 22.4 Two Authentication Boundaries

The architecture contains two distinct authentication boundaries.

### Boundary 1 — MCP Client → FastMCP

The MCP Client must establish an authenticated MCP request using the user's existing access-token authentication context.

The exact FastMCP mechanism for receiving and extracting the token shall be finalized during implementation design based on the FastMCP version and transport being used.

The access token shall not be introduced as a normal business/tool argument such as:

```json
{
  "productId": "...",
  "accessToken": "..."
}
```

Authentication metadata belongs to the protocol/security layer, not to the `get_product` or `search_products` tool contract.

### Boundary 2 — FastMCP → Product Service

When FastMCP calls a protected Product Service endpoint, it shall forward the same access token:

```http
Authorization: Bearer <existing-access-token>
```

The Product Service's existing `JwtAuthenticationFilter` shall validate the token and establish the authenticated Spring Security context.

## 22.5 Authentication vs Authorization

Authentication and authorization remain separate responsibilities.

```text
Authentication
    |
    | Who is the user?
    v
Existing JWT / Product Service security

Authorization
    |
    | What is the user allowed to do?
    v
Product Service security + business rules
```

The MCP Server is not a replacement for microservice-level authorization.

The Product Service remains the final authority for Product Service access control.

Existing rules such as:

```java
@PreAuthorize("hasRole('SELLER')")
```

remain unchanged.

## 22.6 Refresh Token Handling

The refresh token shall not be forwarded to the Product Service.

The existing authentication design uses the refresh token for obtaining a new access token through:

```http
POST /api/auth/refresh
```

The refresh token remains part of the existing HttpOnly cookie mechanism.

For Product Service calls, the MCP architecture uses only the access token:

```text
Access Token
    |
    +---- MCP authentication context
    |
    +---- Product Service Authorization header

Refresh Token
    |
    +---- User Service refresh flow only
```

Phase 2 shall not introduce refresh-token handling inside Product Service calls.

## 22.7 Tool Identity Rules

Authentication identity shall never be supplied as an arbitrary AI tool parameter.

For example, future tools shall not depend on:

```json
{
  "userId": "some-user-id"
}
```

to determine the current user.

Instead, user identity shall be derived from the authenticated security context.

The AI model must not be trusted to select another user's identity.

## 22.8 Product Tool Flow

The existing Phase 1 tools remain:

```text
search_products
get_product
```

Their business inputs remain unchanged.

Example:

```text
MCP Client
    |
    | search_products(search="laptop")
    | + authenticated context
    v
FastMCP
    |
    | GET /api/products/search
    | Authorization: Bearer <JWT>
    v
Product Service
    |
    v
Product search
```

For product details:

```text
MCP Client
    |
    | get_product(productId)
    | + authenticated context
    v
FastMCP
    |
    | GET /api/products/{id}
    | Authorization: Bearer <JWT>
    v
Product Service
```

## 22.9 Error Flow

Authentication-related failures shall be represented as controlled MCP failures.

The architecture shall distinguish at least:

```text
Missing authentication
        |
        v
401 / authentication failure

Invalid or expired access token
        |
        v
401 / authentication failure

Authenticated but not authorized
        |
        v
403 / authorization failure

Product Service unavailable
        |
        v
Service availability failure
```

Internal JWT details, secrets, stack traces, and sensitive implementation information shall not be exposed to the MCP Client.

## 22.10 Security Boundaries

The Phase 2 architecture explicitly prevents the following:

```text
MCP Server
    X generate JWT
    X store passwords
    X access User database
    X access Product database directly
    X trust LLM-supplied userId
    X forward refresh token to Product Service
    X bypass Product Service authorization
```

Instead:

```text
User Service
    |
    +--> creates authentication tokens

MCP Server
    |
    +--> propagates authentication context

Product Service
    |
    +--> validates access token
    +--> establishes authenticated user
    +--> enforces authorization
    +--> executes product operation
```

## 22.11 Responsibility Matrix

| Component | Responsibility |
|---|---|
| User Service | Login, registration, access-token generation, refresh-token lifecycle |
| MCP Client | Initiates MCP requests with the authenticated security context |
| FastMCP Server | Exposes MCP tools and propagates the access token to Product Service |
| Product Service | JWT validation, Spring Security context, authorization and product business logic |
| Product Database | Product persistence; accessed only by Product Service |

## 22.12 Architectural Constraints

Phase 2 shall preserve the following constraints:

1. Existing User Service authentication remains the source of truth.
2. Existing Product Service authentication remains unchanged.
3. MCP remains an adapter layer.
4. MCP does not directly access any microservice database.
5. MCP does not duplicate Product Service business logic.
6. MCP does not generate or sign JWTs.
7. Refresh tokens are not used as Product Service credentials.
8. Authentication credentials are not exposed as normal MCP tool parameters.
9. User identity is derived from authenticated context rather than LLM-supplied identifiers.
10. API Gateway is not required for this architecture.
11. Payment/Razorpay remains outside this phase.
12. Cart, Order, Inventory, and administrative write operations remain outside this phase.

## 22.13 Architecture Decision

The selected Phase 2 architecture is:

```text
                         +------------------+
                         |   User Service   |
                         |                  |
                         | /api/auth/login  |
                         +--------+---------+
                                  |
                                  | accessToken
                                  v
                         +------------------+
                         |    MCP Client    |
                         +--------+---------+
                                  |
                                  | Authenticated MCP request
                                  v
                         +------------------+
                         |     FastMCP      |
                         |      Server      |
                         +--------+---------+
                                  |
                                  | HTTP / REST
                                  | Authorization:
                                  | Bearer <same JWT>
                                  v
                         +------------------+
                         | Product Service  |
                         |                  |
                         | JWT validation   |
                         | Authorization    |
                         | Product logic    |
                         +--------+---------+
                                  |
                                  v
                         +------------------+
                         |   Product DB     |
                         +------------------+
```

This architecture keeps authentication centralized in the existing e-commerce security model while allowing MCP to act as a secure AI-facing adapter.

The exact FastMCP authentication-context extraction mechanism shall be finalized before implementation and shall not alter the architectural responsibilities defined above.

