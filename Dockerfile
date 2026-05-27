FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv
EXPOSE 8000
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system .

COPY config ./config
COPY skills ./skills
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

VOLUME ["/app/logs", "/app/data", "/app/config"]
CMD ["edera"]
