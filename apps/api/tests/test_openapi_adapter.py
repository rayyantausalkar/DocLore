from doclore_api.ingestion.openapi import OpenAPIAdapter
from doclore_api.models import Source, SourceType

SAMPLE_OPENAPI_YAML = """openapi: 3.0.3
info:
  title: Order Processing Service
  version: 1.2.0
  description: Service managing customer orders and payment authorizations.
paths:
  /api/v1/orders:
    post:
      summary: Create a customer order
      operationId: createOrder
      security:
        - BearerAuth:
            - write:orders
      parameters:
        - name: X-Idempotency-Key
          in: header
          required: true
          description: Unique client key to guarantee idempotent creation
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateOrderRequest'
      responses:
        '201':
          description: Order created successfully
        '401':
          description: Missing or expired bearer authorization token
        '403':
          description: Insufficient scope write:orders
components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: Bearer token containing user roles and permissions
  schemas:
    CreateOrderRequest:
      type: object
      required:
        - customer_id
        - amount_cents
      properties:
        customer_id:
          type: string
          description: Unique customer identifier
        amount_cents:
          type: integer
          description: Total order charge in cents
"""

SAMPLE_OPENAPI_JSON = """{
  "openapi": "3.0.0",
  "info": {
    "title": "Auth Gateway",
    "version": "2.0.0"
  },
  "paths": {
    "/oauth/v2/token": {
      "post": {
        "summary": "Exchange credentials for JWT access token",
        "operationId": "exchangeToken",
        "parameters": [
          {
            "name": "grant_type",
            "in": "query",
            "required": true,
            "description": "Must be client_credentials or refresh_token"
          }
        ],
        "responses": {
          "200": { "description": "Token granted" },
          "400": { "description": "Invalid grant parameters" }
        }
      }
    }
  }
}"""


def test_openapi_adapter_parses_yaml_with_structural_provenance() -> None:
    source = Source(
        id="src-spec-yaml",
        project_id="proj-1",
        name="Order Spec",
        source_type=SourceType.OPENAPI,
    )

    adapter = OpenAPIAdapter()
    docs = adapter.parse(
        source=source,
        content=SAMPLE_OPENAPI_YAML,
        canonical_path="specs/order-service.yaml",
        revision="rev-yaml-1",
    )

    assert len(docs) == 1
    doc = docs[0]
    assert doc.title == "Order Processing Service"
    assert doc.canonical_path == "specs/order-service.yaml"
    assert len(doc.chunks) >= 3

    # 1. Verify Operation chunk
    op_chunks = [c for c in doc.chunks if "paths./api/v1/orders.post" in c.provenance.section_path]
    assert len(op_chunks) == 1
    op_chunk = op_chunks[0]
    assert "POST /api/v1/orders" in op_chunk.text
    assert "X-Idempotency-Key" in op_chunk.text
    assert "write:orders" in op_chunk.text
    assert "Status 401" in op_chunk.text
    assert op_chunk.provenance.start_line is not None
    assert op_chunk.provenance.end_line >= op_chunk.provenance.start_line

    # 2. Verify Security Scheme chunk
    sec_chunks = [c for c in doc.chunks if "components.securitySchemes.BearerAuth" in c.provenance.section_path]
    assert len(sec_chunks) == 1
    sec_chunk = sec_chunks[0]
    assert "BearerAuth" in sec_chunk.text
    assert "bearer" in sec_chunk.text
    assert "JWT" in sec_chunk.text

    # 3. Verify Model Schema chunk
    schema_chunks = [c for c in doc.chunks if "components.schemas.CreateOrderRequest" in c.provenance.section_path]
    assert len(schema_chunks) == 1
    schema_chunk = schema_chunks[0]
    assert "customer_id" in schema_chunk.text
    assert "amount_cents" in schema_chunk.text


def test_openapi_adapter_parses_json_spec() -> None:
    source = Source(
        id="src-spec-json",
        project_id="proj-1",
        name="Auth Gateway Spec",
        source_type=SourceType.OPENAPI,
    )

    adapter = OpenAPIAdapter()
    docs = adapter.parse(
        source=source,
        content=SAMPLE_OPENAPI_JSON,
        canonical_path="specs/auth-gateway.json",
        revision="rev-json-1",
    )

    assert len(docs) == 1
    doc = docs[0]
    assert doc.title == "Auth Gateway"
    assert len(doc.chunks) >= 2

    token_chunks = [c for c in doc.chunks if "/oauth/v2/token" in c.text]
    assert len(token_chunks) == 1
    assert "exchangeToken" in token_chunks[0].text
    assert "grant_type" in token_chunks[0].text
