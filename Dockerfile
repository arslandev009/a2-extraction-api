# Build from the ai-studio ROOT (the context must contain packages/llm-client and this project):
#   docker build -f projects/a2-extraction-api/Dockerfile -t a2-extraction .
#   docker run --rm -p 8002:8002 --env-file .env a2-extraction
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY packages/llm-client /app/packages/llm-client
COPY projects/a2-extraction-api/pyproject.toml /app/a2/pyproject.toml
COPY projects/a2-extraction-api/src /app/a2/src
RUN pip install /app/packages/llm-client && pip install /app/a2

RUN useradd --create-home appuser
USER appuser

ENV PORT=8002 MAX_UPLOAD_MB=3 MAX_PAGES=5
EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8002'))"
CMD ["sh", "-c", "uvicorn extractor.main:app --host 0.0.0.0 --port ${PORT}"]
