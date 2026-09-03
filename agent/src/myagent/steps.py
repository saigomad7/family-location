"""에이전트의 각 단계. 전부 순수 함수다.

규칙 세 가지 — 이걸 지키는 동안에만 Spyder에서 한 줄씩 확인하며 개발할 수 있다.
  1. 필요한 것은 전부 인자로 받는다 (전역 상태 금지).
  2. 결과는 dict / list[dict] / DataFrame 으로 돌려준다 (변수 탐색기에서 열린다).
  3. 프레임워크 콜백이나 클래스 내부에 로직을 숨기지 않는다.

새 단계를 추가할 때도 이 모양을 유지하면, agent.py 는 그냥 이들을 이어 붙이는
얇은 함수로 남고 app/main.py 는 계속 30줄짜리 껍데기로 남는다.
"""

import hashlib
import logging

from . import embeddings, llm, storage, vectordb

logger = logging.getLogger(__name__)

SYSTEM = (
    "너는 사내 문서를 근거로 답하는 어시스턴트다. "
    "주어진 컨텍스트에 있는 내용만으로 답하고, 근거가 없으면 모른다고 말한다. "
    "답변에는 사용한 문서의 doc_id 를 함께 밝힌다."
)


# ---------- 색인(indexing) ----------

def load_docs(keys: list[str]) -> list[dict]:
    """S3 키 목록을 문서로 읽어온다(캐시 경유)."""
    docs = []
    for key in keys:
        docs.append({"doc_id": key, "source_key": key, "text": storage.read_text(key)})
    return docs


def chunk(docs: list[dict], size: int = 800, overlap: int = 100) -> list[dict]:
    """문자 단위 슬라이딩 청킹. 단순하지만 눈으로 확인하기 쉽다."""
    step = max(1, size - overlap)
    chunks = []
    for doc in docs:
        text = doc["text"]
        for i, start in enumerate(range(0, max(len(text), 1), step)):
            piece = text[start : start + size].strip()
            if not piece:
                continue
            chunks.append(
                {
                    "id": hashlib.sha1(f"{doc['doc_id']}#{i}".encode()).hexdigest(),
                    "doc_id": doc["doc_id"],
                    "source_key": doc["source_key"],
                    "chunk_idx": i,
                    "text": piece[: vectordb.TEXT_MAX_LEN],
                }
            )
    return chunks


def embed_chunks(chunks: list[dict], batch: int = 32) -> list[dict]:
    out = []
    for i in range(0, len(chunks), batch):
        part = chunks[i : i + batch]
        for row, vec in zip(part, embeddings.embed([c["text"] for c in part])):
            out.append({**row, "vector": vec})
    return out


def index(keys: list[str]) -> dict:
    """S3 키들을 읽어 청킹·임베딩해서 Milvus에 넣는다."""
    vectordb.ensure_collection()
    rows = embed_chunks(chunk(load_docs(keys)))
    n = vectordb.upsert(rows)
    return {"documents": len(keys), "chunks": n}


# ---------- 질의(query) ----------

def retrieve(question: str, k: int = 5, expr: str | None = None) -> list[dict]:
    return vectordb.search(embeddings.embed_one(question), k=k, expr=expr)


def build_prompt(question: str, contexts: list[dict]) -> str:
    """LLM에 보내기 전에 눈으로 확인하라고 문자열을 그대로 돌려준다."""
    blocks = [
        f"[{i + 1}] doc_id={c['doc_id']} (score={c['score']})\n{c['text']}"
        for i, c in enumerate(contexts)
    ]
    context = "\n\n".join(blocks) if blocks else "(검색 결과 없음)"
    return f"# 컨텍스트\n{context}\n\n# 질문\n{question}"


def answer(prompt: str, stream: bool = False) -> dict:
    return llm.complete(prompt, system=SYSTEM, stream=stream)
