"""S3 → 로컬 캐시 동기화.

로컬에서 반복 실험할 데이터를 한 번에 내려받아 둔다. 이후 storage.fetch() 는
네트워크를 타지 않는다.

    python ops/sync_s3.py --prefix raw/2024/ --limit 50
"""

import argparse

from myagent import storage
from myagent.logging_setup import setup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max-mb", type=float, default=50.0, help="이보다 큰 객체는 건너뛴다")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    setup()
    df = storage.ls(args.prefix, limit=args.limit)
    if df.empty:
        print(f"'{args.prefix}' 에 객체가 없습니다.")
        return

    skipped = 0
    for row in df.itertuples():
        if row.size_mb > args.max_mb:
            skipped += 1
            continue
        path = storage.fetch(row.key, force=args.force)
        print(f"  {row.key}  ({row.size_mb} MB) -> {path}")

    print(f"\n{len(df) - skipped}개 동기화 완료, {skipped}개 건너뜀(용량 초과).")


if __name__ == "__main__":
    main()
