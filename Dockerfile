FROM python:3.10-slim

WORKDIR /app

# Lazım olan faylları kopyalayın
COPY requirements.txt .
COPY . .

# Sistem asılılıqlarını quraşdırın
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libssl-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Pip versiyasını yeniləyin
RUN pip install --upgrade pip

# Kitabxanaları quraşdırın
RUN pip install --no-cache-dir -r requirements.txt

# Fayl sistemi üçün direktoriyanı yaradın
RUN mkdir -p downloads

CMD ["python3", "musicuserbot.py"]
