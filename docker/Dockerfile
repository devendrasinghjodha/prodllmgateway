# Stage 1: Build & Dependencies
FROM python:3.11-slim as builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Final Runtime Image
FROM python:3.11-slim as runner

WORKDIR /app

# Create non-root user for security
RUN groupadd -r prodllm && useradd -r -g prodllm prodllm

# Copy installed python dependencies
COPY --from=builder /root/.local /home/prodllm/.local
ENV PATH=/home/prodllm/.local/bin:$PATH
ENV PYTHONPATH=/app

# Copy application source code
COPY app ./app
COPY pyproject.toml .

RUN chown -R prodllm:prodllm /app
USER prodllm

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
