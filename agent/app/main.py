"""App Service 진입점 — 얇은 껍데기.

여기에 로직을 쓰지 말 것. 로직이 여기 들어오는 순간 Spyder에서 그 부분만
따로 실행할 수 없게 되고, 그때부터 "로컬에서 확인하며 개발"이 불가능해진다.
"""

import logging

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from myagent import __version__, logging_setup
from myagent.agent import run
from myagent.config import get_settings

settings = get_settings()
logging_setup.setup(settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="myagent", version=__version__)


class AskRequest(BaseModel):
    question: str
    k: int = 5


class IndexRequest(BaseModel):
    keys: list[str]


@app.post("/ask")
def ask(body: AskRequest):
    logging_setup.new_request_id()
    return run(body.question, k=body.k)


@app.post("/index")
def index(body: IndexRequest):
    from myagent import steps

    logging_setup.new_request_id()
    return steps.index(body.keys)


@app.get("/healthz")
def healthz():
    """살아 있는지만 본다. 외부 의존성을 건드리지 않아야 배포 헬스체크가 안정적이다."""
    return {"ok": True, "version": __version__}


@app.get("/diag")
def diag(x_diag_token: str | None = Header(default=None)):
    """로컬과 클라우드가 정말 같은 환경인지 비교하는 창구.

    "왜 클라우드에서만 결과가 다르지?"의 대부분은 버킷/컬렉션/버전 차이다.
    여기서 두 환경의 응답을 나란히 놓고 보면 몇 초 만에 드러난다.
    비밀값은 절대 넣지 않는다 — 이름과 개수만.
    """
    import sys

    from myagent import vectordb

    if settings.diag_token and x_diag_token != settings.diag_token:
        raise HTTPException(status_code=403, detail="diag token mismatch")

    try:
        milvus = vectordb.stats()
    except Exception as exc:  # 진단 엔드포인트는 실패해도 응답은 줘야 한다
        milvus = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "env": settings.env,
        "version": __version__,
        "git_sha": settings.git_sha,
        "python": sys.version.split()[0],
        "s3": {"endpoint": settings.s3_endpoint, "bucket": settings.s3_bucket},
        "cache_dir": str(settings.cache_path),
        "milvus": milvus,
        "embed": {
            "provider": settings.embed_provider,
            "model": settings.embed_model,
            "dim": settings.embed_dim,
        },
        "llm": {"model": settings.llm_model, "effort": settings.llm_effort},
    }
