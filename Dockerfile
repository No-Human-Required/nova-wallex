FROM python:3.12-slim@sha256:cb33f7f771ecec2ef1225cf39b159591a040391bd73e4c01f00fdfc4c47611d2
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONHASHSEED=0 \
    SW_ENV=production SW_DATA_DIR=/data PORT=8080 SW_REQUIRE_ENGINE=1 SW_REQUIRE_POSTGRES=1 SW_PUBLIC_READ_ONLY=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home app \
    && mkdir -p /data && chown app:app /data
COPY --chown=app:app app ./app
COPY --chown=app:app execution ./execution
COPY --chown=app:app starwallex ./starwallex
COPY --chown=app:app config ./config
COPY --chown=app:app prompts ./prompts
COPY --chown=app:app data ./data
COPY --chown=app:app seed ./seed
COPY --chown=app:app static ./static
COPY --chown=app:app scripts ./scripts
COPY --chown=app:app run.py supervisor.py ./
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8080')+'/readyz',timeout=3)"
CMD ["python", "supervisor.py"]
