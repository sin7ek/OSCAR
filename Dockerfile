FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OSCAR_CONFIG_PATH=/config/settings.json

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

RUN groupadd --system oscar && useradd --system --gid oscar --home-dir /app oscar \
    && mkdir -p /config && chown oscar:oscar /config
USER oscar

EXPOSE 8080
CMD ["uvicorn", "oscar.api:app", "--host", "0.0.0.0", "--port", "8080"]
