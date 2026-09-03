"""Milvus 어댑터.

로컬에서는 docker-compose.dev.yml 로 띄운 Milvus, 클라우드에서는 사내 Milvus를
본다. 바뀌는 건 MILVUS_URI 뿐이다.

스키마는 **코드가 진실**이다. 콘솔에서 손으로 컬렉션을 만들면 로컬과 클라우드가
갈라지고, 그 차이는 검색 결과가 이상해질 때까지 드러나지 않는다.
"""

import logging
from functools import lru_cache

from pymilvus import DataType, MilvusClient

from .config import get_settings

logger = logging.getLogger(__name__)

TEXT_MAX_LEN = 60000


@lru_cache
def client() -> MilvusClient:
    s = get_settings()
    kwargs = {"uri": s.milvus_uri}
    if s.milvus_token:
        kwargs["token"] = s.milvus_token
    return MilvusClient(**kwargs)


def ensure_collection(drop: bool = False) -> str:
    """컬렉션이 없으면 만든다. 로컬/클라우드 어디서 돌려도 같은 스키마가 나온다."""
    s = get_settings()
    name = s.milvus_collection
    c = client()

    if drop and c.has_collection(name):
        logger.warning("dropping collection %s", name)
        c.drop_collection(name)

    if c.has_collection(name):
        return name

    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=True)
    schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=256)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=s.embed_dim)
    schema.add_field("doc_id", DataType.VARCHAR, max_length=256)
    schema.add_field("source_key", DataType.VARCHAR, max_length=1024)
    schema.add_field("chunk_idx", DataType.INT64)
    schema.add_field("text", DataType.VARCHAR, max_length=TEXT_MAX_LEN)

    index_params = MilvusClient.prepare_index_params()
    index_params.add_index(
        field_name="vector", index_type="AUTOINDEX", metric_type="COSINE"
    )

    c.create_collection(collection_name=name, schema=schema, index_params=index_params)
    logger.info("created collection %s (dim=%s)", name, s.embed_dim)
    return name


def upsert(rows: list[dict]) -> int:
    """rows: id / vector / doc_id / source_key / chunk_idx / text 를 담은 dict 목록."""
    if not rows:
        return 0
    s = get_settings()
    client().upsert(collection_name=s.milvus_collection, data=rows)
    return len(rows)


def search(vector: list[float], k: int = 5, expr: str | None = None) -> list[dict]:
    s = get_settings()
    hits = client().search(
        collection_name=s.milvus_collection,
        data=[vector],
        limit=k,
        filter=expr or "",
        output_fields=["doc_id", "source_key", "chunk_idx", "text"],
    )
    return [
        {"score": round(float(h["distance"]), 4), **h["entity"]} for h in hits[0]
    ]


def stats() -> dict:
    """/diag 와 Spyder에서 "지금 무슨 컬렉션을 보고 있나"를 확인하는 용도."""
    s = get_settings()
    c = client()
    info = {"uri": s.milvus_uri, "collections": c.list_collections()}
    if c.has_collection(s.milvus_collection):
        info["collection"] = s.milvus_collection
        info["num_entities"] = c.get_collection_stats(s.milvus_collection).get(
            "row_count"
        )
    else:
        info["collection"] = f"{s.milvus_collection} (없음)"
    return info
