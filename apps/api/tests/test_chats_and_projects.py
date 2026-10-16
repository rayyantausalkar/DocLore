import subprocess
from fastapi.testclient import TestClient

from doclore_api.main import app

REAL_ORDERS_CODE = """from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/api/v1")


async def verify_bearer_token(authorization: str = "") -> dict:
    \"\"\"Validate JWT bearer credentials from Authorization header.\"\"\"
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AUTH_INVALID_TOKEN: Missing Bearer token in header",
        )
    return {"sub": "user_456", "scope": "write:orders"}


@router.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_order(auth: dict = Depends(verify_bearer_token)) -> dict:
    \"\"\"Process customer order creation with verified permissions.\"\"\"
    return {"order_id": "ord_777", "status": "confirmed"}
"""


def test_projects_with_github_repo_and_chats_workflow(tmp_path):
    # 1. Create a simulated local Git repository remote (real code, no dummy data)
    remote_repo_dir = tmp_path / "orders_backend_repo"
    remote_repo_dir.mkdir()

    subprocess.run(["git", "init", str(remote_repo_dir)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(remote_repo_dir), "config", "user.name", "TestUser"], check=True)
    subprocess.run(["git", "-C", str(remote_repo_dir), "config", "user.email", "test@example.com"], check=True)

    src_dir = remote_repo_dir / "src"
    src_dir.mkdir()
    (src_dir / "routes.py").write_text(REAL_ORDERS_CODE, encoding="utf-8")

    subprocess.run(["git", "-C", str(remote_repo_dir), "add", "."], check=True)
    subprocess.run(["git", "-C", str(remote_repo_dir), "commit", "-m", "Initial commit"], check=True)

    with TestClient(app) as client:
        # 2. Create Project with GitHub repo URL directly
        proj_res = client.post(
            "/api/v1/projects",
            json={
                "name": "Orders Backend",
                "description": "Customer order processing service",
                "github_url": str(remote_repo_dir),
            },
        )
        assert proj_res.status_code == 201
        project = proj_res.json()
        project_id = project["id"]
        assert project["name"] == "Orders Backend"
        assert project["github_url"] == str(remote_repo_dir)
        assert project["repo_status"] == "synced"
        assert project["document_count"] >= 1

        # 3. Create a chat session inside the project
        chat_create_res = client.post(
            f"/api/v1/projects/{project_id}/chats",
            json={"title": "Auth Debugging"},
        )
        assert chat_create_res.status_code == 201
        chat = chat_create_res.json()
        chat_id = chat["id"]
        assert chat["title"] == "Auth Debugging"
        assert chat["project_id"] == project_id
        assert len(chat["messages"]) == 0

        # 4. Send message in simple English inside the chat
        msg_res = client.post(
            f"/api/v1/projects/{project_id}/chats/{chat_id}/messages",
            json={"content": "Why am I getting a 401 when calling this API?"},
        )
        assert msg_res.status_code == 200
        updated_chat = msg_res.json()
        assert len(updated_chat["messages"]) == 2

        user_msg = updated_chat["messages"][0]
        assert user_msg["role"] == "user"
        assert user_msg["content"] == "Why am I getting a 401 when calling this API?"

        asst_msg = updated_chat["messages"][1]
        assert asst_msg["role"] == "assistant"
        assert len(asst_msg["summary"]) > 0
        assert len(asst_msg["citations"]) >= 1
        assert "routes.py" in asst_msg["citations"][0]["canonical_path"]

        # 5. List chats for project
        list_res = client.get(f"/api/v1/projects/{project_id}/chats")
        assert list_res.status_code == 200
        chats_list = list_res.json()
        assert len(chats_list) == 1
        assert chats_list[0]["id"] == chat_id
