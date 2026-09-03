"""S3 어댑터 + 로컬 캐시.

핵심: 호출부에는 "로컬이냐 클라우드냐" 분기가 없다. fetch()가 캐시를 먼저 보고
없으면 S3에서 받아온다. 로컬에서는 한 번 받으면 계속 캐시를 쓰므로 빠르고,
App Service에서도 같은 코드가 그대로 동작한다(캐시 디렉터리만 /tmp 로).
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Iterator

import boto3
from botocore.config import Config

from .config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def client():
    s = get_settings()
    s.require("s3_endpoint", "s3_bucket", "s3_access_key", "s3_secret_key")
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
        # 사내 MinIO/Ceph 계열은 path-style 이 안전하다.
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
    )


def iter_keys(prefix: str = "") -> Iterator[dict]:
    s = get_settings()
    paginator = client().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=s.s3_bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj


def ls(prefix: str = "", limit: int = 1000):
    """버킷 목록을 DataFrame으로 돌려준다.

    Spyder 변수 탐색기에서 표로 열어 보라고 만든 함수다. S3에 뭐가 있는지
    브라우저를 열지 않고 확인하는 게 목적.
    """
    import pandas as pd

    rows = []
    for i, obj in enumerate(iter_keys(prefix)):
        if i >= limit:
            break
        rows.append(
            {
                "key": obj["Key"],
                "size_mb": round(obj["Size"] / 1e6, 4),
                "modified": obj["LastModified"],
            }
        )
    df = pd.DataFrame(rows, columns=["key", "size_mb", "modified"])
    return df.sort_values("modified", ascending=False).reset_index(drop=True)


def local_path(key: str) -> Path:
    return get_settings().cache_path / key


def fetch(key: str, force: bool = False) -> Path:
    """S3 객체를 로컬 파일로 확보하고 그 경로를 돌려준다. 있으면 캐시를 쓴다."""
    s = get_settings()
    dst = local_path(key)
    if dst.exists() and not force:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")  # 중간에 끊겨도 캐시가 오염되지 않게
    client().download_file(s.s3_bucket, key, str(tmp))
    tmp.replace(dst)
    logger.info("s3 download %s -> %s", key, dst)
    return dst


def read_text(key: str, encoding: str = "utf-8", force: bool = False) -> str:
    return fetch(key, force=force).read_text(encoding=encoding)


def put(key: str, path: str | Path) -> str:
    """결과물을 S3에 올린다.

    App Service의 디스크는 휘발성이다. 남겨야 할 산출물은 로컬 파일이 아니라
    반드시 여기를 거쳐야 한다.
    """
    s = get_settings()
    client().upload_file(str(path), s.s3_bucket, key)
    return f"s3://{s.s3_bucket}/{key}"


def cache_report():
    """로컬 캐시에 뭐가 쌓였는지 확인 (디스크 정리용)."""
    import pandas as pd

    root = get_settings().cache_path
    if not root.exists():
        return pd.DataFrame(columns=["key", "size_mb"])
    rows = [
        {"key": str(p.relative_to(root)), "size_mb": round(p.stat().st_size / 1e6, 4)}
        for p in root.rglob("*")
        if p.is_file()
    ]
    return pd.DataFrame(rows).sort_values("size_mb", ascending=False).reset_index(drop=True)
