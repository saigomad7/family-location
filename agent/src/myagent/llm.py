"""Claude(Anthropic API) 클라이언트.

- 모델 기본값은 claude-opus-5. 설정으로 바꿀 수 있다.
- adaptive thinking + effort 로 깊이를 조절한다(예전의 budget_tokens 방식은 이
  모델군에서 400 에러가 난다).
- 출력이 길어질 수 있는 호출은 stream=True 로 쓴다. HTTP 타임아웃을 피하는
  가장 확실한 방법이고, App Service의 요청 타임아웃 아래에서 특히 중요하다.
"""

import logging
from functools import lru_cache

import anthropic

from .config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def client() -> anthropic.Anthropic:
    s = get_settings()
    kwargs = {}
    if s.anthropic_api_key:
        kwargs["api_key"] = s.anthropic_api_key
    if s.anthropic_base_url:  # 사내 게이트웨이를 경유하는 경우
        kwargs["base_url"] = s.anthropic_base_url
    return anthropic.Anthropic(**kwargs)


def complete(
    prompt: str,
    system: str | None = None,
    *,
    max_tokens: int = 16000,
    effort: str | None = None,
    stream: bool = False,
) -> dict:
    """한 번의 LLM 호출. 결과를 평범한 dict로 돌려준다.

    dict로 돌려주는 이유: Spyder 변수 탐색기에서 바로 펼쳐 볼 수 있고,
    FastAPI 응답으로도 그대로 나갈 수 있기 때문이다.
    """
    s = get_settings()
    params = {
        "model": s.llm_model,
        "max_tokens": max_tokens,
        "thinking": {"type": "adaptive"},
        "output_config": {"effort": effort or s.llm_effort},
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        # 시스템 프롬프트는 잘 안 바뀌므로 캐시를 걸어 둔다(프리픽스 캐싱).
        params["system"] = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]

    if stream:
        with client().messages.stream(**params) as s_:
            message = s_.get_final_message()
    else:
        message = client().messages.create(**params)

    if message.stop_reason == "refusal":
        detail = getattr(message.stop_details, "explanation", None)
        raise RuntimeError(f"모델이 응답을 거절했습니다: {detail}")

    text = "".join(b.text for b in message.content if b.type == "text")
    return {
        "text": text,
        "stop_reason": message.stop_reason,
        "model": message.model,
        "request_id": message._request_id,
        "usage": {
            "input": message.usage.input_tokens,
            "output": message.usage.output_tokens,
            "cache_read": getattr(message.usage, "cache_read_input_tokens", 0),
        },
    }
