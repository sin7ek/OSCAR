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

# Build the pinned Linux CTDB verifier and retain its corresponding source.
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS ctdb-builder
ARG TARGETARCH
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1
RUN apt-get update && apt-get install -y --no-install-recommends git patch \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src/ctdb-cli
RUN git init && git fetch --depth 1 https://github.com/Masterisk-F/ctdb-cli.git \
      627d2daae63d638c6ca9b578a2abba1290a45350 \
    && git checkout --detach FETCH_HEAD \
    && bash setup.sh \
    && test "$(git -C external/cuetools.net rev-parse HEAD)" = 4ddf769ce6d9ff850165f2468c8b58c1718844da \
    && tar --exclude=.git -czf /ctdb-cli-source.tar.gz -C /src ctdb-cli
RUN case "$TARGETARCH" in amd64) rid=linux-x64 ;; arm64) rid=linux-arm64 ;; *) exit 1 ;; esac \
    && dotnet publish CTDB.CLI/CTDB.CLI.csproj -c Release -m:1 \
       -r "$rid" --self-contained true -o /ctdb-publish

FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OSCAR_CONFIG_PATH=/config/settings.json \
    OSCAR_CTDB_EXECUTABLE=/opt/ctdb/ctdb-cli

RUN apt-get update && apt-get install -y --no-install-recommends libdiscid0 cyanrip flac libicu76 libssl3t64 libgssapi-krb5-2 zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY --from=trackverify-builder /dist/trackverify/ /opt/trackverify/
COPY --from=ctdb-builder /ctdb-publish/ /opt/ctdb/
COPY --from=ctdb-builder /ctdb-cli-source.tar.gz /usr/share/doc/oscar/ctdb-cli-source.tar.gz
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
    && "$OSCAR_CTDB_EXECUTABLE" | grep -q 'verify.*Verify against CTDB' \
    && rm -r "$sample_dir"

EXPOSE 8080
CMD ["uvicorn", "oscar.api:app", "--host", "0.0.0.0", "--port", "8080"]
