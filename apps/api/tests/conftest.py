import os
import tempfile

# Must be set before doclore_api.api.routes is imported by any test module.
os.environ.setdefault("DOCLORE_ALLOW_LOCAL_REPOS", "1")
os.environ["DOCLORE_DATA_DIR"] = tempfile.mkdtemp(prefix="doclore_test_data_")
# Never hit a real LM Studio during tests.
os.environ.setdefault("DOCLORE_LLM_BASE_URL", "http://127.0.0.1:9/v1")
