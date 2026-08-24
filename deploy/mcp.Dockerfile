FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml ./
COPY apps ./apps
COPY pipelines ./pipelines
COPY services ./services
COPY data/metadata ./data/metadata
COPY data/generated ./data/generated
RUN pip install --no-cache-dir .

CMD ["sh", "-c", "uvicorn services.city_data_mcp.server:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers"]
