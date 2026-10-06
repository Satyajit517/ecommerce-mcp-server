"""Unit and integration tests for Phase 2 MCP Authentication and Security."""

import asyncio
import base64
import inspect
import os
import time
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

import jwt

from ecommerce_mcp_server.auth import ECommerceTokenVerifier, authenticated_context
from ecommerce_mcp_server.client import (
    ProductAuthenticationError,
    ProductForbiddenError,
    ProductNotFoundError,
    ProductServiceClient,
    ProductServiceError,
    ProductServiceUnavailableError,
)
from ecommerce_mcp_server.models import (
    CategorySummary,
    ProductItem,
    ProductSearchFilter,
    ProductSearchResult,
)
from ecommerce_mcp_server.server import (
    get_product,
    search_products,
    set_auth_required,
    set_client,
)


class TestAuth(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        set_client(self.mock_client)
        set_auth_required(True)  # Strictly enforce authentication for Phase 2 tests

        # Secret configured in User Service application.properties (Base64-encoded)
        # security.jwt.secret= HUf8w4fuehf8w3hfehvHFuehfhrO9D2nceui0D4hc74Y48d3883H9SaYmA738RH0FE8Y
        self.secret = "HUf8w4fuehf8w3hfehvHFuehfhrO9D2nceui0D4hc74Y48d3883H9SaYmA738RH0FE8Y"
        self.key_bytes = base64.b64decode(self.secret.strip())
        self.now = int(time.time())
        self.valid_claims = {
            "sub": "user@example.com",
            "userId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "role": "BUYER",
            "type": "access",
            "iat": self.now,
            "exp": self.now + 3600,
        }
        # Tokens are signed using HS384 matching the User Service JwtService configuration
        self.valid_token = jwt.encode(self.valid_claims, self.key_bytes, algorithm="HS384")

    def tearDown(self):
        set_client(None)
        set_auth_required(None)

    def test_token_verifier_valid_token(self):
        """Test that a valid JWT signed with the correct secret and HS384 is accepted."""
        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        access_token = asyncio.run(verifier.verify_token(self.valid_token))
        self.assertIsNotNone(access_token)
        self.assertEqual(access_token.token, self.valid_token)
        self.assertEqual(access_token.client_id, "user@example.com")
        self.assertEqual(access_token.scopes, ["BUYER"])
        self.assertEqual(access_token.claims["userId"], "3fa85f64-5717-4562-b3fc-2c963f66afa6")

    def test_token_verifier_rejects_incorrect_secret(self):
        """Test that a JWT signed with an incorrect secret is rejected."""
        wrong_key = b"wrong-secret-key-that-is-at-least-48-bytes-long-1234567890123456"
        wrong_token = jwt.encode(self.valid_claims, wrong_key, algorithm="HS384")

        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        access_token = asyncio.run(verifier.verify_token(wrong_token))
        self.assertIsNone(access_token)

    def test_token_verifier_rejects_modified_signature(self):
        """Test that a JWT with a modified/tampered signature is rejected."""
        parts = self.valid_token.split(".")
        # Tamper with the signature bytes in the 3rd segment
        tampered_sig = parts[2][:-4] + ("AAAA" if parts[2][-4:] != "AAAA" else "BBBB")
        tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        access_token = asyncio.run(verifier.verify_token(tampered_token))
        self.assertIsNone(access_token)

    def test_token_verifier_rejects_modified_claims(self):
        """Test that a JWT with modified claims without a recomputed signature is rejected."""
        parts = self.valid_token.split(".")
        tampered_payload = base64.urlsafe_b64encode(
            b'{"sub":"hacker@evil.com","userId":"3fa85f64-5717-4562-b3fc-2c963f66afa6","role":"ADMIN","type":"access"}'
        ).decode().rstrip("=")
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        access_token = asyncio.run(verifier.verify_token(tampered_token))
        self.assertIsNone(access_token)

    def test_token_verifier_expired_token(self):
        """Test that an expired JWT is rejected."""
        expired_claims = dict(self.valid_claims, exp=self.now - 60)
        expired_token = jwt.encode(expired_claims, self.key_bytes, algorithm="HS384")

        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        access_token = asyncio.run(verifier.verify_token(expired_token))
        self.assertIsNone(access_token)

    def test_token_verifier_rejects_refresh_token(self):
        """Test that a refresh JWT is rejected from access-token authorization."""
        refresh_claims = dict(self.valid_claims, type="refresh")
        refresh_token = jwt.encode(refresh_claims, self.key_bytes, algorithm="HS384")

        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        access_token = asyncio.run(verifier.verify_token(refresh_token))
        self.assertIsNone(access_token)

    def test_token_verifier_rejects_invalid_base64_secret(self):
        """Verify that an invalid Base64 JWT secret fails closed and is NOT converted to UTF-8 bytes."""
        # A 48+ byte string that is invalid Base64 (contains spaces and exclamation points)
        invalid_b64_secret = "This is definitely not valid base64 key string!!! 1234567890abcdefghijklmnopqrstuvwxyz"
        verifier = ECommerceTokenVerifier(secret_key=invalid_b64_secret)
        self.assertIsNone(verifier.secret_bytes)

        # Even if a token was signed with the UTF-8 bytes of this invalid string,
        # the verifier must NOT accept it (proves no raw UTF-8 fallback occurred).
        token_signed_with_utf8 = jwt.encode(
            self.valid_claims,
            invalid_b64_secret.encode("utf-8"),
            algorithm="HS384",
        )
        access_token = asyncio.run(verifier.verify_token(token_signed_with_utf8))
        self.assertIsNone(access_token)

    def test_token_verifier_rejects_base64_secret_too_short(self):
        """Verify that a valid Base64 secret that decodes to less than 48 bytes fails closed."""
        # 32 bytes encoded in Base64 (valid for HS256, but too short for HS384)
        short_bytes = b"01234567890123456789012345678901"  # 32 bytes
        short_b64 = base64.b64encode(short_bytes).decode("ascii")
        verifier = ECommerceTokenVerifier(secret_key=short_b64)
        self.assertIsNone(verifier.secret_bytes)

    def test_token_verifier_rejects_missing_type_claim(self):
        """Test that a correctly signed, non-expired HS384 JWT with no type claim is rejected."""
        claims_no_type = {
            "sub": "user@example.com",
            "userId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "role": "BUYER",
            "iat": self.now,
            "exp": self.now + 3600,
        }
        token_no_type = jwt.encode(claims_no_type, self.key_bytes, algorithm="HS384")

        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        access_token = asyncio.run(verifier.verify_token(token_no_type))
        self.assertIsNone(access_token)

    def test_token_verifier_rejects_invalid_token_type_something(self):
        """Test that a token with type='something' is rejected."""
        something_claims = dict(self.valid_claims, type="something")
        something_token = jwt.encode(something_claims, self.key_bytes, algorithm="HS384")

        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        access_token = asyncio.run(verifier.verify_token(something_token))
        self.assertIsNone(access_token)

    def test_token_verifier_rejects_uppercase_access_type(self):
        """Test that type='ACCESS' (wrong case) is rejected; only exact lowercase 'access' is accepted."""
        uppercase_claims = dict(self.valid_claims, type="ACCESS")
        uppercase_token = jwt.encode(uppercase_claims, self.key_bytes, algorithm="HS384")

        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        access_token = asyncio.run(verifier.verify_token(uppercase_token))
        self.assertIsNone(access_token)

        # Confirm exact lowercase 'access' is accepted
        exact_claims = dict(self.valid_claims, type="access")
        exact_token = jwt.encode(exact_claims, self.key_bytes, algorithm="HS384")
        access_token = asyncio.run(verifier.verify_token(exact_token))
        self.assertIsNotNone(access_token)

    def test_token_verifier_fails_closed_when_jwt_secret_missing(self):
        """Test that authentication fails closed when JWT_SECRET is missing."""
        with patch.dict(os.environ, {}, clear=True):
            verifier = ECommerceTokenVerifier(secret_key=None)
            self.assertIsNone(verifier.secret_bytes)

            with patch("jwt.decode") as mock_jwt_decode:
                access_token = asyncio.run(verifier.verify_token(self.valid_token))
                self.assertIsNone(access_token)
                # Ensure jwt.decode is NEVER called when secret is missing (fails closed immediately)
                mock_jwt_decode.assert_not_called()

    def test_token_verifier_rejects_unsigned_jwt(self):
        """Test that an unsigned JWT (alg=none) is rejected."""
        header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').decode().rstrip("=")
        payload = base64.urlsafe_b64encode(b'{"sub":"user@example.com","type":"access"}').decode().rstrip("=")
        unsigned_token = f"{header}.{payload}."

        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        access_token = asyncio.run(verifier.verify_token(unsigned_token))
        self.assertIsNone(access_token)

    def test_token_verifier_rejects_unsupported_algorithms(self):
        """Test that JWTs signed with algorithms other than HS384 are strictly rejected."""
        # Sign with HS256 using a 32-byte key
        hs256_key = b"12345678901234567890123456789012"
        hs256_token = jwt.encode(self.valid_claims, hs256_key, algorithm="HS256")

        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        access_token = asyncio.run(verifier.verify_token(hs256_token))
        self.assertIsNone(access_token)

    def test_token_verifier_never_falls_back_to_verify_signature_false(self):
        """Explicitly test that the verifier always sets verify_signature=True and never False."""
        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        real_decode = jwt.decode

        def spy_decode(*args, **kwargs):
            options = kwargs.get("options", {})
            self.assertTrue(options.get("verify_signature", True))
            self.assertNotEqual(options.get("verify_signature"), False)
            return real_decode(*args, **kwargs)

        with patch("jwt.decode", side_effect=spy_decode) as mock_decode:
            access_token = asyncio.run(verifier.verify_token(self.valid_token))
            self.assertIsNotNone(access_token)
            self.assertEqual(mock_decode.call_count, 1)

    def test_token_verifier_rejects_malformed_token(self):
        """Test that non-JWT or empty strings are rejected."""
        verifier = ECommerceTokenVerifier(secret_key=self.secret)
        self.assertIsNone(asyncio.run(verifier.verify_token("invalid-string")))
        self.assertIsNone(asyncio.run(verifier.verify_token("")))

    def test_get_product_authenticated_success(self):
        """Test get_product returns data when authenticated context is present."""
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_client.get_product.return_value = ProductItem(
            productId=valid_id,
            name="Wireless Headphones",
            brand="Bose",
            price=Decimal("199.99"),
            category=CategorySummary(id="cat-1", name="Audio"),
            status="ACTIVE",
        )

        with authenticated_context(self.valid_token):
            res = get_product(productId=valid_id)

        self.assertEqual(res["productId"], valid_id)
        self.assertEqual(res["name"], "Wireless Headphones")
        self.assertEqual(res["price"], Decimal("199.99"))
        self.mock_client.get_product.assert_called_once_with(valid_id, access_token=self.valid_token)

    def test_search_products_authenticated_success(self):
        """Test search_products returns items when authenticated context is present."""
        self.mock_client.search_products.return_value = ProductSearchResult(
            products=[
                ProductItem(
                    productId="3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    name="Wireless Headphones",
                    price=Decimal("199.99"),
                    status="ACTIVE",
                )
            ],
            page=0,
            size=10,
            totalElements=1,
            totalPages=1,
            isLast=True,
        )

        with authenticated_context(self.valid_token):
            res = search_products(search="Headphones", brand="Bose")

        self.assertEqual(len(res["products"]), 1)
        self.assertEqual(res["products"][0]["name"], "Wireless Headphones")
        self.assertEqual(self.mock_client.search_products.call_count, 1)
        _, kwargs = self.mock_client.search_products.call_args
        self.assertEqual(kwargs.get("access_token"), self.valid_token)

    def test_get_product_missing_authentication(self):
        """Test get_product rejects request when unauthenticated."""
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        res = get_product(productId=valid_id)

        self.assertEqual(res["error"], "Authentication Required")
        self.assertIn("Missing authentication", res["message"])
        self.mock_client.get_product.assert_not_called()

    def test_search_products_missing_authentication(self):
        """Test search_products rejects request when unauthenticated."""
        res = search_products(search="Laptop")

        self.assertEqual(res["error"], "Authentication Required")
        self.assertIn("Missing authentication", res["message"])
        self.assertEqual(res["products"], [])
        self.mock_client.search_products.assert_not_called()

    def test_token_propagation_to_product_service_client(self):
        """Test that ProductServiceClient sends the Authorization: Bearer header downstream."""
        mock_http = MagicMock()
        client = ProductServiceClient(
            base_url="http://test-product-service:8082",
            http_client=mock_http,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "success": True,
            "data": {
                "productId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "name": "Tablet",
                "price": "499.00",
            },
        }
        mock_http.get.return_value = mock_resp

        # Test get_product forwards Authorization header
        product = client.get_product(
            "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            access_token=self.valid_token,
        )
        mock_http.get.assert_called_with(
            "http://test-product-service:8082/api/products/3fa85f64-5717-4562-b3fc-2c963f66afa6",
            headers={"Authorization": f"Bearer {self.valid_token}"},
        )
        self.assertEqual(product.name, "Tablet")

        # Test search_products forwards Authorization header
        filter_criteria = ProductSearchFilter(search="tablet")
        client.search_products(filter_criteria, access_token=self.valid_token)
        mock_http.get.assert_called_with(
            "http://test-product-service:8082/api/products/search",
            params={"page": 0, "size": 10, "search": "tablet"},
            headers={"Authorization": f"Bearer {self.valid_token}"},
        )

    def test_product_service_401_error_handling(self):
        """Test controlled handling of Product Service HTTP 401."""
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_client.get_product.side_effect = ProductAuthenticationError(
            "Product Service rejected invalid JWT", status_code=401
        )

        with authenticated_context("invalid-or-expired-token"):
            res = get_product(productId=valid_id)

        self.assertEqual(res["error"], "Authentication Failed")
        self.assertIn("Invalid or expired access token", res["message"])
        self.assertNotIn("invalid-or-expired-token", str(res))

    def test_product_service_403_forbidden_handling(self):
        """Test controlled handling of Product Service HTTP 403."""
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_client.get_product.side_effect = ProductForbiddenError(
            "User does not have required SELLER role", status_code=403
        )

        with authenticated_context(self.valid_token):
            res = get_product(productId=valid_id)

        self.assertEqual(res["error"], "Forbidden")
        self.assertIn("Access forbidden", res["message"])
        self.assertNotIn(self.valid_token, str(res))

    def test_security_token_not_in_tool_schemas(self):
        """Verify access_token is never in the public MCP tool parameter schemas."""
        sig_get = inspect.signature(get_product)
        self.assertEqual(list(sig_get.parameters.keys()), ["productId"])
        self.assertNotIn("accessToken", sig_get.parameters)
        self.assertNotIn("access_token", sig_get.parameters)

        sig_search = inspect.signature(search_products)
        self.assertNotIn("accessToken", sig_search.parameters)
        self.assertNotIn("access_token", sig_search.parameters)

    def test_security_token_not_in_tool_output_or_errors(self):
        """Verify access_token is never leaked in successful output or error payloads."""
        valid_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        self.mock_client.get_product.return_value = ProductItem(
            productId=valid_id,
            name="Secure Item",
            price=Decimal("10.00"),
        )

        with authenticated_context(self.valid_token):
            res = get_product(productId=valid_id)

        self.assertNotIn(self.valid_token, str(res))
        self.assertNotIn("Authorization", str(res))


if __name__ == "__main__":
    unittest.main()
