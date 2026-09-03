"""로컬 Milvus에 샘플 데이터를 넣는다.

전체를 넣지 말 것. 수백~수천 청크면 개발 반복이 몇 초로 끝난다.

    python ops/seed_milvus.py --prefix raw/2024/ --limit 20
    python ops/seed_milvus.py --prefix raw/2024/ --limit 20 --recreate
"""

import argparse

from myagent import steps, storage, vectordb
from myagent.config import get_settings
from myagent.logging_setup import setup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--suffix", default=".txt,.md", help="쉼표로 구분한 확장자")
    parser.add_argument("--recreate", action="store_true", help="컬렉션을 지우고 다시 만든다")
    args = parser.parse_args()

    setup()
    s = get_settings()
    print(f"대상 Milvus: {s.milvus_uri} / 컬렉션: {s.milvus_collection}")
    vectordb.ensure_collection(drop=args.recreate)

    suffixes = tuple(x.strip() for x in args.suffix.split(",") if x.strip())
    df = storage.ls(args.prefix, limit=args.limit * 5)
    keys = [k for k in df["key"].tolist() if k.endswith(suffixes)][: args.limit]
    if not keys:
        print("조건에 맞는 객체가 없습니다. --prefix / --suffix 를 확인하세요.")
        return

    result = steps.index(keys)
    print(f"적재 완료: {result}")
    print(vectordb.stats())


if __name__ == "__main__":
    main()
