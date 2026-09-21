# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build

COPY pyproject.toml ./
COPY src ./src
RUN python -m pip wheel --wheel-dir=/wheels .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}"

RUN groupadd --system --gid 10001 pe-agent \
    && useradd --system --uid 10001 --gid pe-agent --home-dir /nonexistent --shell /usr/sbin/nologin pe-agent \
    && python -m venv /opt/venv

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl \
    && rm -rf /wheels

WORKDIR /app
COPY --chown=10001:10001 alembic.ini ./
COPY --chown=10001:10001 alembic ./alembic
COPY --chown=10001:10001 fixtures/scenarios ./fixtures
COPY --chown=10001:10001 fixtures/decisions ./decisions

USER 10001:10001
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "pe_agent.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
