import pytest
from fastapi.testclient import TestClient
from jose import jwt

from src.rag import hybrid_engine

FAKE_DOCS = (
    {
        "id": "SOP-801",
        "title": "Turbine Maintenance Standard Operating Procedure",
        "content": "Turbine-002 bearing hub operating above 85C requires emergency lubricant flushing.",
    },
    {
        "id": "SOP-802",
        "title": "Critical Overheat Protocol",
        "content": "Any subsystem exceeding 110C triggers automated telemetry shutdown.",
    },
)


class FakeRAGEngine:
    """Skips the Hugging Face model downloads that the real engine performs at import time."""

    def __init__(self, documents=None):
        self.documents = documents

    def retrieve(self, query: str, top_k: int = 2) -> list[dict]:
        return [dict(doc) for doc in FAKE_DOCS[:top_k]]


hybrid_engine.HybridRAGEngine = FakeRAGEngine

from src.config import settings  # noqa: E402
from src.main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def make_token(role: str, secret: str | None = None) -> str:
    payload = {"sub": f"test-{role}", "role": role}
    return jwt.encode(payload, secret or settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture
def admin_token():
    return make_token("admin")


@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
