#!/usr/bin/env python3
"""
Script de warmup pour pré-construire l'index RAG au démarrage du container.
Exécuté avant le lancement de Streamlit.
"""

import os
import sys
import logging

# Charger les variables d'environnement
from dotenv import load_dotenv
load_dotenv()

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def warmup_rag():
    """Pré-construit l'index RAG pour éviter le cold start."""
    try:
        logger.info("🔄 Warmup: Pré-construction de l'index RAG...")

        # Import ici pour avoir les logs avant
        from app.rag_engine import RAGEngine

        # Construction de l'index (sans skip)
        engine = RAGEngine(skip_index_build=False)

        if engine.index is not None:
            logger.info("✅ Warmup: Index RAG construit avec succès")
            return True
        else:
            logger.warning("⚠️ Warmup: Index non construit, le service fonctionnera en mode dégradé")
            return False

    except Exception as e:
        logger.error(f"❌ Warmup: Erreur lors de la construction de l'index: {e}")
        logger.info("💡 Le service démarrera quand même, l'index sera construit à la première requête")
        return False


def warmup_sql_agent():
    """Vérifie que les dépendances SQL sont OK."""
    try:
        logger.info("🔄 Warmup: Vérification de la connexion SQL...")

        from sqlalchemy import create_engine, text

        db_url = os.environ.get(
            "AGENT_DB_URL",
            "postgresql://artefact_reader:reader_password@localhost:5433/elections_db"
        )
        engine = create_engine(db_url)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        logger.info("✅ Warmup: Connexion SQL OK")
        return True

    except Exception as e:
        logger.error(f"❌ Warmup: Connexion SQL échouée: {e}")
        return False


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("WARMUP - Préparation du service")
    logger.info("=" * 60)

    # Vérification des variables d'environnement
    required_env = ["OLLAMA_API_KEY", "GEMINI_API_KEY"]
    missing = [env for env in required_env if not os.environ.get(env)]
    if missing:
        logger.warning(f"⚠️ Variables d'environnement manquantes: {missing}")
    else:
        logger.info("✅ Toutes les clés API sont configurées")

    # Warmup SQL
    sql_ok = warmup_sql_agent()

    # Warmup RAG
    rag_ok = warmup_rag()

    logger.info("=" * 60)
    if sql_ok and rag_ok:
        logger.info("✅ WARMUP COMPLET - Service prêt")
        sys.exit(0)
    elif sql_ok:
        logger.info("⚠️ WARMUP PARTIEL - SQL OK, RAG en mode dégradé")
        sys.exit(0)  # On démarre quand même
    else:
        logger.error("❌ WARMUP ÉCHOUÉ - SQL non disponible")
        sys.exit(1)
