FROM python:3.10-slim

# Installation des dépendances système critiques pour Camelot et OpenCV
RUN apt-get update && apt-get install -y \
    ghostscript \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Exposition du port Streamlit
EXPOSE 8501

# Healthcheck pour Streamlit
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Rendre l'entrypoint exécutable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Commande par défaut : warmup puis Streamlit
ENTRYPOINT ["/entrypoint.sh"]
