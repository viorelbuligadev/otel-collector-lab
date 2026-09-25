FROM python:3.13.15-slim

# Print logs immediately instead of buffering stdout
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Don't run as root
USER nobody

ENTRYPOINT ["python", "app.py"]
