"""
Tests unitaires pour les fonctions de sécurité SQL (Guardrails - Bonus A).

Ce module teste exhaustivement la fonction apply_guardrails qui valide
et sécurise les requêtes SQL générées par l'agent.
"""

import pytest
from app.sql_agent import apply_guardrails


class TestValidQueries:
    """Tests pour les requêtes SQL valides sur les vues autorisées."""

    @pytest.mark.guardrails
    @pytest.mark.parametrize("query,view_name", [
        ("SELECT candidat, parti FROM vw_winners WHERE region = 'Abidjan'", "vw_winners"),
        ("SELECT * FROM vw_winners LIMIT 10", "vw_winners"),
        ("SELECT region, taux_participation FROM vw_turnout", "vw_turnout"),
        ("SELECT code_circonscription, votants FROM vw_turnout WHERE region = 'Bouaké'", "vw_turnout"),
        ("SELECT candidat, voix FROM vw_results_clean WHERE est_elu = true", "vw_results_clean"),
        ("SELECT * FROM vw_results_clean", "vw_results_clean"),
    ])
    def test_valid_queries_on_allowed_views(self, query, view_name):
        """
        Vérifie que les requêtes sur les vues autorisées passent les guardrails.

        Les trois vues (vw_winners, vw_turnout, vw_results_clean) doivent être
        accessibles en lecture seule.
        """
        is_safe, final_sql, error = apply_guardrails(query)

        assert is_safe is True, f"La requête sur {view_name} devrait être acceptée"
        assert error == "", "Aucun message d'erreur ne devrait être retourné pour une requête valide"
        assert view_name.upper() in final_sql.upper()

    @pytest.mark.guardrails
    def test_query_case_insensitive_views(self):
        """
        Vérifie que la détection des vues est insensible à la casse.

        Les vues en minuscules, majuscules ou mixtes doivent toutes être reconnues.
        """
        queries = [
            "select * from vw_winners",
            "SELECT * FROM VW_WINNERS",
            "Select * From Vw_Winners",
            "SELECT * FROM Vw_Turnout",
            "select * from vw_RESULTS_clean",
        ]

        for query in queries:
            is_safe, _, error = apply_guardrails(query)
            assert is_safe is True, f"La requête '{query}' devrait être acceptée (insensible à la casse)"
            assert error == ""


class TestForbiddenOperations:
    """Tests pour les opérations SQL destructrices qui doivent être bloquées."""

    @pytest.mark.guardrails
    @pytest.mark.security
    @pytest.mark.parametrize("query,operation", [
        ("DROP TABLE users", "DROP"),
        ("DROP TABLE IF EXISTS vw_winners", "DROP"),
        ("DELETE FROM vw_winners WHERE 1=1", "DELETE"),
        ("DELETE FROM vw_turnout", "DELETE"),
        ("INSERT INTO vw_winners VALUES ('test', 'test')", "INSERT"),
        ("INSERT INTO vw_results_clean (candidat) VALUES ('hacker')", "INSERT"),
        ("UPDATE vw_winners SET candidat = 'hacked'", "UPDATE"),
        ("UPDATE vw_turnout SET votants = 0", "UPDATE"),
        ("ALTER TABLE vw_winners ADD COLUMN hacked BOOLEAN", "ALTER"),
        ("TRUNCATE TABLE vw_winners", "TRUNCATE"),
        ("GRANT ALL ON vw_winners TO public", "GRANT"),
        ("REVOKE ALL ON vw_winners FROM public", "REVOKE"),
    ])
    def test_forbidden_keywords_blocked(self, query, operation):
        """
        Vérifie que les opérations destructrices sont bloquées.

        Les mots-clés INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, GRANT, REVOKE
        doivent tous déclencher un rejet avec le message approprié.
        """
        is_safe, final_sql, error = apply_guardrails(query)

        assert is_safe is False, f"La requête avec {operation} devrait être bloquée"
        assert "Opération destructive" in error, f"Le message d'erreur devrait mentionner 'Opération destructive' pour {operation}"
        assert final_sql == query.rstrip(';'), "La requête originale (sans point-virgule) devrait être retournée"

    @pytest.mark.guardrails
    @pytest.mark.security
    def test_forbidden_keywords_case_insensitive(self):
        """
        Vérifie que la détection des mots interdits est insensible à la casse.

        'drop', 'DROP', 'Drop', 'dRoP' doivent tous être détectés.
        """
        queries = [
            "drop table users",
            "DROP TABLE users",
            "Drop Table users",
            "dRoP TaBlE users",
            "delete from vw_winners",
            "DELETE FROM vw_winners",
            "UPDATE vw_winners SET x=1",
            "insert into vw_winners values (1)",
        ]

        for query in queries:
            is_safe, _, error = apply_guardrails(query)
            assert is_safe is False, f"La requête '{query}' devrait être bloquée (insensible à la casse)"
            assert "Opération destructive" in error


