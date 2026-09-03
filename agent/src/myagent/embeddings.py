"""임베딩 어댑터.

provider=local  : sentence-transformers 를 프로세스 안에서 실행 (오프라인, 재현 가능)
provider=http   : 사내 임베딩 API 호출

로컬/클라우드에서 **같은 모델**을 써야 벡터가 호환된다. 다른 모델로 색인한
Milvus 컬렉션을 검색하면 에러 없이 조용히 엉뚱한 결과가 나온다 — 제일 찾기
어려운 버그이므로, ops/seed_milvus.py 가 컬렉션에 모델 이름을 함께 기록한다.
"""

import logging
from functools import lru_cache

from .config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _local_model():
    from sentence_transformers import SentenceTransformer

    s = get_settings()
    logger.info("loading embedding model %s", s.embed_model)
    return SentenceTransformer(s.embed_model)


def embed(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    if not texts:
        return []

    if s.embed_provider == "local":
        vectors = _local_model().encode(texts, normalize_embeddings=True)
        out = [v.tolist() for v in vectors]
    elif s.embed_provider == "http":
        import httpx

        s.require("embed_endpoint")
        resp = httpx.post(s.embed_endpoint, json={"texts": texts}, timeout=60)
        resp.raise_for_status()
        out = resp.json()["embeddings"]
    else:
        raise ValueError(f"알 수 없는 EMBED_PROVIDER: {s.embed_provider}")

    if out and len(out[0]) != s.embed_dim:
        raise RuntimeError(
            f"임베딩 차원 불일치: 모델은 {len(out[0])}, 설정(EMBED_DIM)은 {s.embed_dim}. "
            f"Milvus 컬렉션과 반드시 같아야 합니다."
        )
    return out


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
