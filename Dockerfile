FROM python:3.10-slim

# Installation des dépendances système critiques pour Camelot et OpenCV
RUN apt-get update && apt-get install -y \
    ghostscript \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Commande par défaut (on pourra la surcharger dans le docker-compose)
CMD ["python", "ingestion/ingest.py"]