class TestAllowlistEnforcement:
    """Tests pour l'allowlist des tables/vues autorisées."""

    @pytest.mark.guardrails
    @pytest.mark.security
    def test_raw_table_blocked(self):
        """
        Vérifie que l'accès à la table brute raw_election_data est bloqué.

        Même une requête SELECT simple sur la table brute doit être rejetée.
        """
        query = "SELECT * FROM raw_election_data"
        is_safe, _, error = apply_guardrails(query)

        assert is_safe is False, "L'accès à raw_election_data devrait être bloqué"
        assert "Allowlist" in error or "non autorisée" in error, "Le message d'erreur devrait mentionner l'allowlist"

    @pytest.mark.guardrails
    @pytest.mark.security
    def test_raw_table_case_insensitive_blocked(self):
        """
        Vérifie que la détection de raw_election_data est insensible à la casse.
        """
        queries = [
            "SELECT * FROM raw_election_data",
            "SELECT * FROM RAW_ELECTION_DATA",
            "SELECT * FROM Raw_Election_Data",
        ]

        for query in queries:
            is_safe, _, error = apply_guardrails(query)
            assert is_safe is False, f"L'accès via '{query}' devrait être bloqué"

    @pytest.mark.guardrails
    @pytest.mark.security
    def test_mixed_valid_and_forbidden_tables(self):
        """
        Vérifie qu'une requête mixant vue autorisée et table interdite est bloquée.

        Les requêtes avec UNION, JOIN ou sous-requêtes accédant à raw_election_data
        doivent être rejetées.
        """
        queries = [
            "SELECT * FROM vw_winners UNION SELECT * FROM raw_election_data",
            "SELECT * FROM vw_winners JOIN raw_election_data ON 1=1",
            "SELECT * FROM (SELECT * FROM raw_election_data) AS subquery",
        ]

        for query in queries:
            is_safe, _, error = apply_guardrails(query)
            assert is_safe is False, f"La requête '{query}' devrait être bloquée car elle accède à raw_election_data"

    @pytest.mark.guardrails
    def test_query_without_allowed_view_blocked(self):
        """
        Vérifie qu'une requête ne touchant aucune vue autorisée est bloquée.

        Une requête comme 'SELECT 1' ou sur une table non autorisée doit échouer.
        """
        queries = [
            "SELECT 1",
            "SELECT * FROM pg_tables",
            "SELECT * FROM information_schema.tables",
            "SELECT * FROM users",
        ]

        for query in queries:
            is_safe, _, error = apply_guardrails(query)
            assert is_safe is False, f"La requête '{query}' devrait être bloquée (pas de vue autorisée)"


