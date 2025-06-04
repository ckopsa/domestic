FROM ghcr.io/astral-sh/uv:python3.10-bookworm AS builder

WORKDIR /code
COPY ./pyproject.toml /code/pyproject.toml
COPY ./uv.lock /code/uv.lock
COPY src /code/src
RUN uv sync
CMD ["uv", "run", "fastapi", "run", "app/main.py", "--proxy-headers", "--port", "80"]