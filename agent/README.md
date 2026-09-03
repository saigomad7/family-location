# myagent — 로컬(Spyder)에서 개발하고 App Service로 배포하는 AI 에이전트

사내 클라우드(App Service + S3 + Milvus)를 쓰면서도, **로컬에서 한 줄씩 실행하며
확인하는 개발 방식**을 유지하기 위한 뼈대입니다.

## 설계 원칙 3가지

1. **코드는 하나, 바뀌는 건 환경변수뿐.** 로컬용/클라우드용 코드를 나누지 않습니다.
   `if local:` 분기는 어댑터(`storage.py`, `vectordb.py`) 안에만 있고 호출부에는 없습니다.
2. **환경변수는 `config.py` 에서만 읽습니다.** 다른 파일에 `os.getenv` 가 생기는 순간
   로컬/클라우드 차이를 추적할 수 없게 됩니다.
3. **로직은 순수 함수(`steps.py`), 서버는 얇은 껍데기(`app/main.py`).**
   FastAPI 안에 로직을 쓰면 그 부분은 Spyder에서 실행할 수 없게 됩니다.

## 구조

```
agent/
├── src/myagent/
│   ├── config.py         환경변수의 유일한 진입점
│   ├── logging_setup.py  stdout JSON 로깅 (App Service 로그 스트림과 동일한 모양)
│   ├── storage.py        S3 어댑터 + 로컬 캐시 + ls() → DataFrame
│   ├── embeddings.py     로컬 모델 / 사내 HTTP API 전환
│   ├── vectordb.py       Milvus 어댑터, 스키마는 코드가 진실
│   ├── llm.py            Claude 호출 (adaptive thinking + effort)
│   ├── steps.py          ★ 에이전트 단계들. 전부 순수 함수
│   └── agent.py          steps 조합 = run()
├── app/main.py           App Service 진입점 (/ask /index /healthz /diag)
├── scratch/              ★ Spyder에서 셀 단위로 돌리는 개발용 스크립트
├── ops/                  sync_s3 / seed_milvus / smoke
├── tests/                외부 의존성 없는 계약 테스트
├── Dockerfile            App Service와 같은 런타임 재현
└── docker-compose.dev.yml  로컬 Milvus(+MinIO)
```

## 최초 1회 셋업

```bash
cd agent
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .                                       # myagent 를 어디서든 import 가능하게
cp .env.example .env.local                             # 값 채우기 (커밋 금지)
docker compose -f docker-compose.dev.yml up -d         # 로컬 Milvus
python ops/sync_s3.py   --prefix raw/ --limit 50       # S3 → 로컬 캐시
python ops/seed_milvus.py --prefix raw/ --limit 20     # 로컬 Milvus에 샘플 적재
```

Spyder에서는 **이 `.venv` 를 인터프리터로 지정**하고(도구 → 환경설정 → Python 인터프리터),
작업 디렉터리를 `agent/` 로 맞춥니다.

## 매일의 개발 루프 (Spyder)

1. 콘솔에서 `runfile('scratch/bootstrap.py')`
   → `%autoreload 2` 가 켜지고 현재 설정이 출력됩니다.
2. `scratch/explore_s3.py` 를 셀 단위로 실행 → **S3에 뭐가 있는지 표로 확인**
3. `scratch/dev_agent.py` 를 셀 단위로 실행 → 검색 / 프롬프트 / 답변을 **한 단계씩 확인**
4. 이상하면 `src/myagent/steps.py` 의 해당 함수만 고치고 저장 → **콘솔 재시작 없이**
   그 셀만 다시 실행

S3를 파일 탐색기처럼 보고 싶다면 마운트를 병행하세요(읽기 확인 전용, 실제 코드는
`storage.fetch()` 캐시를 사용):

```bash
rclone mount s3:my-bucket ~/s3mnt --read-only --vfs-cache-mode minimal
```

## App Service에서 잘 도는지 확인하는 3단 게이트

로컬에서 되던 게 클라우드에서 깨지는 원인은 거의 항상 ①의존성 버전 ②환경변수
③파일시스템 ④네트워크입니다. 순서대로 거릅니다.

**1단 — 로컬 프로세스** (Spyder에서 서버 없이도 가능)
```python
from fastapi.testclient import TestClient
from app.main import app
TestClient(app).post("/ask", json={"question": "..."}).json()
```
```bash
uvicorn app.main:app --reload      # 브라우저로 확인하려면
pytest -q                          # 배포 전 계약 테스트
```

**2단 — 도커** (여기서 의존성·경로 문제가 먼저 잡힙니다)
```bash
docker build -t myagent .
docker run --rm -p 8000:8000 --env-file .env.cloudlike myagent
```

**3단 — 배포 후 스모크** (두 환경을 나란히 비교)
```bash
python ops/smoke.py --base http://localhost:8000 \
                    --base https://myagent.<사내도메인> --token "$DIAG_TOKEN"
```

`/diag` 가 핵심입니다. "왜 클라우드에서만 다르지?"의 대부분은 버킷·컬렉션·버전
차이이고, 두 `/diag` 응답을 나란히 놓으면 몇 초 만에 드러납니다. 비밀값은 담지
않으며, 배포 시 `DIAG_TOKEN` 을 반드시 설정하세요.

## App Service 배포 시 주의

| 항목 | 내용 |
|---|---|
| 디스크 | **휘발성.** 재시작하면 사라집니다. 캐시는 `CACHE_DIR=/tmp/cache`, 남길 산출물은 반드시 `storage.put()` 으로 S3에 |
| 프로세스 상태 | 워커가 여러 개면 전역 dict 캐시는 워커마다 다릅니다. `lru_cache` 는 커넥션 정도까지만 |
| 타임아웃 | 요청 타임아웃보다 긴 작업은 `202 + job_id` 비동기 패턴으로. LLM 호출은 `stream=True` 로 |
| 포트 | 컨테이너는 `PORT` 환경변수를 따릅니다(Dockerfile에 반영됨) |
| 시크릿 | `.env.local` 은 커밋 금지. 클라우드는 App Settings / Key Vault |
| 네트워크 | 노트북 → 사내 Milvus 는 막히는 경우가 많아 로컬은 도커 Milvus 를 기본으로 둡니다 |
| 임베딩 모델 | 로컬과 클라우드가 **같은 모델·같은 차원**이어야 합니다. 다르면 에러 없이 결과만 이상해집니다 |

## 바꿔야 할 곳

- `steps.py` 의 `SYSTEM` 프롬프트와 `chunk()` 전략 — 실제 데이터에 맞게
- `embeddings.py` — 사내 임베딩 API가 있으면 `EMBED_PROVIDER=http` + `EMBED_ENDPOINT`
- `llm.py` — 사내 게이트웨이를 경유하면 `ANTHROPIC_BASE_URL`
- `requirements.txt` — 버전 핀은 그대로 두세요. 로컬/클라우드 드리프트의 주범입니다