class TestLimitEnforcement:
    """Tests pour l'ajout automatique du LIMIT."""

    @pytest.mark.guardrails
    @pytest.mark.parametrize("query", [
        "SELECT * FROM vw_winners",
        "SELECT candidat, parti FROM vw_winners WHERE region = 'Abidjan'",
        "SELECT * FROM vw_turnout WHERE taux_participation > 50",
        "SELECT code_circonscription FROM vw_results_clean",
    ])
    def test_limit_added_when_missing(self, query):
        """
        Vérifie que LIMIT 100 est ajouté automatiquement aux requêtes simples.

        Les requêtes sans clause LIMIT doivent se voir ajouter 'LIMIT 100'.
        """
        is_safe, final_sql, error = apply_guardrails(query)

        assert is_safe is True
        assert "LIMIT 100" in final_sql, f"LIMIT 100 devrait être ajouté à la requête: {final_sql}"

    @pytest.mark.guardrails
    def test_limit_not_added_when_present(self):
        """
        Vérifie qu'on ne double pas un LIMIT déjà présent.

        Si la requête contient déjà un LIMIT, il ne doit pas être modifié.
        """
        query = "SELECT * FROM vw_winners LIMIT 50"
        is_safe, final_sql, error = apply_guardrails(query)

        assert is_safe is True
        assert final_sql == query, "La requête avec LIMIT existant ne devrait pas être modifiée"

    @pytest.mark.guardrails
    @pytest.mark.parametrize("query", [
        "SELECT region, SUM(voix) FROM vw_results_clean GROUP BY region",
        "SELECT COUNT(*) FROM vw_winners",
        "SELECT AVG(taux_participation) FROM vw_turnout",
        "SELECT MIN(votants), MAX(votants) FROM vw_turnout",
        "SELECT region, parti, COUNT(*) FROM vw_winners GROUP BY region, parti",
        "SELECT region, SUM(voix), AVG(pourcentage) FROM vw_results_clean GROUP BY region",
    ])
    def test_limit_not_added_for_aggregations(self, query):
        """
        Vérifie que LIMIT n'est PAS ajouté aux requêtes d'agrégation.

        Les requêtes avec SUM, COUNT, AVG, MIN, MAX ou GROUP BY ne doivent pas
        recevoir de LIMIT automatique car cela perturberait les résultats d'agrégation.
        """
        is_safe, final_sql, error = apply_guardrails(query)

        assert is_safe is True
        assert "LIMIT" not in final_sql.upper(), f"LIMIT ne devrait pas être ajouté aux agrégations: {final_sql}"

    @pytest.mark.guardrails
    def test_limit_detection_case_insensitive(self):
        """
        Vérifie que la détection du LIMIT est insensible à la casse.
        """
        queries = [
            "select * from vw_winners limit 50",
            "SELECT * FROM vw_winners LIMIT 50",
            "Select * From vw_winners Limit 50",
        ]

        for query in queries:
            is_safe, final_sql, error = apply_guardrails(query)
            assert is_safe is True
            assert final_sql == query, f"La requête avec limit détecté ne devrait pas être modifiée: {query}"


class TestQueryNormalization:
    """Tests pour la normalisation des requêtes."""

    @pytest.mark.guardrails
    def test_trailing_semicolon_removed(self):
        """
        Vérifie que le point-virgule final est retiré.

        Le point-virgule est retiré pour faciliter l'ajout du LIMIT si nécessaire.
        """
        query = "SELECT * FROM vw_winners;"
        is_safe, final_sql, error = apply_guardrails(query)

        assert is_safe is True
        assert not final_sql.endswith(";"), "Le point-virgule final devrait être retiré"
        assert final_sql == "SELECT * FROM vw_winners LIMIT 100"

    @pytest.mark.guardrails
    def test_leading_trailing_whitespace_removed(self):
        """
        Vérifie que les espaces en début et fin sont retirés.
        """
        query = "   SELECT * FROM vw_winners   "
        is_safe, final_sql, error = apply_guardrails(query)

        assert is_safe is True
        assert not final_sql.startswith(" "), "Les espaces de début devraient être retirés"
        assert not final_sql.endswith(" "), "Les espaces de fin devraient être retirés"


class TestEdgeCases:
    """Tests pour les cas limites et edge cases."""

    @pytest.mark.guardrails
    def test_empty_query(self):
        """
        Vérifie le comportement avec une requête vide.
        """
        query = ""
        is_safe, _, error = apply_guardrails(query)

        # Une requête vide ne passe pas l'allowlist car elle ne contient pas de vue autorisée
        assert is_safe is False

    @pytest.mark.guardrails
    def test_whitespace_only_query(self):
        """
        Vérifie le comportement avec une requête contenant uniquement des espaces.
        """
        query = "   \n\t   "
        is_safe, _, error = apply_guardrails(query)

        assert is_safe is False

    @pytest.mark.guardrails
    def test_subquery_injection_attempt(self):
        """
        Vérifie que les tentatives d'injection via sous-requêtes sont détectées.
        """
        queries = [
            "SELECT * FROM vw_winners WHERE 1=1; DROP TABLE users; --",
            "SELECT * FROM vw_winners; DELETE FROM vw_winners; --",
        ]

        for query in queries:
            is_safe, _, error = apply_guardrails(query)
            assert is_safe is False, f"La tentative d'injection '{query}' devrait être bloquée"

    @pytest.mark.guardrails
    def test_union_injection_attempt(self):
        """
        Vérifie que les tentatives d'injection via UNION sont gérées.
        """
        query = "SELECT * FROM vw_winners UNION SELECT * FROM raw_election_data"
        is_safe, _, error = apply_guardrails(query)

        assert is_safe is False, "L'injection via UNION avec table interdite devrait être bloquée"
