"""Module RAG avec LlamaIndex pour le système hybride."""

import os
import json
import time
from typing import List, Dict, Optional
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from ollama import Client
from dotenv import load_dotenv

from llama_index.core import Document, VectorStoreIndex, Settings, StorageContext, load_index_from_storage
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.embeddings import BaseEmbedding
from pydantic import PrivateAttr

PERSIST_DIR = "/app/rag_storage"

from google import genai
from google.genai import types

load_dotenv()

OLLAMA_HOST = "https://ollama.com"
MODEL_RAG = "qwen3-coder-next"

MAX_RETRIES = 3
RETRY_DELAY = 1

try:
    client = Client(
        host=OLLAMA_HOST,
        headers={'Authorization': f"Bearer {os.environ.get('OLLAMA_API_KEY')}"}
    )
except Exception as e:
    import logging
    logging.warning(f"Impossible de connecter Ollama client: {e}")
    client = None

class GeminiEmbedding(BaseEmbedding):
    """Wrapper Gemini Embeddings avec retry et fallback."""
    _client: genai.Client = PrivateAttr()
    _model_name: str = PrivateAttr()
    _fallback_mode: bool = PrivateAttr(default=False)

    def __init__(self, model_name: str = "gemini-embedding-001", **kwargs):
        super().__init__(**kwargs)
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            import logging
            logging.warning("GEMINI_API_KEY non définie, mode fallback activé")
            self._fallback_mode = True
        else:
            self._client = genai.Client(api_key=api_key)
        self._model_name = model_name

    def _embed_with_retry(self, text: str, task_type: str) -> List[float]:
        """Embedding avec retry et backoff exponentiel."""
        if self._fallback_mode:
            import hashlib
            hash_val = hashlib.md5(text.encode()).hexdigest()
            embedding = [(int(hash_val[i:i+2], 16) / 255.0) - 0.5 for i in range(0, 1536, 2)]
            return embedding[:768]

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                result = self._client.models.embed_content(
                    model=self._model_name,
                    contents=text,
                    config=types.EmbedContentConfig(task_type=task_type)
                )
                return result.embeddings[0].values
            except Exception as e:
                last_error = e
                error_msg = str(e)
                if "400" in error_msg or "401" in error_msg or "403" in error_msg or "404" in error_msg:
                    raise
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (2 ** attempt)
                    import logging
                    logging.warning(f"Gemini API erreur (tentative {attempt + 1}/{MAX_RETRIES}): {e}")
                    time.sleep(wait_time)

        import logging
        logging.error(f"Gemini API indisponible après {MAX_RETRIES} tentatives: {last_error}")
        self._fallback_mode = True
        return self._embed_with_retry(text, task_type)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._embed_with_retry(query, "RETRIEVAL_QUERY")

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._embed_with_retry(text, "RETRIEVAL_DOCUMENT")

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Batch embeddings avec gestion d'erreur par item."""
        results = []
        for text in texts:
            try:
                results.append(self._get_text_embedding(text))
            except Exception as e:
                import logging
                logging.error(f"Erreur embedding batch item: {e}")
                # Fallback for this item
                results.append(self._embed_with_retry(text, "RETRIEVAL_DOCUMENT"))
        return results

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)


# Configuration lazy (évite l'échec au import)
_embed_model_instance = None

def get_embed_model():
    global _embed_model_instance
    if _embed_model_instance is None:
        try:
            _embed_model_instance = GeminiEmbedding()
            Settings.embed_model = _embed_model_instance
        except Exception as e:
            import logging
            logging.error(f"Impossible d'initialiser GeminiEmbedding: {e}")
            # Create dummy embedding that doesn't block the app
            _embed_model_instance = GeminiEmbedding()
            _embed_model_instance._fallback_mode = True
    return _embed_model_instance


@dataclass
class ElectionDocument:
    """Représente une ligne de données électorales formatée en texte."""
    text: str
    region: str
    circonscription: str
    code_circonscription: str
    metadata: Dict


DB_URL = os.environ.get(
    "AGENT_DB_URL",
    "postgresql://artefact_reader:reader_password@db:5432/elections_db"
)
engine = create_engine(DB_URL)


