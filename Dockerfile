# Minimal Python imici
FROM python:3.10-slim

# İşçi direktoriyası təyin edin
WORKDIR /app

# Lazım olan faylları konteynerə kopyalayın
COPY . .

# Tələb olunan Python kitabxanalarını quraşdırın
RUN pip install --no-cache-dir -r requirements.txt

# Fayl sistemi üçün müvafiq direktoriyanı yaradın
RUN mkdir -p downloads

# Port təyin edin (opsional)
EXPOSE 5000

# Botun işə salınması
CMD ["python3", "musicuserbot.py"]
