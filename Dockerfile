# Python 3.11.9-slim imicindən istifadə edirik
FROM python:3.11.9-slim

# İş qovluğunu təyin edirik
WORKDIR /app

# Lazımi sistem paketlərini quraşdırırıq (ffmpeg kimi)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Tələblər faylını kopyalayırıq və asılılıqları quraşdırırıq
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Bütün faylları konteynerə kopyalayırıq
COPY . .

# Userbotu işə salırıq
CMD ["python", "main.py"]
