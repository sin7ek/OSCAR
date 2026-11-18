FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OSCAR_CONFIG_PATH=/config/settings.json

RUN apt-get update && apt-get install -y --no-install-recommends libdiscid0 cyanrip flac \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

RUN groupadd --system oscar && useradd --system --gid oscar --home-dir /app oscar \
    && mkdir -p /config && chown oscar:oscar /config
USER oscar

EXPOSE 8080
CMD ["uvicorn", "oscar.api:app", "--host", "0.0.0.0", "--port", "8080"]
