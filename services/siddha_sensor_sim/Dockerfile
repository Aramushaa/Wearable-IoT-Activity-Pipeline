FROM python:3.11-slim

WORKDIR /app

# Keep containers clean and stream logs immediately to Docker.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
# Install dependencies before copying app code for better Docker layer caching.
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

CMD ["python", "-m", "app.main"]
