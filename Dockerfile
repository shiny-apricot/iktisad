FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY iktisad /app/iktisad

RUN pip install --no-cache-dir .

ENTRYPOINT ["iktisad-mcp"]
