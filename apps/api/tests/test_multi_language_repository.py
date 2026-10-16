import os
import tempfile
import pytest

from doclore_api.ingestion.repository import (
    DEFAULT_IGNORE_DIRS,
    DEFAULT_IGNORE_FILES,
    DEFAULT_REPOSITORY_EXTENSIONS,
    EXACT_FILENAME_MATCHES,
    RepositoryAdapter,
    get_file_language,
)
from doclore_api.models import Project, Source, SourceStatus, SourceType
from doclore_api.persistence.memory import (
    InMemoryDocumentRepository,
    InMemoryProjectRepository,
    InMemorySourceRepository,
)
from doclore_api.retrieval.service import RetrievalService
from doclore_api.sources.service import SourceService


TS_SAMPLE = """import express, { Request, Response } from 'express';

export interface UserProfile {
  id: string;
  email: string;
  role: 'admin' | 'developer';
}

export class AuthService {
  private secretKey: string;

  constructor(secretKey: string) {
    this.secretKey = secretKey;
  }

  public validateToken(token: string): boolean {
    return token.startsWith("Bearer valid_");
  }
}

const app = express();

app.post('/api/v2/auth/login', async (req: Request, res: Response) => {
  const { username, password } = req.body;
  if (!username) {
    return res.status(400).json({ error: 'MISSING_CREDENTIALS' });
  }
  return res.status(200).json({ token: 'Bearer valid_mock_token' });
});

export default app;
"""

GO_SAMPLE = """package main

import (
\t"net/http"
\t"github.com/gin-gonic/gin"
)

type PaymentPayload struct {
\tAmountCents int64  `json:"amount_cents"`
\tCurrency    string `json:"currency"`
}

type PaymentGateway interface {
\tCharge(payload PaymentPayload) (string, error)
}

func ProcessPaymentHandler(c *gin.Context) {
\tvar payload PaymentPayload
\tif err := c.ShouldBindJSON(&payload); err != nil {
\t\tc.JSON(http.StatusBadRequest, gin.H{"error": "PAYMENT_PAYLOAD_INVALID"})
\t\treturn
\t}
\tc.JSON(http.StatusOK, gin.H{"status": "captured", "charge_id": "ch_999"})
}

func main() {
\tr := gin.Default()
\tr.POST("/v1/payments/charge", ProcessPaymentHandler)
\tr.Run(":8080")
}
"""

RUST_SAMPLE = """use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct ClusterConfig {
    pub node_id: String,
    pub heartbeat_interval_ms: u64,
}

pub trait ClusterNode {
    fn ping(&self) -> bool;
}

impl ClusterConfig {
    pub fn new(node_id: String) -> Self {
        Self {
            node_id,
            heartbeat_interval_ms: 1000,
        }
    }
}

pub fn initialize_cluster(config: ClusterConfig) -> Result<(), String> {
    if config.node_id.is_empty() {
        return Err("NODE_ID_REQUIRED".to_string());
    }
    Ok(())
}
"""

YAML_SAMPLE = """version: '3.8'
services:
  web:
    image: node:18-alpine
    ports:
      - "3000:3000"
    environment:
      - NODE_ENV=production
  api:
    image: python:3.10-slim
    ports:
      - "8000:8000"
    environment:
      - AUTH_SECRET=secret123
"""


def test_language_detection():
    assert get_file_language("src/index.ts") == "typescript"
    assert get_file_language("src/App.tsx") == "typescript"
    assert get_file_language("utils.js") == "javascript"
    assert get_file_language("backend/main.go") == "go"
    assert get_file_language("core/lib.rs") == "rust"
    assert get_file_language("config.yaml") == "yaml"
    assert get_file_language("Dockerfile") == "dockerfile"
    assert get_file_language("script.sh") == "bash"
    assert get_file_language("query.sql") == "sql"


def test_typescript_chunking():
    adapter = RepositoryAdapter()
    source = Source(
        id="src-ts",
        project_id="proj-1",
        name="ts-repo",
        source_type=SourceType.REPOSITORY,
        config={},
    )
    docs = adapter.parse(
        source=source,
        content=TS_SAMPLE,
        canonical_path="src/server.ts",
        revision="rev-0",
    )
    assert len(docs) == 1
    doc = docs[0]
    assert doc.canonical_path == "src/server.ts"
    assert doc.source_id == "src-ts"
    assert len(doc.chunks) > 0

    # Ensure line bounds are valid
    for chunk in doc.chunks:
        assert chunk.provenance.start_line is not None
        assert chunk.provenance.end_line is not None
        assert 1 <= chunk.provenance.start_line <= chunk.provenance.end_line

    section_paths = [c.provenance.section_path for c in doc.chunks]
    assert any("interface:UserProfile" in sp for sp in section_paths)
    assert any("class:AuthService" in sp for sp in section_paths)
    assert any("route:POST /api/v2/auth/login" in sp for sp in section_paths)


