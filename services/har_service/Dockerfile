FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
# ONNX Runtime and numpy are installed before app code for better layer caching.
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
# Copy the model and diagnostic scripts into the same image used by the service.
COPY model ./model
COPY evaluate_model.py ./evaluate_model.py
COPY inspect_model.py ./inspect_model.py
COPY fix_finder.py ./fix_finder.py

CMD ["python", "-m", "app.main"]
