import os
import subprocess

import pytest
from fastapi.testclient import TestClient

from doclore_api.diagnostics.llm import LMStudioLLMAdapter
from doclore_api.ingestion.github import GitHubRepoManager
from doclore_api.main import app
from doclore_api.models import Project
from doclore_api.persistence.memory import InMemoryProjectRepository
from doclore_api.retrieval.dense import DenseVectorIndex
from doclore_api.workflow.graph import DiagnosticWorkflow


def _make_remote(tmp_path):
    remote = tmp_path / "remote"
    remote.mkdir()
    subprocess.run(["git", "init", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(remote), "config", "user.name", "T"], check=True)
    subprocess.run(["git", "-C", str(remote), "config", "user.email", "t@e.com"], check=True)
    (remote / "a.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(remote), "add", "."], check=True)
    subprocess.run(["git", "-C", str(remote), "commit", "-m", "init"], check=True, capture_output=True)
    return remote


def test_subpath_traversal_is_rejected(tmp_path):
    remote = _make_remote(tmp_path)
    with pytest.raises(ValueError, match="inside the repository"):
        GitHubRepoManager().sync_and_extract_files(
            github_url=str(remote),
            target_dir=str(tmp_path / "clone"),
            subpath="../..",
        )


def test_branch_option_injection_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Invalid branch"):
        GitHubRepoManager().sync_and_extract_files(
            github_url="https://github.com/owner/repo",
            target_dir=str(tmp_path / "clone"),
            branch="--upload-pack=evil",
        )


def test_non_github_url_rejected_when_local_disabled(tmp_path, monkeypatch):
    monkeypatch.delenv("DOCLORE_ALLOW_LOCAL_REPOS", raising=False)
    with pytest.raises(ValueError, match="Only GitHub"):
        GitHubRepoManager().sync_and_extract_files(
            github_url="https://example.com/x/y",
            target_dir=str(tmp_path / "clone"),
        )


def test_failed_import_leaves_no_project_and_reports_error():
    with TestClient(app) as client:
        before = len(client.get("/api/v1/projects").json())
        res = client.post(
            "/api/v1/projects",
            json={"name": "Broken", "github_url": "https://github.com/definitely-not/a-real-repo-xyz"},
        )
        assert res.status_code == 400
        assert "Could not import repository" in res.json()["detail"]
        assert len(client.get("/api/v1/projects").json()) == before


def test_blank_name_and_blank_message_rejected():
    with TestClient(app) as client:
        assert client.post("/api/v1/projects", json={"name": "   "}).status_code == 422
        proj = client.post("/api/v1/projects", json={"name": "Blank Msg"}).json()
        chat = client.post(f"/api/v1/projects/{proj['id']}/chats", json={}).json()
        res = client.post(
            f"/api/v1/projects/{proj['id']}/chats/{chat['id']}/messages", json={"content": "   "}
        )
        assert res.status_code == 422


def test_delete_project_cascades():
    with TestClient(app) as client:
        proj = client.post("/api/v1/projects", json={"name": "Cascade"}).json()
        pid = proj["id"]
        src = client.post(
            f"/api/v1/projects/{pid}/sources",
            json={
                "name": "Doc",
                "source_type": "markdown",
                "config": {"raw_content": "# Title\nbody text", "canonical_path": "d.md"},
            },
        ).json()
        assert client.post(f"/api/v1/sources/{src['id']}/sync").status_code == 200
        client.post(f"/api/v1/projects/{pid}/chats", json={})
        assert client.delete(f"/api/v1/projects/{pid}").status_code == 204
        assert client.get(f"/api/v1/sources/{src['id']}/documents").status_code == 404
        assert client.get(f"/api/v1/projects/{pid}/chats").status_code == 404


def test_server_filesystem_reads_blocked_via_api(monkeypatch):
    monkeypatch.delenv("DOCLORE_ALLOW_LOCAL_REPOS", raising=False)
    with TestClient(app) as client:
        pid = client.post("/api/v1/projects", json={"name": "FS"}).json()["id"]
        src = client.post(
            f"/api/v1/projects/{pid}/sources",
            json={"name": "Secrets", "source_type": "markdown", "config": {"file_path": __file__}},
        ).json()
        res = client.post(f"/api/v1/sources/{src['id']}/sync")
        assert res.status_code >= 400


def test_projects_persist_across_restart(tmp_path):
    path = str(tmp_path / "projects.json")
    repo = InMemoryProjectRepository(path)
    repo.create(Project(id="p1", name="Persisted"))
    reloaded = InMemoryProjectRepository(path)
    assert reloaded.get("p1").name == "Persisted"


def test_corrupt_snapshot_does_not_crash(tmp_path):
    path = tmp_path / "projects.json"
    path.write_text("{not json", encoding="utf-8")
    assert InMemoryProjectRepository(str(path)).list() == []


def test_llm_reasoning_blocks_are_stripped():
    assert LMStudioLLMAdapter._strip_reasoning("<think>plan...</think>{\"a\": 1}") == '{"a": 1}'
    assert LMStudioLLMAdapter._strip_reasoning("answer<think>cut off") == "answer"


def test_synthesis_json_extracted_from_prose():
    raw = 'Sure! ```json\n{"summary": "s", "explanation": "e", "recommended_actions": "do x"}\n``` done'
    parsed = DiagnosticWorkflow._parse_synthesis(raw)
    assert parsed["explanation"] == "e"
    assert parsed["recommended_actions"] == ["do x"]
    assert DiagnosticWorkflow._parse_synthesis("no json here") is None


class _CountingAdapter:
    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += len(texts)
        return [[1.0, float(len(t) % 3)] for t in texts]


def test_dense_index_does_not_reembed_unchanged_chunks():
    from doclore_api.models import Chunk, Provenance, SourceType

    def chunk(i, text):
        return Chunk(
            id=f"c{i}", document_id="d", text=text,
            provenance=Provenance(
                project_id="p", source_id="s", document_id="d", chunk_id=f"c{i}",
                source_type=SourceType.MARKDOWN, canonical_path="x.md", source_revision="r",
            ),
        )

    adapter = _CountingAdapter()
    index = DenseVectorIndex(embedding_adapter=adapter)
    chunks = [chunk(1, "alpha"), chunk(2, "beta")]
    index.index_chunks(chunks)
    index.index_chunks(chunks)
    assert adapter.calls == 2
    index.index_chunks([chunk(1, "alpha changed"), chunk(2, "beta")])
    assert adapter.calls == 3
