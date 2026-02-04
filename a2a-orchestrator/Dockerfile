FROM python:3.11-slim

WORKDIR /app

# Install dependencies directly
RUN pip install --no-cache-dir \
    "fastapi>=0.109.0" \
    "uvicorn[standard]>=0.27.0" \
    "httpx>=0.26.0" \
    "pydantic>=2.5.0"

# Copy source
COPY src/a2a_orchestrator/ /app/a2a_orchestrator/

# Run as non-root
RUN useradd -m -u 1000 app
USER app

EXPOSE 8000

CMD ["uvicorn", "a2a_orchestrator.server:app", "--host", "0.0.0.0", "--port", "8000"]
