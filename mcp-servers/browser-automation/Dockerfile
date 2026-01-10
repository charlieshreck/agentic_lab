# Use Microsoft's Playwright Python image - includes browsers pre-installed
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install uv for fast package management
RUN pip install --no-cache-dir uv

# Copy and install dependencies
COPY pyproject.toml .
RUN uv pip install --system -e .

# Copy source
COPY src/ ./src/

# Run as non-root user (pwuser is created by Playwright image)
USER pwuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

EXPOSE 8000

CMD ["python", "-m", "src.main"]
