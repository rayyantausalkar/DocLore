import os
import subprocess
import tempfile
import pytest
from fastapi.testclient import TestClient

from doclore_api.ingestion.github import GitHubRepoManager
from doclore_api.main import app


SAMPLE_REPO_CODE = """from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/api/v1")


async def verify_bearer_token(authorization: str = "") -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AUTH_INVALID_TOKEN")
    return {"user": "alice"}


@router.post("/orders")
async def create_order(auth: dict = Depends(verify_bearer_token)) -> dict:
    return {"order_id": "ord-999", "status": "created"}
"""


def test_github_url_parser():
    manager = GitHubRepoManager()

    # Standard HTTPS
    info1 = manager.parse_github_url("https://github.com/fastapi/fastapi")
    assert info1.owner == "fastapi"
    assert info1.repo_name == "fastapi"
    assert info1.clone_url == "https://github.com/fastapi/fastapi.git"

    # HTTPS with .git
    info2 = manager.parse_github_url("https://github.com/pallets/flask.git")
    assert info2.owner == "pallets"
    assert info2.repo_name == "flask"

    # HTTPS with tree and subpath
    info3 = manager.parse_github_url("https://github.com/myorg/services/tree/release-v2/backend/orders")
    assert info3.owner == "myorg"
    assert info3.repo_name == "services"
    assert info3.branch == "release-v2"
    assert info3.subpath == "backend/orders"

    # SSH format
    info4 = manager.parse_github_url("git@github.com:myorg/repo.git")
    assert info4.owner == "myorg"
    assert info4.repo_name == "repo"


def test_github_repository_ingestion_end_to_end(tmp_path):
    # 1. Create a simulated local Git repository remote
    remote_repo_dir = tmp_path / "simulated_github_remote"
    remote_repo_dir.mkdir()
    
    subprocess.run(["git", "init", str(remote_repo_dir)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(remote_repo_dir), "config", "user.name", "TestUser"], check=True)
    subprocess.run(["git", "-C", str(remote_repo_dir), "config", "user.email", "test@example.com"], check=True)

    src_dir = remote_repo_dir / "src"
    src_dir.mkdir()
    code_file = src_dir / "routes.py"
    code_file.write_text(SAMPLE_REPO_CODE, encoding="utf-8")

    subprocess.run(["git", "-C", str(remote_repo_dir), "add", "."], check=True)
    subprocess.run(["git", "-C", str(remote_repo_dir), "commit", "-m", "Initial commit"], check=True)

    # 2. Register source in DocLore using the git repo URL
    with TestClient(app) as client:
        proj_res = client.post("/api/v1/projects", json={"name": "GitHub Ingestion Test"})
        assert proj_res.status_code == 201
        project_id = proj_res.json()["id"]

        source_res = client.post(
            f"/api/v1/projects/{project_id}/sources",
            json={
                "name": "Orders GitHub Repo",
                "source_type": "repository",
                "config": {
                    "github_url": str(remote_repo_dir),
                    "storage_dir": str(tmp_path / "cloned_cache"),
                },
            },
        )
        assert source_res.status_code == 201
        source_id = source_res.json()["id"]

        # 3. Trigger sync
        sync_res = client.post(f"/api/v1/sources/{source_id}/sync")
        assert sync_res.status_code == 200
        sync_data = sync_res.json()
        assert sync_data["status"] == "synced"
        assert sync_data["document_count"] >= 1
        assert sync_data["chunk_count"] >= 2  # Function + Route chunks extracted via AST

        # 4. Verify indexed documents and line numbers
        docs_res = client.get(f"/api/v1/sources/{source_id}/documents")
        assert docs_res.status_code == 200
        docs = docs_res.json()
        assert len(docs) == 1
        doc = docs[0]
        assert "routes.py" in doc["canonical_path"]
        assert any("route:POST /orders" in (c["provenance"]["section_path"] or "") for c in doc["chunks"])
        assert any("create_order" in c["text"] for c in doc["chunks"])
