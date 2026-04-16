# Livrables - CI Elections AI Agent

## Éléments fournis

| Livrable | Statut | Localisation |
|----------|--------|--------------|
| Code source | Disponible | GitHub (repository public) |
| Vidéo de démonstration | Enregistrée | Disque local (à uploader sur Google Drive/YouTube unlisted) |
| Documentation technique | Ce fichier + README.md | Racine du projet |

---

## 1. Choix Technologiques

### 1.1 LLM : Ollama Cloud (Qwen3 Coder)

- **Modèle puissant** : Qwen3 Coder (32B paramètres) offre des performances proches de GPT-4 à fraction du coût et est spécialiser dans le coding. Ideal pour du Text to Sql
- **API simple** : Pas de gestion d'infrastructure GPU
- **Coût maîtrisé** : Pay-per-use, pas de VM dédiée à maintenir
- **Différenciation** : Alternative peu connue aux hyperscalers (OpenAI, Anthropic)

### 1.2 Orchestrateur : Python Vanilla (ReAct)

**Pourquoi pas LangChain/LangGraph ?**

- **Pas de over-engineering** : Une boucle ReAct simple (3 essais max) suffit pour la génération SQL
- **Contrôle total** : Pas de magic cachée, chaque étape est visible et debuggable
- **Dépendances minimales** : SQLAlchemy + Ollama client uniquement, pas de framework lourd
- **Performances** : Moins de overhead que LangChain pour des appels LLM simples

**Pattern utilisé** : Boucle ReAct manuelle (Question → Prompt LLM → Extraction SQL → Guardrails → Exécution → Retry si erreur)

### 1.3 Embeddings : Google Gemini

**Pourquoi Gemini pour les embeddings ?**

- **Multilingue natif** : Support du français et des langues locales ivoiriennes
- **Free tier généreux** : 1500 requêtes/jour gratuitement, suffisant pour le développement

### 1.4 Framework RAG : LlamaIndex

**Pourquoi LlamaIndex et non LangChain ?**

- **Abstraction pertinente** : High-level API pour l'indexation
- **Stockage persistant natif** : Sauvegarde/chargement disque via `StorageContext` (crucial pour le warmup Docker)
- **Intégration embeddings** : Connecteur Gemini natif avec retry exponentiel intégré
- **Moins de magic** : Plus transparent sur les étapes de retrieval

### 1.5 Base de données : PostgreSQL + SQLAlchemy

- **Maturité** : Moteur relationnel éprouvé pour les données électorales structurées
- **Couche sémantique** : Vues SQL (`vw_winners`, `vw_turnout`) isolant la complexité métier
- **Sécurité RBAC** : Rôle `artefact_reader` en read-only, empêchant toute modification accidentelle

### 1.6 Interface : Streamlit

- **Rapidité de développement** : POC fonctionnel en 2 heures vs jours pour React+FastAPI et facilité d'utilisation par rapport à OpenWeb UI
- **Intégration Python native** : Pas de friction entre le backend et l'UI
- **Widgets data** : Tableaux et graphiques natifs avec rendering intelligent. Meilleurs visuel par rapport à Gradio.

### 1.7 Docker : Portabilité

**Pourquoi Docker ?**

- **Portabilité** : L'environnement complet (Python, PostgreSQL, dépendances) est reproductible sur n'importe quelle machine avec Docker installé
- **Zero configuration** : Pas d'installation manuelle de PostgreSQL, pgAdmin ou des packages Python
- **Isolation** : Les services communiquent via réseau interne Docker, pas de conflit de ports avec l'hôte
- **Démarrage unique** : `docker compose up` lance toute la stack (DB, ingestion, warmup, UI)

