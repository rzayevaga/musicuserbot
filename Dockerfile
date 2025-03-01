# Dockerfile for Heroku deploy

FROM python:3.9-slim

WORKDIR /app

# Əvvəlcə asılılıqları yükləyirik
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bütün kod fayllarını konteynerə kopyalayırıq
COPY . .

# Botu işə salırıq
CMD ["python", "main.py"]
