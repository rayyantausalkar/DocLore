from fastapi.testclient import TestClient
from doclore_api.main import app


def test_supported_types_endpoint() -> None:
    with TestClient(app) as client:
        res = client.get("/api/v1/sources/supported-types")
    assert res.status_code == 200
    data = res.json()
    assert any(item["source_type"] == "markdown" and item["status"] == "supported" for item in data)
    assert any(item["source_type"] == "openapi" and item["status"] == "supported" for item in data)
    assert any(item["source_type"] == "repository" and item["status"] == "supported" for item in data)
    assert any(item["source_type"] == "issue_logs" and item["status"] == "supported" for item in data)
    assert any(item["source_type"] == "style_guide" and item["status"] == "supported" for item in data)
    assert any(item["source_type"] == "architecture_diagram" and item["status"] == "supported" for item in data)


def test_project_lifecycle_and_sources() -> None:
    with TestClient(app) as client:
        # 1. Create project
        create_proj_res = client.post(
            "/api/v1/projects",
            json={"name": "Payment Engine", "description": "Payment microservice docs"},
        )
        assert create_proj_res.status_code == 201
        project = create_proj_res.json()
        project_id = project["id"]
        assert project["name"] == "Payment Engine"

        # 2. Get project
        get_proj_res = client.get(f"/api/v1/projects/{project_id}")
        assert get_proj_res.status_code == 200
        assert get_proj_res.json()["id"] == project_id

        # 3. Register invalid source type -> Expect 422
        invalid_res = client.post(
            f"/api/v1/projects/{project_id}/sources",
            json={
                "name": "Invalid Source",
                "source_type": "unknown_type",
                "config": {"path": "/invalid"},
            },
        )
        assert invalid_res.status_code == 422


        # 4. Register supported markdown source
        md_content = """# Payment API Guide

## Authorization

All endpoints require an Authorization header:

```http
Authorization: Bearer <oauth_token>
```

If unauthorized, the server returns 401 with code `AUTH_INVALID_TOKEN`.
"""
        create_source_res = client.post(
            f"/api/v1/projects/{project_id}/sources",
            json={
                "name": "Payment Docs",
                "source_type": "markdown",
                "config": {
                    "raw_content": md_content,
                    "canonical_path": "docs/payments.md",
                },
            },
        )
        assert create_source_res.status_code == 201
        source = create_source_res.json()
        source_id = source["id"]
        assert source["status"] == "pending"

        # 5. List sources for project
        list_sources_res = client.get(f"/api/v1/projects/{project_id}/sources")
        assert list_sources_res.status_code == 200
        sources_list = list_sources_res.json()
        assert len(sources_list) == 1
        assert sources_list[0]["id"] == source_id

        # 6. Trigger sync
        sync_res = client.post(f"/api/v1/sources/{source_id}/sync")
        assert sync_res.status_code == 200
        sync_data = sync_res.json()
        assert sync_data["status"] == "synced"
        assert sync_data["document_count"] == 1
        assert sync_data["chunk_count"] >= 1
        assert not sync_data["is_idempotent_skip"]

        # 7. Check source status updated to synced
        get_source_res = client.get(f"/api/v1/sources/{source_id}")
        assert get_source_res.status_code == 200
        assert get_source_res.json()["status"] == "synced"

        # 8. Inspect indexed documents and chunks
        docs_res = client.get(f"/api/v1/sources/{source_id}/documents")
        assert docs_res.status_code == 200
        docs = docs_res.json()
        assert len(docs) == 1
        doc = docs[0]
        assert doc["title"] == "Payment API Guide"
        assert doc["canonical_path"] == "docs/payments.md"
        assert len(doc["chunks"]) > 0

        # Verify chunks have line ranges and provenance
        first_chunk = doc["chunks"][0]
        assert "provenance" in first_chunk
        prov = first_chunk["provenance"]
        assert prov["project_id"] == project_id
        assert prov["source_id"] == source_id
        assert prov["canonical_path"] == "docs/payments.md"
        assert prov["start_line"] >= 1
        assert prov["end_line"] >= prov["start_line"]
        assert prov["source_type"] == "markdown"

        # 9. Test hybrid search endpoint
        search_res = client.post(
            f"/api/v1/projects/{project_id}/search",
            json={"query": "AUTH_INVALID_TOKEN", "limit": 3},
        )
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert search_data["total_results"] > 0
        top_result = search_data["results"][0]
        assert "AUTH_INVALID_TOKEN" in top_result["text"]
        assert top_result["provenance"]["canonical_path"] == "docs/payments.md"
        assert top_result["rrf_score"] > 0.0

        # 10. Test project update (PATCH)
        patch_proj_res = client.patch(
            f"/api/v1/projects/{project_id}",
            json={"name": "Payment Platform", "description": "Updated description"},
        )
        assert patch_proj_res.status_code == 200
        assert patch_proj_res.json()["name"] == "Payment Platform"
        assert patch_proj_res.json()["description"] == "Updated description"

        # 11. Test source update (PATCH) and delete (DELETE)
        patch_src_res = client.patch(
            f"/api/v1/sources/{source_id}",
            json={"name": "Renamed Payment Docs"},
        )
        assert patch_src_res.status_code == 200
        assert patch_src_res.json()["name"] == "Renamed Payment Docs"

        # 12. Test chat CRUD: create, update, delete
        create_chat_res = client.post(
            f"/api/v1/projects/{project_id}/chats",
            json={"title": "Test Chat"},
        )
        assert create_chat_res.status_code == 201
        chat_id = create_chat_res.json()["id"]

        patch_chat_res = client.patch(
            f"/api/v1/projects/{project_id}/chats/{chat_id}",
            json={"title": "Renamed Chat"},
        )
        assert patch_chat_res.status_code == 200
        assert patch_chat_res.json()["title"] == "Renamed Chat"

        del_chat_res = client.delete(f"/api/v1/projects/{project_id}/chats/{chat_id}")
        assert del_chat_res.status_code == 204

        # 13. Test source delete
        del_src_res = client.delete(f"/api/v1/sources/{source_id}")
        assert del_src_res.status_code == 204
        assert client.get(f"/api/v1/sources/{source_id}").status_code == 404
        assert client.get(f"/api/v1/sources/{source_id}/documents").status_code == 404

        # 14. Test project delete
        del_proj_res = client.delete(f"/api/v1/projects/{project_id}")
        assert del_proj_res.status_code == 204
        assert client.get(f"/api/v1/projects/{project_id}").status_code == 404


