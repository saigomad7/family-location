"""단계들을 이어 붙인 얇은 조합 함수.

app/main.py 도, Spyder도, ops/smoke.py 도 전부 이 run() 하나를 호출한다.
그래서 "로컬에서는 되는데 App Service에서는 다르다"가 코드 차이에서 생길 수 없다.
"""

import logging
import time

from . import steps
from .logging_setup import log

logger = logging.getLogger(__name__)


def run(question: str, k: int = 5, stream: bool = False) -> dict:
    t0 = time.perf_counter()

    contexts = steps.retrieve(question, k=k)
    prompt = steps.build_prompt(question, contexts)
    out = steps.answer(prompt, stream=stream)

    result = {
        "answer": out["text"],
        "sources": [
            {"doc_id": c["doc_id"], "score": c["score"]} for c in contexts
        ],
        "usage": out["usage"],
        "model": out["model"],
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
    }
    log(
        logger,
        logging.INFO,
        "agent.run",
        question=question[:120],
        n_sources=len(contexts),
        elapsed_ms=result["elapsed_ms"],
        request_id_llm=out["request_id"],
    )
    return result
