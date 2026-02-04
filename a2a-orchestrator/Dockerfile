FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/a2a_orchestrator/ /app/a2a_orchestrator/

# Set PYTHONPATH explicitly
ENV PYTHONPATH=/app

# Verify imports work at build time
RUN python -c "from a2a_orchestrator.server import app; print('Import OK')"

# Run as non-root
RUN useradd -m -u 1000 app
USER app

EXPOSE 8000

CMD ["uvicorn", "a2a_orchestrator.server:app", "--host", "0.0.0.0", "--port", "8000"]
