# Enterprise MCP Bridge & Hybrid RAG Gateway

An enterprise-ready AI Gateway connecting foundation LLMs to internal relational databases and documentation without exposing raw credentials or sensitive PII.

## Architectural Highlights
- **Hybrid RAG Pipeline:** Sparse lexical matching (BM25) combined with dense vector representations (`sentence-transformers`), refined via cross-encoder reranking.
- **Model Context Protocol (MCP) Server:** Isolated read-only PostgreSQL bridge exposing schema-validated analytical telemetry.
- **Enterprise Guardrails:** Presidio-powered PII redaction layer and JWT-based Role-Based Access Control (`admin`, `analyst`, `viewer`).
- **LLMOps Benchmarks:** Automated evaluation pipeline powered by Ragas scoring context precision, faithfulness, and answer relevance.

## Quickstart

### 1. Run via Docker Compose
```bash
cp .env.example .env   # then set ANTHROPIC_API_KEY and a strong JWT_SECRET
docker compose up --build -d
curl http://localhost:8000/health
```

### 2. Local development
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d db
uvicorn src.main:app --reload
```

### 3. Benchmarks
```bash
python -m eval.benchmark_ragas
```

## Testing & Verification

Development dependencies (including `pytest`, `pytest-cov`, and `httpx`) are specified in `requirements-dev.txt`.

### Running the Automated Test Suite

Run the full suite with coverage inside an isolated gateway container:

```bash
docker compose run --rm -v "$PWD":/app gateway sh -c "pip install -q -r requirements-dev.txt && python -m pytest tests -v --cov=src"
```
