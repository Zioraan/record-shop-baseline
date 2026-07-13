FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*
COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY libs /app/libs
COPY services/api/app /app/app
ENV PYTHONPATH=/app/libs
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
