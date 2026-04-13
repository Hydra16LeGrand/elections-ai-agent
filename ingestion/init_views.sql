-- =====================================================================================
-- PIPELINE ELT : IMPLÉMENTATION PRINCIPALE (COUCHE SILVER)
-- Description : Transformation des données textuelles brutes en structures analytiques typées.
-- =====================================================================================

-- Vue Silver : Localités (Typage et nettoyage des données)
CREATE OR REPLACE VIEW vw_localities_clean AS
SELECT DISTINCT
    raw_code_circonscription AS code_circonscription,
    raw_region AS region,
    raw_nom_circonscription AS nom_circonscription,
    CAST(NULLIF(REPLACE(raw_nb_bv, ' ', ''), '') AS INTEGER) AS nb_bv,
    CAST(NULLIF(REPLACE(raw_inscrits, ' ', ''), '') AS INTEGER) AS inscrits,
    CAST(NULLIF(REPLACE(raw_votants, ' ', ''), '') AS INTEGER) AS votants,
    CAST(REPLACE(REPLACE(raw_taux_part, '%', ''), ',', '.') AS FLOAT) AS taux_participation,
    CAST(NULLIF(REPLACE(raw_bull_nuls, ' ', ''), '') AS INTEGER) AS bulletins_nuls,
    CAST(NULLIF(REPLACE(raw_bull_blancs_nb, ' ', ''), '') AS INTEGER) AS bulletins_blancs_nb,
    CAST(REPLACE(REPLACE(raw_bull_blancs_pct, '%', ''), ',', '.') AS FLOAT) AS bulletins_blancs_pct,
    CAST(NULLIF(REPLACE(raw_suf_exprimes, ' ', ''), '') AS INTEGER) AS suffrages_exprimes
FROM raw_election_data;

-- Vue Silver : Candidats (Typage et création d'un indicateur booléen)
CREATE OR REPLACE VIEW vw_candidates_clean AS
SELECT 
    raw_code_circonscription AS code_circonscription,
    raw_parti AS parti,
    raw_candidat AS candidat,
    CAST(NULLIF(REPLACE(raw_voix, ' ', ''), '') AS INTEGER) AS voix,
    CAST(REPLACE(REPLACE(raw_pourcentage, '%', ''), ',', '.') AS FLOAT) AS pourcentage,
    CASE WHEN raw_elu ILIKE '%ELU%' THEN TRUE ELSE FALSE END AS est_elu
FROM raw_election_data;


-- =====================================================================================
-- PIPELINE ELT : IMPLÉMENTATION BONUS (COUCHE GOLD - COUCHE SÉMANTIQUE)
-- Objectif : Exigence Bonus du Test Artefact [cf. Lignes 67-68 de l'énoncé]
-- Description : Vues métier conçues strictement pour limiter les hallucinations du LLM et 
-- simplifier la génération Text-to-SQL. Aucune jointure (JOIN) ne sera requise de la part de l'agent.
-- =====================================================================================

-- Vue Gold : Vainqueurs uniquement
CREATE OR REPLACE VIEW vw_winners AS
SELECT 
    l.code_circonscription,
    l.region,
    l.nom_circonscription,
    c.parti,
    c.candidat,
    c.voix,
    c.pourcentage
FROM vw_candidates_clean c
JOIN vw_localities_clean l ON c.code_circonscription = l.code_circonscription
WHERE c.est_elu = TRUE;

-- Vue Gold : Statistiques géographiques et de participation (Prévient les doubles comptages par le LLM)
CREATE OR REPLACE VIEW vw_turnout AS
SELECT 
    code_circonscription,
    region,
    nom_circonscription,
    nb_bv,
    inscrits,
    votants,
    taux_participation,
    bulletins_nuls,
    bulletins_blancs_nb,
    bulletins_blancs_pct,
    suffrages_exprimes
FROM vw_localities_clean;

-- Vue Gold : Vue principale consolidée pour les métriques générales des candidats
CREATE OR REPLACE VIEW vw_results_clean AS
SELECT 
    l.code_circonscription,
    l.region,
    l.nom_circonscription,
    c.parti,
    c.candidat,
    c.voix,
    c.pourcentage,
    c.est_elu
FROM vw_candidates_clean c
JOIN vw_localities_clean l ON c.code_circonscription = l.code_circonscription;


-- =====================================================================================
-- OPTIMISATION DES PERFORMANCES
-- Description : Index de base pour les requêtes structurées et les futures implémentations RAG.
-- =====================================================================================
CREATE INDEX IF NOT EXISTS idx_raw_code_circo ON raw_election_data (raw_code_circonscription);
CREATE INDEX IF NOT EXISTS idx_raw_parti ON raw_election_data (raw_parti);
CREATE INDEX IF NOT EXISTS idx_raw_candidat ON raw_election_data (raw_candidat);


-- =====================================================================================
-- IMPLÉMENTATION BONUS : SÉCURITÉ DE LA BASE DE DONNÉES (RBAC)
-- Objectif : Exigence de Sécurité du Test Artefact [cf. Lignes 66-68 de l'énoncé]
-- Description : Application de contraintes strictes de lecture seule (Read-Only) au niveau 
-- de la base de données pour protéger contre les injections SQL adverses (ex: DROP TABLE).
-- =====================================================================================

-- Révocation des accès par défaut au schéma public
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Création du rôle en lecture seule (s'il n'existe pas)
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = 'artefact_reader') THEN
      CREATE ROLE artefact_reader WITH LOGIN PASSWORD 'reader_password';
   END IF;
END
$do$;

-- Octroi d'un accès restreint en lecture UNIQUEMENT à la couche sémantique
GRANT CONNECT ON DATABASE elections_db TO artefact_reader;
GRANT USAGE ON SCHEMA public TO artefact_reader;
GRANT SELECT ON vw_winners, vw_turnout, vw_results_clean TO artefact_reader;

-- Interdiction explicite de l'accès aux données brutes ingérées
REVOKE ALL PRIVILEGES ON raw_election_data FROM artefact_reader;