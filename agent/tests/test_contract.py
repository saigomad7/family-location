"""외부 의존성 없이 도는 계약 테스트.

배포 전에 `pytest -q` 로 돌린다. 네트워크가 필요한 검증은 ops/smoke.py 쪽.
"""

from myagent import steps
from myagent.config import Settings


def test_settings_defaults():
    s = Settings(_env_file=None)
    assert s.env == "local"
    assert s.llm_model == "claude-opus-5"


def test_require_reports_missing():
    s = Settings(_env_file=None)
    try:
        s.require("s3_bucket", "s3_access_key")
    except RuntimeError as exc:
        assert "s3_bucket" in str(exc)
    else:
        raise AssertionError("빈 설정인데 예외가 나지 않았다")


def test_chunk_covers_text_with_overlap():
    docs = [{"doc_id": "d1", "source_key": "d1", "text": "가나다라마바사" * 300}]
    chunks = steps.chunk(docs, size=800, overlap=100)
    assert len(chunks) > 1
    assert {c["id"] for c in chunks}.__len__() == len(chunks)  # id 중복 없음
    assert chunks[0]["chunk_idx"] == 0


def test_build_prompt_handles_empty_context():
    prompt = steps.build_prompt("질문", [])
    assert "검색 결과 없음" in prompt
    assert "질문" in prompt