**Architecture multi-services** :
- `db` : PostgreSQL avec données persistantes (volume Docker)
- `ingestion` : Pipeline ELT (exécute une fois puis s'arrête)
- `warmup` : Construction index RAG (exécute une fois puis s'arrête)
- `ui` : Streamlit (dépend du warmup)
- `pgadmin` : Interface graphique PostgreSQL

### 1.8 Outils complémentaires

| Outil | Usage | Justification |
|-------|-------|---------------|
| **pgAdmin** | Visualisation données | Interface graphique pour explorer les 1500+ lignes de résultats électoraux sans écrire de SQL |
| **thefuzz** | Fuzzy matching | Correction des typos utilisateur (Tiapam → Tiapoum) via Levenshtein distance |
| **Camelot** | Extraction PDF | Extraction tableaux PDF avec préservation de la structure tabulaire (alternative à PDFplumber) |

### 1.9 Qualité des données (Data Patch)

Lors de l'analyse du dataset PDF, une anomalie a été détectée : la circonscription '028' commence à la page 4 mais sa région parente ('BOUNKANI') n'est rendue qu'à la page 5. Le forward fill standard ne pouvait pas associer correctement cette circonscription à sa région.

**Solution** : Injection manuelle de la région correcte dans `ingestion/ingest.py` (ligne 72) avant le forward fill :

```python
# CORRECTIF : Anomalie de saut de page dans le document source
mask_028 = df_raw['raw_code_circonscription'].astype(str).str.contains('028', na=False)
df_raw.loc[mask_028, 'raw_region'] = 'BOUNKANI'
```

Ce patch assure l'intégrité géographique des données avant leur insertion en base.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DOCKER COMPOSE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌─────────────┐ │
│  │    db        │◄───│  ingestion   │    │   warmup     │───►│     ui      │ │
│  │ PostgreSQL   │    │   service    │    │   service    │    │  Streamlit  │ │
│  │- election_db │    │  (PDF→SQL)   │    │ (Build index)│    │   (:8501)   │ │
│  │- artefact_  │    │              │    │              │    │             │ │
│  │  reader role│    │              │    │              │    │             │ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └─────────────┘ │
│         ▲                                                    │              │
│         │                                                    │              │
│         │              ┌──────────────┐                      │              │
│         └──────────────│   pgAdmin    │◄─────────────────────┘              │
│                        │   (:8080)    │                                     │
│                        └──────────────┘                                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL APIs                                      │
│  ┌──────────────────────────────┐  ┌─────────────────────────────────────┐ │
│  │      Ollama Cloud API         │  │         Google Gemini API            │ │
│  │  (Qwen3 Coder - Text Gen)    │  │   (Embeddings - Vector Search)      │ │
│  └──────────────────────────────┘  └─────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Flux de données

1. **Ingestion** (au premier démarrage) : PDF → Camelot → Forward Fill → PostgreSQL
2. **Warmup** (post-ingestion) : PostgreSQL → LlamaIndex → Gemini Embeddings → Disk (`/app/rag_storage`)
3. **Runtime** : Streamlit charge l'index RAG depuis le disque partagé

---

## 3. Sécurité (Guardrails)

### 3.1 Niveau 1 : SQL Agent

| Menace | Mitigation | Implémentation |
|--------|------------|----------------|
| Injection SQL destructive | Blocklist DDL/DML | `apply_guardrails()` vérifie `INSERT/UPDATE/DELETE/DROP/ALTER` |
| Exfiltration massive | LIMIT forcé | Ajout auto `LIMIT 100` si pas d'aggregation |
| Timeout de requête | Statement timeout | `SET statement_timeout = '5s'` côté PostgreSQL |
| Accès table non autorisée | Allowlist | Vérification présence `VW_WINNERS/VW_TURNOUT/VW_RESULTS_CLEAN` |
| Prompt injection | Intent router | Classification `valid/out_of_domain/adversarial` via LLM |

### 3.2 Niveau 2 : Hybrid Router

- **Seuil de confiance** : 0.80 pour la décision SQL vs RAG
- **Clarification automatique** : Questions ambiguës déclenchent une question de précision
- **Fuzzy matching** : Correction typos avant recherche (score minimum 80/100)

### 3.3 Niveau 3 : Session Memory

- **Context isolation** : Entités stockées par session utilisateur Streamlit
- **Enrichissement contrôlé** : Injection contexte uniquement sur questions de suivi explicites

---

## 4. Performance et Optimisation

### 4.1 Indexation Vectorielle

| Aspect | Solution | Impact |
|--------|----------|--------|
| Cold start | Warmup container séparé | ~2min de build index hors runtime utilisateur |
| Persistence | Stockage disque `StorageContext` | Index chargé en ~3s au démarrage Streamlit |
| Recherche | Top-k = 5 | Réponse RAG < 2s après indexation |

### 4.2 Base de données

- **Vues matérialisées** : Non implémenté (dataset < 10k lignes), mais vues SQL pour abstraction
- **Index PostgreSQL** : Index implicites sur clés primaires (`code_circonscription`)
- **Connection pooling** : SQLAlchemy `create_engine` avec paramètres par défaut (suffisant pour la charge)

### 4.3 Caching

- **RAG index** : Persisté sur disque, chargé une seule fois par session Streamlit
- **Entity resolver** : Singleton pattern, chargement BDD au premier appel uniquement

---

## 5. Cas d'Usage Supportés

### Questions analytiques (SQL)

- "Quel candidat a gagné à Agboville ?"
- "Top 10 des partis par nombre de sièges"
- "Taux de participation dans chaque région"

### Questions narratives (RAG)

- "Résume les résultats de Tiapoum"
- "Quels sont les enjeux de cette élection ?"
- "Décris la situation politique à Korhogo"

### Visualisations automatiques

| Type | Déclencheur |
|------|-------------|
| Tableau | Données non-numériques ou 1 seule ligne |
| Bar chart | Comparaison de valeurs numériques (>1 ligne) |
| Pie chart | Répartition proportionnelle (optionnel via toggle) |

---

## 6. Limitations Connues

### 6.1 Fonctionnelles

- **Entity resolution SQL désactivée** : La correction automatique des typos (Tiapam → Tiapoum) fonctionne pour le RAG et la détection d'ambiguïté, mais pas pour la génération SQL (risque de faux positifs transformant des mots-clés valides)
- **Citations/provenance** : Les réponses RAG n'indiquent pas le numéro de page PDF source. Seul le `code_circonscription` est disponible comme identifiant de traçabilité.

### 6.2 Techniques

- **Premier démarrage** : ~4 minutes nécessaires (ingestion + warmup)
- **Scalabilité horizontale** : L'index RAG en mémoire n'est pas partageable entre instances (pas de Redis/vector DB centralisé)
- **Dépendances externes** : Nécessite connexion Internet (Ollama Cloud + Gemini)

### 6.3 Données

- **Dataset limité** : Élections locales ivoiriennes uniquement (pas de données présidentielles, pas de données historiques multi-années)
- **Qualité PDF** : Quelques erreurs d'OCR sur les caractères spéciaux dans les noms de candidats

---

## 7. Améliorations Futures

| Priorité | Amélioration |
|----------|--------------|
| P1 | Citations précises (page + tableau) |
| P1 | Entity resolution SQL fiable |
| P2 | Cache réponses fréquentes |
| P2 | Mode offline (LLM local) |
| P3 | Multi-élections (comparer années) |

---

## 8. Instructions de Déploiement

```bash
# 1. Cloner le repository
git clone https://github.com/Hydra16LeGrand/elections-ai-agent.git
cd elections-ai-agent

# 2. Configuration
cp .env.example .env
# Éditer .env avec OLLAMA_API_KEY et GEMINI_API_KEY

# 3. Lancement
docker compose up --build -d

# 4. Attendre le warmup apres le build (~4 min)
docker-compose logs -f ui
# Attendre "WARMUP COMPLET" dans les logs

# 5. Accès
# - Chatbot : http://localhost:8501
# - pgAdmin : http://localhost:8080 (admin@artefact.com / admin)
# - DB : localhost:5433 (artefact_reader / reader_password)
```

---

## 9. Informations Complémentaires

### Développement

Ce projet a été développé pour le test technique Artefact. **Claude** a été utilisé pour :

- Structurer le code initial
- Corriger des bugs
- Rédiger la documentation
- L'aide aux tests

L'architecture, la logique métier (routing, guardrails) et les choix techniques ont été faits manuellement.

### Stratégie Git

Workflow feature branch : une branche par niveau fonctionnel, merge sur `main` après stabilisation.

| Branche | Description | Statut |
|---------|-------------|--------|
| `main` | Branche stable, production-ready | Active |
| `feat/sql-agent` | Level 1 : Agent SQL + Guardrails | Merge vers main |
| `feat/hybrid-router` | Level 2 : Routing SQL/RAG + Fuzzy matching | Merge vers main |
| `feat/improved-agentic` | Level 3 : Session memory + Clarification | Merge vers main |

**Règles suivies** :
- Pas de commit direct sur `main`
- Tests passants avant chaque merge
- Messages de commit en anglais, format conventionnel (`feat:`, `fix:`, `docs:`)

### Structure du Repository

```
artefact/
├── app/                    # Application principale
│   ├── sql_agent.py        # Agent Text-to-SQL
│   ├── hybrid_router.py    # Routing SQL vs RAG
│   ├── entity_resolver.py  # Fuzzy matching
│   ├── rag_engine.py       # Index vectoriel LlamaIndex
│   └── ui.py               # Interface Streamlit
├── ingestion/              # Pipeline ELT
│   └── ingest.py
├── tests/                  # Tests par niveau
│   ├── level_1/           # Guardrails + Intent
│   ├── level_2/           # Hybrid + Entity + RAG
│   └── level_3/           # Session + Ambiguity
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

**Date de livraison** : 16 avril 2026  
**Version** : 1.0.0 (Levels 1, 2, 3 complets)  
**Branche** : feat/improved-agentic
