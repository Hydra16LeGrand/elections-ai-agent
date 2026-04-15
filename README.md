# CI Elections - Agent d'Analyse Électorale

Chatbot pour interroger les résultats des élections locales ivoiriennes via une interface conversationnelle.

## Fonctionnalités

- **Questions analytiques** : "Combien de sièges a remporté le RHDP ?" → réponse avec données SQL
- **Questions narratives** : "Résume les résultats de Tiapoum" → réponse RAG avec contexte
- **Visualisations** : graphiques automatiques (barres, camembres) selon les données
- **Sécurité** : guardrails SQL (pas de DROP/DELETE, LIMIT auto, allowlist tables)

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Streamlit │────▶│  SQL Agent   │────▶│  PostgreSQL │
│   (UI)      │     │  Hybrid/RAG  │     │  (vues      │
└─────────────┘     └──────────────┘     │   sécurisées)│
                                         └─────────────┘
```

**Stack** : Python, Streamlit, PostgreSQL, LlamaIndex, Ollama, Gemini

## Prérequis

- Docker + Docker Compose
- Clé API Ollama Cloud ([ollama.com](https://ollama.com))
- Clé API Gemini ([aistudio.google.com](https://aistudio.google.com))

## Déploiement

### 1. Configuration

```bash
cp .env.example .env
# Éditez .env et ajoutez :
# OLLAMA_API_KEY=votre_cle_ollama
# GEMINI_API_KEY=votre_cle_gemini
```

### 2. Lancement

```bash
docker-compose up --build -d
```

**Important** : L'interface n'est pas immédiatement disponible. Au premier démarrage, le système :
1. Ingeste les données PDF (~2 min)
2. Construit l'index RAG (~1-2 min)

Attendez environ 3-4 minutes avant d'accéder à l'interface.

### 3. Vérification

```bash
# Voir la progression du démarrage
docker-compose logs -f ui

# Une fois que vous voyez "WARMUP COMPLET", l'interface est prête
```

### 4. Accès

| Service | URL | Notes |
|---------|-----|-------|
| Interface chatbot | http://localhost:8501 | Disponible après le warmup |
| Base de données | localhost:5433 | PostgreSQL avec données électorales |
| pgAdmin | http://localhost:8080 | Login: admin@artefact.com / admin |

## Utilisation

Posez des questions en langage naturel :

- **SQL** : "Quel candidat a gagné à Abidjan ?"
- **RAG** : "Résume les résultats de cette élection"
- **Visualisations** : "Montre-moi le top 10 des partis par sièges"

Le système détecte automatiquement s'il doit utiliser SQL (chiffres précis) ou RAG (résumés).

**Recherche flexible** : Les questions peuvent mentionner une région ou une circonscription sans préciser. Le système recherche automatiquement dans les deux champs (ex: "Abidjan" trouve toutes les circonscriptions du district).

## Structure du projet

```
app/
├── sql_agent.py        # Orchestrateur principal (SQL + hybrid)
├── hybrid_router.py    # Décision SQL vs RAG
├── entity_resolver.py  # Correction typos (Tiapam → Tiapoum)
├── rag_engine.py       # Index et recherche vectorielle
└── ui.py               # Interface Streamlit

ingestion/
└── ingest.py           # Pipeline PDF → PostgreSQL

tests/
├── level_1/            # Tests guardrails + intent router
└── level_2/            # Tests hybrid + entity + RAG
```

## Level 1 - SQL Agent (Terminé)

- Pipeline ELT : PDF → PostgreSQL avec vues sécurisées
- Guardrails : blocage DDL/DML, LIMIT auto, timeout 5s
- Détection hors-domaine (météo, présidentielles...)
- Résistance aux injections SQL et prompt injection

## Level 2 - Hybrid Router + RAG (Terminé)

- Routing automatique SQL vs RAG (seuil de confiance 0.80)
- Fuzzy matching pour les typos et alias de partis
- Index vectoriel avec Gemini Embeddings + retry
- Warmup automatique au démarrage Docker

## Limitations connues

- L'index RAG est reconstruit à chaque démarrage (pas de persistance)
- Premier démarrage lent (~4 min) à cause de l'ingestion + warmup
- Fallback MD5 sur les embeddings si Gemini API indisponible

## Développement local

```bash
# Base de données
docker-compose up -d db

# Ingestion
pip install -r requirements.txt
python ingestion/ingest.py

# Lancer l'UI
streamlit run app/ui.py
```

## Tests

```bash
# Tous les tests
pytest tests/

# Par niveau
pytest tests/level_1/
pytest tests/level_2/
```

---

Projet développé pour le test technique Artefact.
