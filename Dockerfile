FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project specification files
COPY pyproject.toml README.md ./

# Install project dependencies into system environment
RUN uv pip install --system -e .

# Copy application code
COPY lifeos/ ./lifeos/
COPY scripts/ ./scripts/

EXPOSE 8000 8001 8002 8003 8004 8005

CMD ["uvicorn", "lifeos.agents.orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]
