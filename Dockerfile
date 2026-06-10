FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        libmariadb3 \
        libmariadb-dev \
        gcc \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY app ./app 

RUN useradd --create-home --uid 10001 appuser \
    && chown --recursive appuser:appuser /app

USER appuser 

EXPOSE 8000

CMD ["/app/.venv/bin/python", "-m", "app.server"]