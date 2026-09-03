# App Service와 로컬이 같은 런타임을 쓰게 하는 장치.
# "로컬에서는 됐는데" 사고의 대부분(의존성/경로/OS 패키지)이 여기서 먼저 잡힌다.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CACHE_DIR=/tmp/cache

WORKDIR /app

COPY requirements.txt pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .

COPY app ./app

EXPOSE 8000
# App Service는 보통 PORT 환경변수로 포트를 지정한다.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
