"""로컬과 App Service에 같은 입력을 던져 결과를 비교한다.

배포 후 제일 먼저 돌리는 것. /diag 를 나란히 보면 환경 차이가 바로 보인다.

    python ops/smoke.py --base http://localhost:8000 --base https://myagent.example.com
"""

import argparse
import json

import httpx

CASES = [
    "이 문서들에서 다루는 주제를 한 문장으로 요약해줘.",
]


def probe(base: str, token: str | None, timeout: float) -> None:
    print(f"\n=== {base} ===")
    headers = {"x-diag-token": token} if token else {}
    try:
        health = httpx.get(f"{base}/healthz", timeout=10).json()
        print("healthz:", health)
        diag = httpx.get(f"{base}/diag", headers=headers, timeout=20).json()
        print("diag   :", json.dumps(diag, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"진단 실패: {type(exc).__name__}: {exc}")
        return

    for case in CASES:
        try:
            resp = httpx.post(f"{base}/ask", json={"question": case}, timeout=timeout)
            body = resp.json()
            print(f"\nQ: {case}\n  status={resp.status_code} "
                  f"elapsed_ms={body.get('elapsed_ms')} sources={body.get('sources')}")
            print(f"  A: {str(body.get('answer'))[:300]}")
        except Exception as exc:
            print(f"  실패: {type(exc).__name__}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", action="append", default=None,
                        help="여러 번 주면 순서대로 비교한다")
    parser.add_argument("--token", default=None, help="DIAG_TOKEN")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    for base in (args.base or ["http://localhost:8000"]):
        probe(base.rstrip("/"), args.token, args.timeout)


if __name__ == "__main__":
    main()
