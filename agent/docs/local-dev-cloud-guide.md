# 클라우드 AI 에이전트를 로컬에서 한 줄씩 확인하며 개발하는 방법

> **대상**: 사내 클라우드(App Service + S3 + Milvus)에 AI 에이전트를 올리려 하지만,
> 개발은 로컬 IDE(Spyder / VS Code Interactive / Jupyter)에서 한 단계씩 실행하며
> 눈으로 확인하는 방식을 유지하고 싶은 개발자.
>
> **다루는 것**: 로컬과 클라우드가 같은 코드를 돌리게 만드는 구조, S3 데이터를
> 로컬에서 다루는 법, 로컬 Milvus 구성, 배포 전 3단 검증, 배포 시 함정.
>
> **다루지 않는 것**: 특정 벤더의 App Service 설정 화면, 사내 네트워크 정책,
> 모델 선택·프롬프트 엔지니어링 자체.

---

## 목차

1. [문제 정의](#1-문제-정의)
2. [핵심 원칙 3가지](#2-핵심-원칙-3가지)
3. [전체 구조](#3-전체-구조)
4. [디렉터리 레이아웃](#4-디렉터리-레이아웃)
5. [계층별 구현](#5-계층별-구현)
6. [로컬 개발 루프](#6-로컬-개발-루프)
7. [S3를 눈으로 보는 3가지 방법](#7-s3를-눈으로-보는-3가지-방법)
8. [로컬 Milvus](#8-로컬-milvus)
9. [배포 전 3단 검증 게이트](#9-배포-전-3단-검증-게이트)
10. [App Service 배포 시 함정](#10-app-service-배포-시-함정)
11. [트러블슈팅](#11-트러블슈팅)
12. [도입 체크리스트](#12-도입-체크리스트)

---

## 1. 문제 정의

클라우드 기반 에이전트를 개발할 때 흔히 겪는 상황:

- 데이터는 S3에 있는데, 매번 클라우드에 배포해야 결과를 볼 수 있다.
- 배포 → 로그 확인 → 수정 → 재배포 사이클이 한 번에 5~10분씩 걸린다.
- 중간 단계(무엇이 검색되었는지, 프롬프트가 어떻게 만들어졌는지)를 볼 방법이 없다.
- "로컬에서는 됐는데 클라우드에서는 안 되는" 문제가 배포 후에야 드러난다.

목표는 **로컬에서 한 단계씩 실행하며 개발하되, 그 코드가 App Service에서 그대로
동작한다는 확신을 유지하는 것**이다.

### 흔한 실패 패턴 두 가지

| 실패 패턴 | 왜 실패하는가 |
|---|---|
| "로컬용 스크립트"와 "배포용 코드"를 따로 관리 | 두 벌이 서서히 갈라진다. 로컬에서 검증한 것이 배포된 것과 다르므로 검증이 무의미해진다 |
| FastAPI 핸들러 안에 로직을 직접 작성 | 그 로직은 HTTP 요청 없이는 실행할 수 없다. 한 단계씩 확인하는 개발이 원천적으로 불가능해진다 |

---

## 2. 핵심 원칙 3가지

### 원칙 1 — 코드는 하나, 바뀌는 것은 환경변수뿐

로컬과 클라우드는 **동일한 코드**를 실행한다. 달라지는 것은 `.env` / App Settings에
담긴 값뿐이다. `if 로컬:` 같은 분기는 어댑터 내부에만 존재하고, 호출하는 쪽에는
절대 나타나지 않는다.

### 원칙 2 — 환경변수는 한 곳에서만 읽는다

`config.py` 외의 파일에 `os.getenv`가 하나라도 생기면, 두 환경의 차이를 추적할 수
없게 된다. 설정 항목이 늘어날수록 이 원칙의 가치가 커진다.

### 원칙 3 — 로직은 순수 함수, 서버는 얇은 껍데기

에이전트의 각 단계는 **인자를 받아 값을 돌려주는 함수**로 작성한다.
웹 프레임워크는 그 함수를 호출하기만 하는 30줄짜리 껍데기로 유지한다.

```
좋음:  steps.retrieve(question, k=5) -> list[dict]      # Spyder에서 바로 실행 가능
나쁨:  @app.post("/ask") 안에서 검색·프롬프트·호출을 모두 처리   # HTTP 없이는 실행 불가
```

이 원칙 하나가 "한 줄씩 보며 개발"의 가능 여부를 결정한다.

---

## 3. 전체 구조

```
┌─────────────────────── 로컬 개발 환경 ───────────────────────┐
│                                                              │
│  IDE 셀 실행 ──▶ src/myagent/steps.py  (순수 함수)           │
│      │                    │                                  │
│      │                    ├──▶ 로컬 캐시 ./data/cache         │
│      │                    │         ▲                        │
│      │                    │         │ ops/sync_s3.py         │
│      │                    │         │                        │
│      │                    └──▶ 로컬 Milvus (docker)          │
│      │                              ▲                        │
│      │                              │ ops/seed_milvus.py     │
│      │                                                       │
│      └──▶ TestClient ──▶ app/main.py (얇은 껍데기)            │
│                              │                               │
└──────────────────────────────┼───────────────────────────────┘
                               │  docker build / 배포
                               ▼
┌────────────────────── App Service ───────────────────────────┐
│   app/main.py ──▶ 동일한 src/myagent/steps.py                │
│                        │                                     │
│                        ├──▶ 사내 S3 (실데이터)                │
│                        └──▶ 사내 Milvus (전체 색인)           │
└──────────────────────────────────────────────────────────────┘
                               ▲
                    ops/smoke.py 가 양쪽에 같은 입력을 던져 비교
```

읽는 법: **가로선 위와 아래가 같은 `steps.py`를 호출한다.** 데이터 소스만
로컬 캐시/로컬 Milvus ↔ 사내 S3/사내 Milvus로 갈린다.

---

## 4. 디렉터리 레이아웃

```
agent/
├── src/myagent/
│   ├── config.py          환경변수의 유일한 진입점
│   ├── logging_setup.py   stdout JSON 로깅 (로컬 콘솔 = 클라우드 로그 스트림)
│   ├── storage.py         S3 어댑터 + 로컬 캐시
│   ├── embeddings.py      임베딩 어댑터 (로컬 모델 / 사내 API)
│   ├── vectordb.py        Milvus 어댑터 (스키마는 코드가 진실)
│   ├── llm.py             LLM 클라이언트
│   ├── steps.py           ★ 에이전트 단계들. 전부 순수 함수
│   └── agent.py           steps 조합 = run()
│
├── app/main.py            App Service 진입점 (/ask /index /healthz /diag)
│
├── scratch/               ★ 로컬 개발용 셀 스크립트 (배포에 포함되지 않음)
│   ├── bootstrap.py       세션 시작 (autoreload + 설정 출력)
│   ├── explore_s3.py      S3를 표로 보기
│   └── dev_agent.py       에이전트를 한 단계씩
│
├── ops/
│   ├── sync_s3.py         S3 → 로컬 캐시 동기화
│   ├── seed_milvus.py     로컬 Milvus에 샘플 적재
│   └── smoke.py           로컬 ↔ 배포 동일 입력 비교
│
├── tests/                 외부 의존성 없는 계약 테스트
├── Dockerfile             App Service와 동일 런타임 재현
├── docker-compose.dev.yml 로컬 Milvus (+ MinIO)
├── requirements.txt       버전 핀 고정
├── pyproject.toml         pip install -e . 로 어디서든 import 가능
└── .env.example           .env.local 로 복사해 사용 (커밋 금지)
```

`scratch/`와 `src/`를 나누는 것이 중요하다. **`scratch/`는 버려도 되는 실험,
`src/`는 배포되는 자산**이다. 실험이 굳으면 `src/`의 함수로 옮긴다.

---

## 5. 계층별 구현

### 5.1 설정 — `config.py`

```python
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 뒤쪽 파일이 앞쪽을 덮어쓴다 → 개인 설정(.env.local)이 팀 공용(.env)을 이긴다.
    # App Service에는 파일이 없고 실제 환경변수가 그대로 이긴다. 분기 불필요.
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"), env_file_encoding="utf-8", extra="ignore"
    )

    env: str = "local"                      # local | cloud

    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    cache_dir: str = "./data/cache"         # 클라우드에서는 /tmp/cache

    milvus_uri: str = "http://localhost:19530"
    milvus_collection: str = "docs"
    embed_dim: int = 384

    log_level: str = "INFO"
    diag_token: str = ""
    git_sha: str = "dev"

    @property
    def cache_path(self) -> Path:
        return Path(self.cache_dir).expanduser()

    def require(self, *names: str) -> None:
        """빈 설정을 조용히 넘어가지 않게 한다. 클라우드에서 가장 흔한 사고 지점."""
        missing = [n for n in names if not getattr(self, n)]
        if missing:
            raise RuntimeError(
                f"설정 누락: {', '.join(missing)}. "
                f"로컬이면 .env.local, App Service면 App Settings를 확인하세요."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """.env.local 수정 후 IDE 콘솔을 재시작하지 않고 반영할 때."""
    get_settings.cache_clear()
    return get_settings()
```

`require()`가 있는 이유: 환경변수 하나가 비어 있으면 보통 **엉뚱한 기본값으로
조용히 동작**하다가 한참 뒤에 이상한 결과로 드러난다. 시작 지점에서 크게 터지는
편이 훨씬 싸다.

### 5.2 S3 어댑터 — `storage.py`

핵심은 **캐시를 어댑터 안에 숨기는 것**이다. 호출부는 로컬인지 클라우드인지 모른다.

```python
import boto3
from botocore.config import Config
from functools import lru_cache
from pathlib import Path
from .config import get_settings


@lru_cache
def client():
    s = get_settings()
    s.require("s3_endpoint", "s3_bucket", "s3_access_key", "s3_secret_key")
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        # 사내 MinIO / Ceph 계열은 path-style 이 안전하다
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
    )


def fetch(key: str, force: bool = False) -> Path:
    """S3 객체를 로컬 파일로 확보하고 경로를 돌려준다. 있으면 캐시를 쓴다."""
    s = get_settings()
    dst = s.cache_path / key
    if dst.exists() and not force:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")   # 중간에 끊겨도 캐시가 오염되지 않게
    client().download_file(s.s3_bucket, key, str(tmp))
    tmp.replace(dst)
    return dst


def iter_keys(prefix: str = ""):
    s = get_settings()
    paginator = client().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=s.s3_bucket, Prefix=prefix):
        yield from page.get("Contents", [])


def ls(prefix: str = "", limit: int = 1000):
    """버킷 목록을 DataFrame으로. IDE 변수 탐색기에서 표로 열어 보기 위한 함수."""
    import pandas as pd

    rows = []
    for i, obj in enumerate(iter_keys(prefix)):
        if i >= limit:
            break
        rows.append({
            "key": obj["Key"],
            "size_mb": round(obj["Size"] / 1e6, 4),
            "modified": obj["LastModified"],
        })
    df = pd.DataFrame(rows, columns=["key", "size_mb", "modified"])
    return df.sort_values("modified", ascending=False).reset_index(drop=True)


def put(key: str, path) -> str:
    """결과물을 S3에 올린다.

    App Service의 디스크는 휘발성이다. 남겨야 할 산출물은 로컬 파일이 아니라
    반드시 이 함수를 거쳐야 한다.
    """
    s = get_settings()
    client().upload_file(str(path), s.s3_bucket, key)
    return f"s3://{s.s3_bucket}/{key}"
```

`.part` 임시 파일을 거치는 이유: 다운로드 중 연결이 끊기면 잘린 파일이 캐시에 남고,
다음 실행부터 그 잘린 파일을 조용히 사용하게 된다.

### 5.3 벡터 DB 어댑터 — `vectordb.py`

**스키마 정의를 코드에 둔다.** 콘솔에서 손으로 컬렉션을 만들면 로컬과 클라우드가
갈라지고, 그 차이는 검색 결과가 이상해질 때까지 드러나지 않는다.

```python
from functools import lru_cache
from pymilvus import DataType, MilvusClient
from .config import get_settings

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
    name, c = s.milvus_collection, client()

    if drop and c.has_collection(name):
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
    index_params.add_index(field_name="vector", index_type="AUTOINDEX",
                           metric_type="COSINE")

    c.create_collection(collection_name=name, schema=schema, index_params=index_params)
    return name


def search(vector: list[float], k: int = 5, expr: str | None = None) -> list[dict]:
    s = get_settings()
    hits = client().search(
        collection_name=s.milvus_collection,
        data=[vector], limit=k, filter=expr or "",
        output_fields=["doc_id", "source_key", "chunk_idx", "text"],
    )
    return [{"score": round(float(h["distance"]), 4), **h["entity"]} for h in hits[0]]


def stats() -> dict:
    """지금 어떤 Milvus의 어떤 컬렉션을 보고 있는지 확인 (/diag 와 IDE에서 사용)."""
    s = get_settings()
    c = client()
    info = {"uri": s.milvus_uri, "collections": c.list_collections()}
    if c.has_collection(s.milvus_collection):
        info["collection"] = s.milvus_collection
        info["num_entities"] = c.get_collection_stats(s.milvus_collection).get("row_count")
    return info
```

### 5.4 임베딩 어댑터 — `embeddings.py`

로컬과 클라우드가 **같은 모델·같은 차원**을 써야 한다. 다르면 에러 없이 검색
결과만 이상해진다. 그래서 차원을 명시적으로 검증한다.

```python
def embed(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    if not texts:
        return []

    if s.embed_provider == "local":
        out = [v.tolist() for v in _local_model().encode(texts, normalize_embeddings=True)]
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
```

### 5.5 에이전트 로직 — `steps.py`

**여기가 이 문서 전체의 핵심이다.** 지켜야 할 규칙 세 가지:

1. 필요한 것은 전부 인자로 받는다 (전역 상태 금지)
2. 결과는 `dict` / `list[dict]` / `DataFrame`으로 돌려준다 (변수 탐색기에서 열린다)
3. 프레임워크 콜백이나 클래스 내부에 로직을 숨기지 않는다

```python
def load_docs(keys: list[str]) -> list[dict]: ...
def chunk(docs: list[dict], size=800, overlap=100) -> list[dict]: ...
def embed_chunks(chunks: list[dict]) -> list[dict]: ...
def index(keys: list[str]) -> dict: ...

def retrieve(question: str, k: int = 5, expr: str | None = None) -> list[dict]: ...
def build_prompt(question: str, contexts: list[dict]) -> str: ...
def answer(prompt: str, stream: bool = False) -> dict: ...
```

`build_prompt`가 문자열을 **그대로 반환**하는 것이 중요하다. LLM에 보내기 전에
프롬프트를 눈으로 확인할 수 있고, 실제로 문제의 상당수가 이 지점에서 드러난다.

### 5.6 조합 — `agent.py`

```python
def run(question: str, k: int = 5, stream: bool = False) -> dict:
    contexts = steps.retrieve(question, k=k)
    prompt = steps.build_prompt(question, contexts)
    out = steps.answer(prompt, stream=stream)
    return {
        "answer": out["text"],
        "sources": [{"doc_id": c["doc_id"], "score": c["score"]} for c in contexts],
        "usage": out["usage"],
        "elapsed_ms": ...,
    }
```

IDE도, FastAPI도, 스모크 테스트도 **전부 이 `run()` 하나**를 호출한다. 그래서
"로컬에서는 되는데 클라우드에서는 다르다"가 코드 차이에서 생길 수 없다.

### 5.7 서버 껍데기 — `app/main.py`

```python
app = FastAPI(title="myagent", version=__version__)


@app.post("/ask")
def ask(body: AskRequest):
    logging_setup.new_request_id()
    return run(body.question, k=body.k)


@app.get("/healthz")
def healthz():
    """살아 있는지만 본다. 외부 의존성을 건드리지 않아야 배포 헬스체크가 안정적이다."""
    return {"ok": True, "version": __version__}


@app.get("/diag")
def diag(x_diag_token: str | None = Header(default=None)):
    """로컬과 클라우드가 정말 같은 환경인지 비교하는 창구."""
    if settings.diag_token and x_diag_token != settings.diag_token:
        raise HTTPException(status_code=403, detail="diag token mismatch")

    try:
        milvus = vectordb.stats()
    except Exception as exc:          # 진단 엔드포인트는 실패해도 응답은 줘야 한다
        milvus = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "env": settings.env,
        "git_sha": settings.git_sha,
        "python": sys.version.split()[0],
        "s3": {"endpoint": settings.s3_endpoint, "bucket": settings.s3_bucket},
        "cache_dir": str(settings.cache_path),
        "milvus": milvus,
        "embed": {"provider": settings.embed_provider,
                  "model": settings.embed_model, "dim": settings.embed_dim},
        "llm": {"model": settings.llm_model},
    }
```

**`/diag`는 이 구조에서 가장 투자 대비 효과가 큰 30줄이다.** "왜 클라우드에서만
다르지?"의 대부분은 버킷·컬렉션·모델·버전 차이이고, 두 환경의 `/diag` 응답을
나란히 놓으면 몇 초 만에 드러난다.

두 가지를 지킬 것:

- **비밀값은 절대 담지 않는다.** 이름·개수·엔드포인트까지만.
- **배포 시 `DIAG_TOKEN`을 설정한다.** 내부 설정 구조가 노출되는 엔드포인트다.
- **진단 대상이 죽어도 진단은 응답해야 한다.** Milvus 연결 실패를 예외로 던지면
  정작 "Milvus가 안 붙는다"는 사실을 확인할 창구가 사라진다.

---

## 6. 로컬 개발 루프

### 최초 1회

```bash
cd agent
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .                                      # myagent 를 어디서든 import 가능하게
cp .env.example .env.local                            # 값 채우기 (커밋 금지)

docker compose -f docker-compose.dev.yml up -d        # 로컬 Milvus
python ops/sync_s3.py    --prefix raw/ --limit 50     # S3 → 로컬 캐시
python ops/seed_milvus.py --prefix raw/ --limit 20    # 로컬 Milvus에 샘플 적재
```

IDE에서는 이 `.venv`를 인터프리터로 지정하고 작업 디렉터리를 `agent/`로 맞춘다.
(Spyder: 도구 → 환경설정 → Python 인터프리터)

### 세션 시작 — `scratch/bootstrap.py`

```python
from IPython import get_ipython

ipy = get_ipython()
if ipy is not None:
    ipy.run_line_magic("load_ext", "autoreload")
    ipy.run_line_magic("autoreload", "2")

from myagent.config import get_settings, reload_settings
from myagent.logging_setup import setup

s = get_settings()
setup(s.log_level)
print(f"ENV={s.env}")
print(f"S3    : {s.s3_endpoint} / {s.s3_bucket}")
print(f"MILVUS: {s.milvus_uri} / {s.milvus_collection} (dim={s.embed_dim})")
print(f"CACHE : {s.cache_path.resolve()}")
```

`%autoreload 2`가 이 워크플로의 절반이다. `src/myagent/*.py`를 고치고 저장하면
**콘솔을 재시작하지 않고** 다음 셀에서 바로 반영된다.

세션 시작 시 어떤 환경을 보고 있는지 출력하는 것도 중요하다. `.env.local`을
바꿔 놓고 잊은 채 몇 시간을 헤매는 일이 자주 생긴다.

### 개발 — `scratch/dev_agent.py`

```python
# %% 준비
from myagent import steps, storage, vectordb
from myagent.agent import run

q = "여기에 실제 질문"

# %% 컬렉션 상태 확인
vectordb.ensure_collection()
vectordb.stats()

# %% 1단계: 검색만 — 무엇이 걸렸는지 ctx 를 변수 탐색기에서 확인
ctx = steps.retrieve(q, k=5)
[(c["doc_id"], c["score"]) for c in ctx]

# %% 2단계: 프롬프트 — LLM에 보내기 전에 눈으로 본다 (문제가 제일 많이 보이는 지점)
prompt = steps.build_prompt(q, ctx)
print(prompt[:2000])

# %% 3단계: 답변 — 토큰/모델/요청ID까지 dict 로 돌아온다
out = steps.answer(prompt)
print(out["text"]); out["usage"]

# %% 전체 파이프라인 (App Service가 실제로 부르는 것과 동일한 함수)
res = run(q)

# %% HTTP 계층까지 검증 — 서버를 띄우지 않고 라우팅/스키마 확인
from fastapi.testclient import TestClient
from app.main import app
TestClient(app).post("/ask", json={"question": q}).json()
```

**루프는 이렇게 돈다**: 셀을 위에서부터 실행 → 이상한 단계 발견 → `src/steps.py`의
해당 함수만 수정 → 저장 → **그 셀만** 다시 실행. 서버 재시작도, 배포도 없다.

마지막 `TestClient` 셀이 중요하다. 서버를 띄우지 않고도 라우팅·요청 스키마·직렬화
문제를 잡아낸다. 실제 배포 후 발생하는 오류의 상당수가 이 계층에서 생긴다.

---

## 7. S3를 눈으로 보는 3가지 방법

셋을 함께 쓰는 것을 권한다. 목적이 다르다.

| 방법 | 용도 | 비고 |
|---|---|---|
| 사내 S3 웹 콘솔 (MinIO Console 등) | 전체 구조 훑기, 권한 확인 | 브라우저 필요 |
| `storage.ls("prefix/")` → 변수 탐색기 | 개발 중 표로 확인, 필터·집계 | **가장 자주 쓰게 됨** |
| `rclone mount` / `s3fs` | IDE 파일 탐색기에서 폴더처럼 | 읽기 확인 전용 |

```bash
rclone mount s3:my-bucket ~/s3mnt --read-only --vfs-cache-mode minimal
```

마운트는 IDE 습관에 가장 잘 맞지만 **느리고 끊긴다**. 눈으로 확인하는 용도로만
쓰고, 실제 코드는 반드시 `storage.fetch()`의 캐시를 경유하게 한다.

```python
df = storage.ls("raw/", limit=500)
df.groupby(df["key"].str.split("/").str[1]).size()   # 하위 디렉터리별 객체 수
df[df["size_mb"] > 10]                                 # 큰 파일만
```

---

## 8. 로컬 Milvus

### 왜 사내 Milvus에 직접 붙지 않는가

- 노트북 → 사내 Milvus는 방화벽/VPN 때문에 막히거나 느린 경우가 많다.
- 실험 중 컬렉션을 지우고 다시 만드는 일이 잦은데, 공용 인스턴스에서는 위험하다.
- 수백~수천 건 샘플이면 반복 실험이 몇 초로 끝난다. 전체 색인은 필요 없다.

### 구성

```yaml
# docker-compose.dev.yml — Milvus standalone (etcd + MinIO + milvus)
services:
  etcd:    { image: quay.io/coreos/etcd:v3.5.16, ... }
  minio:   { image: minio/minio:..., ports: ["9000:9000", "9001:9001"] }
  milvus:
    image: milvusdb/milvus:v2.5.0
    command: ["milvus", "run", "standalone"]
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    ports: ["19530:19530", "9091:9091"]
    depends_on: [etcd, minio]
```

```bash
docker compose -f docker-compose.dev.yml up -d      # 시작
docker compose -f docker-compose.dev.yml down       # 중지 (데이터 유지)
docker compose -f docker-compose.dev.yml down -v    # 초기화
```

> Milvus 내부 저장소로 쓰이는 MinIO는 **사내 S3와 별개**다. 다만 이 MinIO를
> 사내 S3의 로컬 대역으로 활용할 수도 있다(콘솔 `http://localhost:9001`).

### 스키마 동기화

`vectordb.ensure_collection()`이 로컬·클라우드 양쪽에서 같은 스키마를 만든다.
클라우드에 배포할 때도 이 함수를 거치게 하면 두 환경이 갈라지지 않는다.

---

## 9. 배포 전 3단 검증 게이트

로컬에서 되던 것이 클라우드에서 깨지는 원인은 거의 항상 넷 중 하나다:
**①의존성 버전 ②환경변수 ③파일시스템 ④네트워크.** 순서대로 거른다.

### 1단 — 로컬 프로세스

```python
# IDE 셀에서 (서버 없이)
from fastapi.testclient import TestClient
from app.main import app
TestClient(app).post("/ask", json={"question": "..."}).json()
```

```bash
uvicorn app.main:app --reload    # 브라우저로 확인할 때
pytest -q                        # 외부 의존성 없는 계약 테스트
```

여기서 잡히는 것: 로직 오류, 라우팅, 요청/응답 스키마.

### 2단 — 도커 (App Service와 같은 베이스 이미지)

```bash
docker build -t myagent .
docker run --rm -p 8000:8000 --env-file .env.cloudlike myagent
```

```dockerfile
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 CACHE_DIR=/tmp/cache
WORKDIR /app
COPY requirements.txt pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .
COPY app ./app
# App Service는 보통 PORT 환경변수로 포트를 지정한다
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

여기서 잡히는 것: **의존성 버전 드리프트, 경로 문제, 누락된 OS 패키지.**
로컬 프로세스만 믿으면 이것들을 배포 후에야 발견한다. 이 단계를 건너뛰지 말 것.

### 3단 — 배포 후 스모크

```bash
python ops/smoke.py --base http://localhost:8000 \
                    --base https://myagent.<사내도메인> \
                    --token "$DIAG_TOKEN"
```

`ops/smoke.py`는 두 환경의 `/diag`를 출력하고, 같은 질문 목록을 양쪽에 던져
응답을 나란히 보여준다. **차이가 보이면 거의 항상 `/diag`에 원인이 이미 찍혀 있다.**

### 게이트 요약

| 단계 | 무엇을 잡는가 | 소요 |
|---|---|---|
| 1단 로컬 | 로직, 라우팅, 스키마 | 초 |
| 2단 도커 | 의존성, 경로, OS 패키지 | 분 |
| 3단 스모크 | 환경변수, 네트워크, 권한 | 분 |

---

## 10. App Service 배포 시 함정

| 항목 | 내용 | 대응 |
|---|---|---|
| **디스크 휘발성** | 컨테이너 재시작 시 로컬 파일이 사라진다 | 캐시는 `/tmp`만. 남길 산출물·대화 이력·색인은 반드시 S3/Milvus/DB |
| **프로세스 상태** | 워커가 여러 개면 전역 `dict` 캐시가 워커마다 다르다 | `lru_cache`는 커넥션 정도까지만. 상태는 외부 저장소로 |
| **요청 타임아웃** | 보통 수 분. 긴 에이전트 작업은 잘린다 | `202 + job_id` 비동기 패턴. LLM 호출은 스트리밍 |
| **콜드 스타트** | 첫 요청이 느리다 (모델 로딩 등) | 무거운 초기화는 지연 로딩 + 헬스체크는 외부 의존성 배제 |
| **포트** | 플랫폼이 `PORT` 환경변수로 지정 | `--port ${PORT:-8000}` |
| **시크릿** | 코드·이미지에 넣으면 유출 | App Settings / Key Vault. `.env.local`은 `.gitignore` |
| **로그** | `print`는 버퍼링되어 안 보일 수 있다 | stdout JSON 로깅 + `PYTHONUNBUFFERED=1` |
| **네트워크 방향** | App Service → Milvus는 되지만 노트북 → Milvus는 막힐 수 있다 | 로컬은 도커 Milvus 기본. S3는 읽기 전용 키로 직접 확인 |
| **임베딩 모델 불일치** | 에러 없이 결과만 이상해진다 | 차원을 명시 검증. 컬렉션에 모델 이름 기록 |

### 로깅 — 로컬 콘솔과 클라우드 로그를 같은 모양으로

```python
class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": ..., "level": record.levelname, "logger": record.name,
            "request_id": request_id_var.get(),   # ContextVar
            "msg": record.getMessage(),
        }
        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False)
```

`request_id`를 넣어두면 클라우드 로그에서 특정 요청만 뽑아 로컬에서 같은 입력으로
재현하기가 쉬워진다. HTTP 클라이언트(`httpx`, `botocore`)의 로그는 `WARNING`으로
낮춰야 우리 로그가 묻히지 않는다.

---

## 11. 트러블슈팅

| 증상 | 가장 흔한 원인 | 확인 방법 |
|---|---|---|
| 클라우드에서만 결과가 다르다 | 버킷 / 컬렉션 / 모델이 다름 | 양쪽 `/diag` 비교 |
| 검색 결과가 이상한데 에러는 없다 | 색인과 질의의 임베딩 모델이 다름 | `/diag`의 `embed.model`, `embed.dim` |
| 로컬은 되는데 도커에서 실패 | 의존성 버전 / OS 패키지 누락 | 2단 게이트에서 재현 |
| 재시작하면 데이터가 사라진다 | 로컬 파일에 상태를 저장 | `CACHE_DIR` 외 쓰기 지점을 전부 점검 |
| 요청이 중간에 끊긴다 | 요청 타임아웃 초과 | 스트리밍 또는 비동기 잡으로 전환 |
| 로그가 안 보인다 | 버퍼링 | `PYTHONUNBUFFERED=1` |
| 워커마다 다르게 동작한다 | 프로세스 전역 상태 | 상태를 외부 저장소로 이동 |
| 캐시 파일이 깨져 있다 | 다운로드 중 연결 끊김 | `.part` 임시 파일 패턴 적용 |

---

## 12. 도입 체크리스트

**구조**

- [ ] `os.getenv`가 `config.py` 밖에 없다
- [ ] `app/main.py`에 로직이 없다 (라우팅과 검증만)
- [ ] `steps.py`의 모든 함수를 인자만으로 호출할 수 있다
- [ ] Milvus 스키마가 코드에 정의되어 있다 (콘솔 수작업 없음)
- [ ] `requirements.txt`가 버전 핀 고정 상태다

**로컬 환경**

- [ ] `pip install -e .` 로 어디서든 `import myagent` 가 된다
- [ ] IDE가 프로젝트 `.venv`를 인터프리터로 쓰고 있다
- [ ] `%autoreload 2`가 켜진다 (`scratch/bootstrap.py`)
- [ ] 로컬 Milvus가 뜬다
- [ ] S3 목록이 표로 보인다

**검증**

- [ ] `pytest -q` 가 외부 의존성 없이 통과한다
- [ ] 도커 빌드·실행이 된다
- [ ] `/healthz`가 외부 의존성을 건드리지 않는다
- [ ] `/diag`가 비밀값을 노출하지 않고, 의존성이 죽어도 응답한다
- [ ] `ops/smoke.py`로 두 환경을 비교할 수 있다

**배포**

- [ ] `.env.local`이 `.gitignore`에 있다
- [ ] 클라우드 `CACHE_DIR`이 `/tmp` 계열이다
- [ ] `DIAG_TOKEN`이 설정되어 있다
- [ ] 로컬 파일에 영구 상태를 쓰는 코드가 없다
- [ ] `GIT_SHA`가 주입되어 `/diag`에서 배포 버전을 확인할 수 있다

---

## 부록: 최소 환경변수 목록

```bash
ENV=local                       # local | cloud

S3_ENDPOINT=https://s3.internal.example.com
S3_BUCKET=my-bucket
S3_ACCESS_KEY=
S3_SECRET_KEY=

CACHE_DIR=./data/cache          # 클라우드: /tmp/cache

MILVUS_URI=http://localhost:19530   # 클라우드: 사내 Milvus 주소
MILVUS_COLLECTION=docs
EMBED_DIM=384                   # 임베딩 모델의 실제 차원과 반드시 일치

EMBED_PROVIDER=local            # local | http
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBED_ENDPOINT=                 # EMBED_PROVIDER=http 일 때

LOG_LEVEL=INFO
DIAG_TOKEN=                     # 배포 시 반드시 설정
GIT_SHA=dev                     # CI에서 주입
```

---

## 한 줄 요약

> **같은 `steps.py`를 IDE도, 도커도, App Service도 호출한다. 바뀌는 것은 `.env`뿐이다.**
