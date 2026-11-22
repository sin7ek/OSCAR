# audiotools/trackverify is available in Debian Bookworm but removed from
# Trixie. Bundle the Bookworm tool with its Python 3.11 runtime and libraries.
# Install the unpacked bundle so trackverify never extracts itself at startup.
FROM debian:bookworm-slim AS trackverify-builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    audiotools python3-venv python3-pip libpython3.11 binutils \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv --system-site-packages /opt/pyinstaller \
    && /opt/pyinstaller/bin/pip install --no-cache-dir pyinstaller==6.16.0
RUN /opt/pyinstaller/bin/pyinstaller --clean --onedir \
    --collect-all audiotools --name trackverify /usr/bin/trackverify \
    && /dist/trackverify/trackverify --help

FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OSCAR_CONFIG_PATH=/config/settings.json

RUN apt-get update && apt-get install -y --no-install-recommends libdiscid0 cyanrip flac \
    && rm -rf /var/lib/apt/lists/*

COPY --from=trackverify-builder /dist/trackverify/ /opt/trackverify/
ENV PATH="/opt/trackverify:${PATH}"

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
# Fail the image build if this Debian cyanrip version lacks a flag OSCAR uses.
RUN python -m oscar.cyanrip_compat

RUN groupadd --system oscar && useradd --system --gid oscar --home-dir /app oscar \
    && mkdir -p /config && chown oscar:oscar /config
USER oscar

# Exercise the shipped verifier as the runtime user with an offline CD-audio FLAC.
RUN sample_dir="$(mktemp -d)" \
    && head -c 23520 /dev/zero | flac --silent --force-raw-format \
        --endian=little --sign=signed --channels=2 --bps=16 --sample-rate=44100 \
        -o "$sample_dir/test.flac" - \
    && trackverify -j 1 "$sample_dir/test.flac" \
    && rm -r "$sample_dir"

EXPOSE 8080
CMD ["uvicorn", "oscar.api:app", "--host", "0.0.0.0", "--port", "8080"]
