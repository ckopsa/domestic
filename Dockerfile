FROM ghcr.io/astral-sh/uv:python3.10-bookworm AS builder

WORKDIR /code
COPY ./pyproject.toml /code/pyproject.toml
COPY ./uv.lock /code/uv.lock
RUN uv sync
COPY ./app /code/app
CMD ["uv", "run", "fastapi", "run", "app/main.py", "--proxy-headers", "--port", "80"]