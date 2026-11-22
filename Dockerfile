# audiotools/trackverify is available in Debian Bookworm but removed from
# Trixie. Freeze the Bookworm Python 3.11 tool to a self-contained binary;
# do not mix oldstable apt repositories into OSCAR's runtime.
FROM debian:bookworm-slim AS trackverify-builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    audiotools python3-venv python3-pip libpython3.11 binutils \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv --system-site-packages /opt/pyinstaller \
    && /opt/pyinstaller/bin/pip install --no-cache-dir pyinstaller==6.16.0
RUN /opt/pyinstaller/bin/pyinstaller --clean --onefile \
    --collect-all audiotools --name trackverify /usr/bin/trackverify \
    && /dist/trackverify --help

FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OSCAR_CONFIG_PATH=/config/settings.json

RUN apt-get update && apt-get install -y --no-install-recommends libdiscid0 cyanrip flac \
    && rm -rf /var/lib/apt/lists/*

COPY --from=trackverify-builder /dist/trackverify /usr/local/bin/trackverify

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
# Fail the image build if this Debian cyanrip version lacks a flag OSCAR uses.
RUN python -m oscar.cyanrip_compat && command -v trackverify

RUN groupadd --system oscar && useradd --system --gid oscar --home-dir /app oscar \
    && mkdir -p /config && chown oscar:oscar /config
USER oscar

EXPOSE 8080
CMD ["uvicorn", "oscar.api:app", "--host", "0.0.0.0", "--port", "8080"]
