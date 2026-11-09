FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir build \
    && python -m build --wheel --outdir /wheels \
    && python -m pip wheel --wheel-dir /wheels /wheels/book_catalog-1.0.0-py3-none-any.whl

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    APP_ENV=production LOG_LEVEL=INFO DATABASE_URL=sqlite:////app/data/library.db
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels book-catalog==1.0.0 \
    && rm -rf /wheels \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data && chown appuser:appuser /app/data
USER appuser
VOLUME ["/app/data"]
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["book-catalog", "--host", "0.0.0.0", "--port", "8000"]
