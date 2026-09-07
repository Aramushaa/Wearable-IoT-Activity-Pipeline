FROM python:3.11-slim

WORKDIR /app

# Unbuffered output keeps container logs current for MQTT/Influx diagnostics.
ENV PYTHONUNBUFFERED=1

COPY app ./app
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# The ingest API listens on port 8000 inside the Compose network.
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
