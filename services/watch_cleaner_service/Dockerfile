FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
# Install MQTT/dotenv dependencies before app code for better layer caching.
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
CMD ["python", "-m", "app.main"]
