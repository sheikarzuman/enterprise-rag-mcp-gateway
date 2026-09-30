import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

DEFAULT_CORPUS = [
    {
        "id": "SOP-801",
        "title": "Turbine Maintenance Standard Operating Procedure",
        "content": "Turbine-002 bearing hub operating above 85C requires emergency lubricant flushing and immediate load de-rating to 50% capacity."
    },
    {
        "id": "SOP-802",
        "title": "Critical Overheat Protocol",
        "content": "Any subsystem exceeding 110C triggers automated telemetry shutdown, isolation of the fuel delivery rail, and dispatch of field crew within 15 minutes."
    },
    {
        "id": "SOP-803",
        "title": "Hydraulic Pressure Guidelines",
        "content": "Hydraulic-Loop systems operate optimally at 50-60C. Pressure variance exceeding 15% requires servo valve realignment."
    }
]

class HybridRAGEngine:
    def __init__(self, documents=None):
        self.documents = documents or DEFAULT_CORPUS
        self.corpus_texts = [d["content"] for d in self.documents]
        self.tokenized_corpus = [d.lower().split() for d in self.corpus_texts]
        self.bm25 = BM25Okapi(self.tokenized_corpus)

        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        self.doc_embeddings = self.embedder.encode(self.corpus_texts, convert_to_numpy=True)

    def retrieve(self, query: str, top_k: int = 2) -> list[dict]:
        # 1. BM25 Lexical Score
        bm25_scores = self.bm25.get_scores(query.lower().split())

        # 2. Dense Semantic Cosine Similarity
        q_emb = self.embedder.encode([query], convert_to_numpy=True)[0]
        dense_scores = np.dot(self.doc_embeddings, q_emb) / (
            np.linalg.norm(self.doc_embeddings, axis=1) * np.linalg.norm(q_emb) + 1e-9
        )

        # 3. Reciprocal Rank Fusion / Weighted Blend
        candidates = []
        for i, doc in enumerate(self.documents):
            score = float(dense_scores[i]) + (float(bm25_scores[i]) * 0.1)
            candidates.append((score, doc))

        candidates.sort(key=lambda x: x[0], reverse=True)
        pooled_docs = [c[1] for c in candidates[:5]]

        # 4. Cross-Encoder Reranking
        pairs = [[query, d["content"]] for d in pooled_docs]
        rerank_scores = self.reranker.predict(pairs)
        ranked = [doc for _, doc in sorted(zip(rerank_scores, pooled_docs), key=lambda x: x[0], reverse=True)]

        return ranked[:top_k]
