#!/usr/bin/env python3
"""Script de warmup pour pré-construire l'index RAG au démarrage."""

import os
import sys
import logging

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def warmup_rag():
    """Pré-construit l'index RAG pour éviter le cold start."""
    try:
        logger.info("Warmup: Pré-construction de l'index RAG...")

        from app.rag_engine import RAGEngine, set_rag_engine_instance

        engine = RAGEngine(skip_index_build=False)

        if engine.index is not None:
            set_rag_engine_instance(engine)
            engine.persist()  # Sauvegarde explicite sur disque
            logger.info("Warmup: Index RAG construit, stocké et sauvegardé avec succès")
            return True
        else:
            logger.warning("Warmup: Index non construit, mode dégradé")
            return False

    except Exception as e:
        logger.error(f"Warmup: Erreur lors de la construction de l'index: {e}")
        logger.info("Le service démarrera quand même")
        return False


def warmup_sql_agent():
    """Vérifie que les dépendances SQL sont OK."""
    try:
        logger.info("Warmup: Vérification de la connexion SQL...")

        from sqlalchemy import create_engine, text

        # Utiliser DATABASE_URL (artefact_user) pour la vérification
        # AGENT_DB_URL (artefact_reader) peut ne pas avoir les droits
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://artefact_user:artefact_password@db:5432/elections_db"
        )
        engine = create_engine(db_url)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        logger.info("Warmup: Connexion SQL OK")
        return True

    except Exception as e:
        logger.error(f"Warmup: Connexion SQL échouée: {e}")
        return False


if __name__ == "__main__":
    logger.info("WARMUP - Préparation du service")

    required_env = ["OLLAMA_API_KEY", "GEMINI_API_KEY"]
    missing = [env for env in required_env if not os.environ.get(env)]
    if missing:
        logger.warning(f"Variables manquantes: {missing}")
    else:
        logger.info("Toutes les clés API configurées")

    sql_ok = warmup_sql_agent()
    rag_ok = warmup_rag()

    if sql_ok and rag_ok:
        logger.info("WARMUP COMPLET - Service prêt")
        sys.exit(0)
    elif sql_ok:
        logger.info("WARMUP PARTIEL - SQL OK, RAG en mode dégradé")
        sys.exit(0)
    else:
        logger.error("WARMUP ÉCHOUÉ - SQL non disponible")
        sys.exit(1)
