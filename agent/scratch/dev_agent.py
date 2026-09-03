"""에이전트를 한 단계씩 돌려보는 셀 스크립트 — 실제 개발은 여기서 한다.

셀을 위에서부터 Ctrl+Enter 로 실행하고, 각 결과를 변수 탐색기에서 확인한다.
이상하면 src/myagent/steps.py 의 해당 함수만 고치고, 저장한 뒤 그 셀만
다시 실행한다(autoreload가 반영해 준다).
"""

# %% 준비
from myagent import embeddings, steps, storage, vectordb
from myagent.agent import run

q = "여기에 실제 질문을 넣으세요"

# %% 컬렉션 상태 확인
vectordb.ensure_collection()
vectordb.stats()

# %% (최초 1회) 샘플 색인 — 터미널의 ops/seed_milvus.py 와 같은 일
keys = storage.ls("raw/", limit=20)["key"].tolist()[:5]
steps.index(keys)

# %% 1단계: 검색만 — 무엇이 걸렸는지 ctx 를 눌러서 확인
ctx = steps.retrieve(q, k=5)
[(c["doc_id"], c["score"]) for c in ctx]

# %% 2단계: 프롬프트 — LLM에 보내기 전에 눈으로 본다 (여기서 문제가 제일 많이 보인다)
prompt = steps.build_prompt(q, ctx)
print(prompt[:2000])

# %% 3단계: 답변 — 토큰/모델/요청ID까지 dict 로 돌아온다
out = steps.answer(prompt)
print(out["text"])
out["usage"]

# %% 전체 파이프라인 (App Service가 실제로 부르는 것과 동일한 함수)
res = run(q)
res

# %% HTTP 계층까지 검증 — 서버를 띄우지 않고 라우팅/스키마를 확인한다
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
client.get("/diag").json()

# %%
client.post("/ask", json={"question": q}).json()

# %% 임베딩 차원이 Milvus 컬렉션과 맞는지 (제일 조용히 터지는 부분)
len(embeddings.embed_one("차원 확인"))
