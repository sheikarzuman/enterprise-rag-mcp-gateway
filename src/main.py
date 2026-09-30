from fastapi import FastAPI, Depends
from pydantic import BaseModel
from src.security import verify_jwt, redact_pii
from src.rag.hybrid_engine import HybridRAGEngine
from src.mcp_server.db_server import query_telemetry_db
import anthropic
import logging
import os

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Enterprise MCP Bridge & Hybrid RAG Gateway",
    description="FDE Production API integrating Hybrid RAG, MCP tool execution, and PII anonymization.",
    version="1.0.0"
)

rag_engine = HybridRAGEngine()

class QueryRequest(BaseModel):
    prompt: str
    include_telemetry_tool: bool = True

class QueryResponse(BaseModel):
    sanitized_prompt: str
    retrieved_context: list[dict]
    mcp_tool_output: str
    synthesized_resolution: str

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "mcp-rag-gateway"}

@app.post("/api/v1/solve", response_model=QueryResponse)
def solve_incident(
    req: QueryRequest,
    user: dict = Depends(verify_jwt)
):
    # Step 1: PII Sanitization
    clean_prompt = redact_pii(req.prompt)

    # Step 2: Hybrid RAG Retrieval (Dense + Sparse + Cross-Encoder)
    docs = rag_engine.retrieve(clean_prompt, top_k=2)
    context_str = "\n".join([f"[{d['id']} - {d['title']}]: {d['content']}" for d in docs])

    # Step 3: MCP Tool Call (Read-Only DB bridge)
    mcp_data = "Tool not requested."
    if req.include_telemetry_tool:
        # Sandboxed parameter query
        mcp_data = query_telemetry_db(
            "SELECT device_id, subsystem, status, temperature_c, load_pct FROM enterprise_telemetry WHERE status IN ('WARNING', 'CRITICAL');"
        )

    # Step 4: Claude Context Synthesis
    api_key = os.getenv("ANTHROPIC_API_KEY")
    resolution = None
    if api_key and api_key != "mock-key":
        system_instruction = (
            "You are an enterprise Forward Deployed Engineer responding to operational incidents. "
            "Use the provided documentation context and live telemetry data to draft a root-cause remediation."
        )
        user_message = f"User Request: {clean_prompt}\n\nRetrieved SOPs:\n{context_str}\n\nLive System Telemetry:\n{mcp_data}"
        try:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model="claude-sonnet-5",
                max_tokens=500,
                system=system_instruction,
                messages=[{"role": "user", "content": user_message}]
            )
            resolution = response.content[0].text
        except anthropic.APIError:
            logger.exception("Claude synthesis failed; falling back to offline response")

    if resolution is None:
        resolution = (
            f"[OFFLINE MOCK RESPONSE]\n"
            f"Action Required: High-temp warning detected in telemetry ({mcp_data}).\n"
            f"Cross-referencing {docs[0]['id']}: Trigger manual de-rating and lube flush immediately."
        )

    return QueryResponse(
        sanitized_prompt=clean_prompt,
        retrieved_context=docs,
        mcp_tool_output=mcp_data,
        synthesized_resolution=resolution
    )
