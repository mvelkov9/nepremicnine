# Stage 1: build dependencies
FROM python:3.13-slim AS builder

WORKDIR /build
RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: runtime
FROM python:3.13-slim

RUN adduser --disabled-password --no-create-home appuser

COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

ENV PYTHONPATH=/app

# In development, we run as root for volume mounts
# In production, switch to appuser
# USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
