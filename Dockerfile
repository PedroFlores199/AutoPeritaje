FROM python:3.12-slim-trixie AS serving
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock && useradd --uid 1000 --create-home app
COPY models ./models
COPY scripts ./scripts
RUN python scripts/download_models.py
COPY peritaje ./peritaje
COPY docs/sample.jpg ./docs/sample.jpg
COPY LICENSE NOTICE.md ./
USER app
ENV PORT=7860 PYTHONDONTWRITEBYTECODE=1
EXPOSE 7860
HEALTHCHECK --interval=20s --timeout=5s --start-period=45s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"
CMD ["uvicorn", "peritaje.main:app", "--host", "0.0.0.0", "--port", "7860", "--limit-concurrency", "6", "--backlog", "16", "--no-access-log"]

FROM serving AS space
USER root
COPY requirements-space.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements-space.lock && python scripts/download_pricing.py && chown -R app:app /app/pricing
ENV BUNDLED_PRICING=1 ARTIFACT_DIR=/app/pricing/data/demo PYTHONPATH=/app/pricing TALLER_URL=http://taller.internal
USER app