class RAGEngine:
    """Moteur de Retrieval Augmented Generation pour les données électorales."""

    def __init__(self, skip_index_build: bool = False):
        """Initialise le moteur RAG."""
        self.index: Optional[VectorStoreIndex] = None
        self.documents: List[Document] = []
        self._index_built = False

        if skip_index_build:
            # Try to load from disk first
            self._load_from_disk()
        else:
            # Build from database
            try:
                self._build_index()
            except Exception as e:
                import logging
                logging.error(f"Échec construction index RAG: {e}")

    def _load_from_disk(self) -> bool:
        """Charge l'index depuis le disque si disponible."""
        import os
        if not os.path.exists(PERSIST_DIR):
            return False

        try:
            get_embed_model()
            storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
            self.index = load_index_from_storage(storage_context)
            self._index_built = True
            print("Index RAG chargé depuis le disque")
            return True
        except Exception as e:
            print(f"Impossible de charger l'index depuis le disque: {e}")
            return False

    def persist(self) -> None:
        """Sauvegarde l'index sur le disque."""
        if self.index and self._index_built:
            try:
                import os
                os.makedirs(PERSIST_DIR, exist_ok=True)
                self.index.storage_context.persist(persist_dir=PERSIST_DIR)
                print(f"Index RAG sauvegardé dans {PERSIST_DIR}")
            except Exception as e:
                print(f"Erreur sauvegarde index: {e}")

    def _fetch_election_data(self) -> List[ElectionDocument]:
        """Récupère les données électorales depuis la BDD."""
        documents = []

        try:
            with engine.connect() as conn:
                query = """
                SELECT
                    region,
                    nom_circonscription,
                    code_circonscription,
                    candidat,
                    parti,
                    voix,
                    pourcentage,
                    est_elu
                FROM vw_results_clean
                ORDER BY region, nom_circonscription, voix DESC
                """

                result = conn.execute(text(query))

                current_circo = None
                circo_data = None
                candidates = []

                for row in result:
                    circo_key = row.code_circonscription

                    if circo_key != current_circo:
                        if circo_data and candidates:
                            doc = self._format_circonscription_document(circo_data, candidates)
                            documents.append(doc)

                        current_circo = circo_key
                        circo_data = {
                            'region': row.region,
                            'nom_circonscription': row.nom_circonscription,
                            'code_circonscription': row.code_circonscription,
                        }
                        candidates = []

                    candidates.append({
                        'nom': row.candidat,
                        'parti': row.parti,
                        'voix': row.voix,
                        'pourcentage': row.pourcentage,
                        'elu': row.est_elu
                    })

                if circo_data and candidates:
                    doc = self._format_circonscription_document(circo_data, candidates)
                    documents.append(doc)

        except Exception as e:
            import logging
            logging.error(f"Erreur récupération données: {e}")

        return documents

    def _format_circonscription_document(self, circo_data: Dict, candidates: List[Dict]) -> ElectionDocument:
        """Formate une circonscription et ses candidats en document texte narratif."""
        sorted_candidates = sorted(candidates, key=lambda x: x['voix'], reverse=True)

        lines = [
            f"RÉSULTATS ÉLECTORAUX - {circo_data['region']}",
            f"Circonscription: {circo_data['nom_circonscription']} (Code: {circo_data['code_circonscription']})",
            "",
            "CANDIDATS ET RÉSULTATS:"
        ]

        total_voix = sum(c['voix'] for c in candidates)

        for i, cand in enumerate(sorted_candidates[:10], 1):
            statut = " (ÉLU)" if cand['elu'] else ""
            lines.append(
                f"{i}. {cand['nom']} ({cand['parti']}) : "
                f"{cand['voix']:,} voix ({cand['pourcentage']:.2f}%){statut}"
            )

        lines.extend([
            "",
            f"Total des voix comptées dans cette circonscription: {total_voix:,}"
        ])

        text = "\n".join(lines)

        return ElectionDocument(
            text=text,
            region=circo_data['region'],
            circonscription=circo_data['nom_circonscription'],
            code_circonscription=circo_data['code_circonscription'],
            metadata={
                'nb_candidats': len(candidates),
                'total_voix': total_voix
            }
        )

    def _build_index(self) -> None:
        """Construit l'index vectoriel avec Gemini Embeddings."""
        if self._index_built:
            return

        print("Construction de l'index RAG...")

        try:
            get_embed_model()
        except Exception as e:
            print(f"Impossible d'initialiser les embeddings: {e}")
            return

        election_docs = self._fetch_election_data()
        print(f"{len(election_docs)} documents électoraux chargés")

        if not election_docs:
            print("Aucun document à indexer")
            return

        self.documents = [
            Document(
                text=doc.text,
                metadata={
                    'region': doc.region,
                    'circonscription': doc.circonscription,
                    'code': doc.code_circonscription
                }
            )
            for doc in election_docs
        ]

        try:
            parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)
            nodes = parser.get_nodes_from_documents(self.documents)

            self.index = VectorStoreIndex(nodes)
            self._index_built = True
            print("Index RAG construit avec succès")

            # Sauvegarde sur disque pour les futurs processus
            self.persist()
        except Exception as e:
            import logging
            logging.error(f"Erreur construction index: {e}")
            self.index = None

    def query(self, question: str, top_k: int = 3) -> Dict:
        """Interroge l'index RAG."""
        if not self._index_built and self.index is None:
            try:
                self._build_index()
            except Exception as e:
                import logging
                logging.error(f"Impossible de construire l'index à la volée: {e}")

        if not self.index:
            return {
                'status': 'error',
                'narrative': (
                    "Le service RAG est temporairement indisponible. "
                    "L'index vectoriel n'a pas pu être construit. "
                    "Veuillez réessayer dans quelques instants ou poser une question SQL."
                ),
                'data': [],
                'route': 'rag_error',
                'error_type': 'index_unavailable'
            }

        try:
            retriever = self.index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(question)
        except Exception as e:
            import logging
            logging.error(f"Erreur retrieval: {e}")
            return {
                'status': 'error',
                'narrative': "Erreur lors de la recherche dans l'index. Veuillez réessayer.",
                'data': [],
                'route': 'rag_error',
                'error_type': 'retrieval_error'
            }

        context_parts = []
        for i, node in enumerate(nodes, 1):
            context_parts.append(f"[Document {i}]\n{node.text}")

        context = "\n\n".join(context_parts)

        for attempt in range(MAX_RETRIES):
            try:
                if client is None:
                    raise Exception("Client Ollama non initialisé")

                response = client.chat(
                    model=MODEL_RAG,
                    messages=[
                        {"role": "system", "content": "Tu es un assistant expert en données électorales."},
                        {"role": "user", "content": self._build_prompt(question, context)}
                    ],
                    options={"temperature": 0.2}
                )

                answer = response['message']['content'].strip()

                return {
                    'status': 'success',
                    'narrative': answer,
                    'data': [{'context': context}],
                    'sql': '',
                    'chart_type': 'table',
                    'route': 'rag',
                    'source_regions': [node.metadata.get('region') for node in nodes],
                    'source_circonscriptions': [node.metadata.get('circonscription') for node in nodes]
                }

            except Exception as e:
                import logging
                logging.warning(f"Ollama erreur (tentative {attempt + 1}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                else:
                    # Fallback: return raw context
                    return {
                        'status': 'partial',
                        'narrative': (
                            f"Basé sur les données trouvées:\n\n"
                            f"Circonscriptions pertinentes: {[n.metadata.get('circonscription') for n in nodes]}\n\n"
                            f"Note: Le service de génération de texte est temporairement indisponible."
                        ),
                        'data': [{'context': context[:1000]}],
                        'sql': '',
                        'chart_type': 'table',
                        'route': 'rag_fallback',
                        'error_type': 'generation_failed'
                    }

    def _build_prompt(self, question: str, context: str) -> str:
        """Construit le prompt pour Ollama."""
        return f"""Tu es un assistant expert en analyse électorale ivoirienne.

CONTEXTE (données des élections locales):
{context}

QUESTION DE L'UTILISATEUR:
{question}

INSTRUCTIONS:
1. Réponds en français de manière narrative et claire.
2. Base-toi UNIQUEMENT sur les données fournies ci-dessus.
3. Si les données ne permettent pas de répondre, dis-le honnêtement.
4. Cite des chiffres précis quand c'est pertinent.
5. Sois concis (3-4 phrases maximum).

RÉPONSE:"""


# =============================================================================
# SINGLETON INSTANCE (Thread-safe with lock)
# =============================================================================

import threading
_rag_engine_lock = threading.Lock()
_rag_engine_instance: Optional[RAGEngine] = None


def set_rag_engine_instance(engine: RAGEngine):
    """Stocke l'instance RAG pré-construite (appelé par warmup)."""
    global _rag_engine_instance
    with _rag_engine_lock:
        _rag_engine_instance = engine


def get_rag_engine() -> RAGEngine:
    """
    Retourne l'instance singleton du moteur RAG (thread-safe).
    Essaie d'abord de charger depuis le disque (construit par warmup).
    """
    global _rag_engine_instance
    if _rag_engine_instance is None:
        with _rag_engine_lock:
            if _rag_engine_instance is None:
                # Try loading from disk first (built by warmup)
                _rag_engine_instance = RAGEngine(skip_index_build=True)
                # If not on disk, build from scratch
                if not _rag_engine_instance._index_built:
                    _rag_engine_instance = RAGEngine(skip_index_build=False)
    return _rag_engine_instance


def query_rag(question: str) -> Dict:
    """Fonction rapide pour interroger le RAG."""
    engine = get_rag_engine()
    return engine.query(question)


# =============================================================================
# BLOC DE TEST
# =============================================================================

if __name__ == "__main__":
    print("=== Test RAG Engine (Resilient) ===")
    print()

    engine = RAGEngine()

    test_questions = [
        "Résume les résultats de Tiapoum",
        "Quels sont les principaux candidats à Korhogo ?",
    ]

    for question in test_questions:
        print(f"Q: {question}")
        result = engine.query(question)
        print(f"Status: {result.get('status')}")
        print(f"Route: {result.get('route')}")
        print(f"Réponse: {result['narrative'][:200]}...")
        print()
