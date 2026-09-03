"""설정 = 환경변수의 유일한 진입점.

로컬:      .env.local 파일에서 읽는다.
App Service: 파일이 없고 App Settings(환경변수)가 그대로 들어온다.
둘 다 있으면 실제 환경변수가 이긴다. 따라서 코드에 분기가 필요 없다.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 뒤쪽 파일이 앞쪽을 덮어쓴다 → 개인 설정(.env.local)이 팀 공용(.env)을 이긴다.
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "local"  # local | cloud

    # S3
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"

    # 로컬 캐시 (App Service 에서는 /tmp/cache — 재시작하면 사라진다)
    cache_dir: str = "./data/cache"

    # Milvus
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = ""
    milvus_collection: str = "docs"
    embed_dim: int = 384

    # 임베딩
    embed_provider: str = "local"  # local | http
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embed_endpoint: str = ""

    # LLM
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    llm_model: str = "claude-opus-5"
    llm_effort: str = "high"  # low | medium | high | xhigh | max

    # 운영
    log_level: str = "INFO"
    diag_token: str = ""
    git_sha: str = "dev"

    @property
    def cache_path(self) -> Path:
        return Path(self.cache_dir).expanduser()

    def require(self, *names: str) -> None:
        """빈 설정을 조용히 넘어가지 않게 한다. 클라우드에서 제일 흔한 사고 지점."""
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
    """Spyder에서 .env.local 을 고친 뒤 콘솔 재시작 없이 반영하려고 쓴다."""
    get_settings.cache_clear()
    return get_settings()
