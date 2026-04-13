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

# Exposition du port Streamlit
EXPOSE 8501

# Healthcheck pour Streamlit
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Commande par défaut : lancer l'interface Streamlit
CMD ["streamlit", "run", "app/ui.py", "--server.port=8501", "--server.address=0.0.0.0"]
