# CI Elections - Data & AI Platform

Plateforme d'analyse des élections locales ivoiriennes intégrant un pipeline d'ingestion ELT et un agent conversationnel Text-to-SQL sécurisé.

## Architecture Principale

Le système repose sur la séparation stricte de deux couches :

1. **Couche Ingestion (Data Engineering) - `/ingestion`**
   - Extraction des données tabulaires complexes depuis le PDF source via `camelot`.
   - Nettoyage, standardisation et propagation géographique (Forward Fill).
   - Déploiement d'une couche sémantique PostgreSQL (Vues métier : `vw_winners`, `vw_turnout`, `vw_results_clean`) pour restreindre la portée des requêtes.
   - Application du principe de moindre privilège (RBAC) via la création d'un profil `ReadOnly` dédié à l'agent d'inférence.

2. **Couche Application (AI Engineering) - `/app`**
   - Agent Text-to-SQL implémentant une boucle de rétroaction (ReAct loop).
   - Intégration d'un routeur d'intention (Intent Router) pour la classification des requêtes.

## Architecture Decision Record (ADR) : Vanilla vs. Frameworks

La couche d'orchestration Text-to-SQL est développée en Python standard ("Vanilla") plutôt qu'au travers d'abstractions de type LangChain (`create_sql_agent`). Ce choix garantit la validation des contraintes de sécurité :

- **Routing Sémantique (Out of Domain) :** Les requêtes hors périmètre (ex: données présidentielles, météo) sont identifiées et rejetées par le routeur avant l'étape de traduction SQL, réduisant les risques d'hallucination.
- **Guardrails Déterministes :** La validation des requêtes (Allowlist des vues, blocage des instructions DDL/DML type `DROP`, enforcement du `LIMIT`) est gérée par des fonctions Python pures. Ce pare-feu applicatif offre une sécurité indépendante du modèle linguistique face aux tentatives d'injection (Adversarial Prompts).
- **Contrat de données structuré :** L'agent retourne systématiquement un dictionnaire typé (`narrative`, `data`, `sql`), condition préalable à la génération de graphiques dynamiques sur le front-end.

## Lancement Rapide (Docker)

Le projet est entièrement conteneurisé pour garantir une reproductibilité stricte de l'environnement de développement.

### Prérequis
- Docker & Docker Compose
- Une clé API compatible OpenAI (configurée pour Ollama Cloud dans ce setup)

### Procédure de déploiement

1. **Préparation de l'environnement :**
   Copier le template de configuration et renseigner les variables critiques (notamment `OLLAMA_API_KEY`).
   ```bash
   cp .env.example .env
   ```
2. **Déploiement de l'infrastructure :**
   La commande suivante instancie PostgreSQL, initialise les tables/vues via le script d'ingestion, et démarre l'interface utilisateur.
   ```bash
   docker-compose up --build -d
   ```
3. **Accès aux services :**

   - Base de données locale (débogage) : localhost:5433
   - Interface Web : http://localhost:8501 (en cours d'intégration)