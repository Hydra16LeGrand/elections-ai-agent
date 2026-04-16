#!/bin/bash
set -e

# Script d'initialisation PostgreSQL
# Crée le rôle artefact_reader pour l'accès en lecture seule

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Création du rôle en lecture seule
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'artefact_reader') THEN
            CREATE ROLE artefact_reader WITH LOGIN PASSWORD 'reader_password';
        END IF;
    END
    \$\$;

    -- Accès de base
    GRANT CONNECT ON DATABASE $POSTGRES_DB TO artefact_reader;
    GRANT USAGE ON SCHEMA public TO artefact_reader;
EOSQL

echo "Rôle artefact_reader créé avec succès"