def test_go_chunking():
    adapter = RepositoryAdapter()
    source = Source(
        id="src-go",
        project_id="proj-1",
        name="go-repo",
        source_type=SourceType.REPOSITORY,
        config={},
    )
    docs = adapter.parse(
        source=source,
        content=GO_SAMPLE,
        canonical_path="cmd/main.go",
        revision="rev-0",
    )
    assert len(docs) == 1
    doc = docs[0]
    section_paths = [c.provenance.section_path for c in doc.chunks]
    assert any("struct:PaymentPayload" in sp for sp in section_paths)
    assert any("func:ProcessPaymentHandler" in sp for sp in section_paths)
    assert any("route:POST /v1/payments/charge" in sp for sp in section_paths)


def test_rust_chunking():
    adapter = RepositoryAdapter()
    source = Source(
        id="src-rs",
        project_id="proj-1",
        name="rs-repo",
        source_type=SourceType.REPOSITORY,
        config={},
    )
    docs = adapter.parse(
        source=source,
        content=RUST_SAMPLE,
        canonical_path="src/lib.rs",
        revision="rev-0",
    )
    assert len(docs) == 1
    doc = docs[0]
    section_paths = [c.provenance.section_path for c in doc.chunks]
    assert any("struct:ClusterConfig" in sp for sp in section_paths)
    assert any("func:initialize_cluster" in sp for sp in section_paths)
    assert any("impl:ClusterConfig" in sp for sp in section_paths)


def test_yaml_config_chunking():
    adapter = RepositoryAdapter()
    source = Source(
        id="src-yaml",
        project_id="proj-1",
        name="yaml-repo",
        source_type=SourceType.REPOSITORY,
        config={},
    )
    docs = adapter.parse(
        source=source,
        content=YAML_SAMPLE,
        canonical_path="docker-compose.yml",
        revision="rev-0",
    )
    assert len(docs) == 1
    doc = docs[0]
    assert len(doc.chunks) >= 1
    assert "services:" in doc.chunks[0].text
    assert doc.chunks[0].provenance.section_path == "docker-compose.yml > lines 1-14"


def test_source_service_multi_language_directory_sync():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create TS, Go, YAML, Dockerfile
        os.makedirs(os.path.join(temp_dir, "src"), exist_ok=True)
        os.makedirs(os.path.join(temp_dir, "node_modules", "pkg"), exist_ok=True)
        os.makedirs(os.path.join(temp_dir, ".git"), exist_ok=True)

        with open(os.path.join(temp_dir, "src", "server.ts"), "w", encoding="utf-8") as f:
            f.write(TS_SAMPLE)
        with open(os.path.join(temp_dir, "main.go"), "w", encoding="utf-8") as f:
            f.write(GO_SAMPLE)
        with open(os.path.join(temp_dir, "docker-compose.yml"), "w", encoding="utf-8") as f:
            f.write(YAML_SAMPLE)
        with open(os.path.join(temp_dir, "Dockerfile"), "w", encoding="utf-8") as f:
            f.write("FROM node:18-alpine\nWORKDIR /app\nCOPY . .\nCMD [\"npm\", \"start\"]\n")

        # Files that should be ignored
        with open(os.path.join(temp_dir, "node_modules", "pkg", "index.js"), "w", encoding="utf-8") as f:
            f.write("// ignored node modules")
        with open(os.path.join(temp_dir, "package-lock.json"), "w", encoding="utf-8") as f:
            f.write("{\"name\": \"lockfile\"}")
        with open(os.path.join(temp_dir, "binary.exe"), "wb") as f:
            f.write(b"MZ\x00\x00BinaryExeExecutable")

        # Set up repositories & service
        proj_repo = InMemoryProjectRepository()
        src_repo = InMemorySourceRepository()
        doc_repo = InMemoryDocumentRepository()

        proj = Project(id="proj-poly", name="Polyglot Project")
        proj_repo.create(proj)

        service = SourceService(
            project_repo=proj_repo,
            source_repo=src_repo,
            document_repo=doc_repo,
        )

        source = Source(
            id="src-poly-1",
            project_id="proj-poly",
            name="polyglot-repo",
            source_type=SourceType.REPOSITORY,
            config={"repo_path": temp_dir},
        )
        service.source_repo.create(source)

        result = service.sync(source.id)
        assert result.status == SourceStatus.SYNCED
        assert result.document_count == 4

        docs = doc_repo.list_by_source(source.id)
        doc_paths = {d.canonical_path for d in docs}
        assert "src/server.ts" in doc_paths
        assert "main.go" in doc_paths
        assert "docker-compose.yml" in doc_paths
        assert "Dockerfile" in doc_paths
        assert "node_modules/pkg/index.js" not in doc_paths
        assert "package-lock.json" not in doc_paths
        assert "binary.exe" not in doc_paths

        # Test search retrieval across TypeScript and Go documents
        retrieval_service = RetrievalService(source_repo=src_repo, document_repo=doc_repo)
        from doclore_api.retrieval.models import RetrievalScope
        search_ts = retrieval_service.search(
            query="auth login MISSING_CREDENTIALS",
            scope=RetrievalScope(project_id="proj-poly"),
        )
        assert len(search_ts) > 0
        assert any("server.ts" in e.provenance.canonical_path for e in search_ts)

        search_go = retrieval_service.search(
            query="PAYMENT_PAYLOAD_INVALID PaymentPayload",
            scope=RetrievalScope(project_id="proj-poly"),
        )
        assert len(search_go) > 0
        assert any("main.go" in e.provenance.canonical_path for e in search_go)
