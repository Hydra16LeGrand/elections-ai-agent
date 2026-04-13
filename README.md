# CI Elections - Data & AI Platform

Plateforme d'analyse des élections locales ivoiriennes intégrant un pipeline d'ingestion ELT et un agent conversationnel Text-to-SQL sécurisé avec interface web Streamlit.

## Architecture Principale

Le système repose sur trois couches distinctes :

1. **Couche Ingestion (Data Engineering) - `/ingestion`**
   - Extraction des données tabulaires complexes depuis le PDF source via `camelot`.
   - Nettoyage, standardisation et propagation géographique (Forward Fill).
   - Déploiement d'une couche sémantique PostgreSQL (Vues métier : `vw_winners`, `vw_turnout`, `vw_results_clean`) pour restreindre la portée des requêtes.
   - Application du principe de moindre privilège (RBAC) via la création d'un profil `ReadOnly` dédié à l'agent d'inférence.

2. **Couche Application (AI Engineering) - `/app`**
   - **Agent Text-to-SQL** avec architecture **Dual-Modèle** :
     - `qwen3-coder-next` pour la génération SQL (qualité de code)
     - `mixtral-8x7b` pour la synthèse narrative (vitesse)
   - Boucle de rétroaction (ReAct loop) avec auto-correction sur erreur SQL.
   - Routeur d'intention (Intent Router) pour la classification des requêtes.

3. **Couche Interface (Frontend) - `/app/ui.py`**
   - Interface chatbot avec **Smart Rendering** :
     - Valeurs agrégées : affichage en carte stylisée
     - Petits jeux de données (≤15 lignes) : toggle Graphique/Tableau
     - Grands jeux de données (>15 lignes) : tableau par défaut
   - Visualisations Plotly (bar, pie, line, scatter) avec ordre SQL préservé.

## Architecture Decision Record (ADR) : Vanilla vs. Frameworks

La couche d'orchestration Text-to-SQL est développée en Python standard ("Vanilla") plutôt qu'au travers d'abstractions de type LangChain (`create_sql_agent`). Ce choix garantit la validation des contraintes de sécurité :

- **Routing Sémantique (Out of Domain) :** Les requêtes hors périmètre (ex: données présidentielles, météo) sont identifiées et rejetées par le routeur avant l'étape de traduction SQL, réduisant les risques d'hallucination.
- **Guardrails Déterministes :** La validation des requêtes (Allowlist des vues, blocage des instructions DDL/DML type `DROP`, enforcement du `LIMIT` sauf sur agrégations) est gérée par des fonctions Python pures. Ce pare-feu applicatif offre une sécurité indépendante du modèle linguistique face aux tentatives d'injection (Adversarial Prompts).
- **Contrat de données structuré :** L'agent retourne systématiquement un dictionnaire typé (`narrative`, `data`, `sql`, `chart_type`), condition préalable à la génération de graphiques dynamiques sur le front-end.

## Bonus Implémentés (Level 1)

| Bonus | Description | Implémentation |
|-------|-------------|----------------|
| **A - Guardrails** | Allowlist strict des vues, blocage DDL/DML (DROP, DELETE), timeout 5s, LIMIT intelligent (pas sur agrégations) | `sql_agent.py:apply_guardrails()` |
| **B - Hors Domaine** | Détection et rejet des questions hors dataset (présidentielles, météo) | `sql_agent.py:ROUTER_PROMPT` |
| **C - Adversarial** | Résistance aux prompt injections et tentatives d'exfiltration | `sql_agent.py:analyze_intent()` |

## Performance Optimizations

- **Architecture Dual-Modèle** : Réduction des appels LLM de 4 à 2 par question
- **Smart Rendering** : Pas d'appel LLM depuis l'UI pour le choix de chart
- **Streamlit Caching** : Client Ollama en cache pour réutilisation

## Lancement Rapide (Docker)

Le projet est entièrement conteneurisé pour garantir une reproductibilité stricte de l'environnement de développement.

### Prérequis
- Docker & Docker Compose
- Une clé API Ollama Cloud (variable `OLLAMA_API_KEY`)

### Procédure de déploiement

1. **Préparation de l'environnement :**
   ```bash
   cp .env.example .env
   # Éditer .env et renseigner OLLAMA_API_KEY
   ```

2. **Déploiement complet :**
   ```bash
   docker-compose up --build -d
   ```

3. **Accès aux services :**

   | Service | URL | Description |
   |---------|-----|-------------|
   | Interface Web | http://localhost:8501 | Chatbot Streamlit avec visualisations |
   | Base de données | localhost:5433 | PostgreSQL avec données électorales |
   | pgAdmin | http://localhost:8080 | Interface SQL (admin@artefact.com / admin) |

4. **Logs et debug :**
   ```bash
   # Voir les logs du service UI
   docker-compose logs -f ui

   # Voir les logs de l'ingestion
   docker-compose logs -f ingestion
   ```

### Arrêt des services

```bash
docker-compose down
# Pour supprimer les volumes (données) :
docker-compose down -v
```

## Développement Local (hors Docker)

Pour développer sans Docker :

```bash
# 1. Base de données
docker-compose up -d db

# 2. Ingestion des données
pip install -r requirements.txt
python ingestion/ingest.py

# 3. Lancer l'UI
streamlit run app/ui.py
```

## Structure du Projet

```
artefact/
├── app/
│   ├── sql_agent.py          # Agent Text-to-SQL avec architecture dual-modèle
│   └── ui.py                 # Interface Streamlit avec Smart Rendering
├── ingestion/
│   ├── ingest.py             # Pipeline ELT PDF → PostgreSQL
│   └── init_views.sql        # Vues métier et sécurité RBAC
├── source_files/
│   └── EDAN_2025_*.pdf       # Données sources
├── Dockerfile                # Image Docker production-ready
├── docker-compose.yml        # Orchestration multi-services
└── requirements.txt        # Dépendances Python
```

## Licence

Projet développé pour le test technique Artefact.
