"""
Module de résolution d'entités avec fuzzy matching.
Corrige automatiquement les fautes de frappe sur les noms de communes,
candidats et partis politiques.
"""

import os
from typing import Optional, List, Tuple
from thefuzz import fuzz, process
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


class EntityResolver:
    """
    Résolveur d'entités géographiques et politiques.

    Utilise le fuzzy matching (Levenshtein distance) pour corriger
    automatiquement les typos dans les noms de localités et partis.
    """

    # Seuil de similarité minimum (0-100)
    # 80 = tolérant aux petites fautes, strict sur les grosses erreurs
    MIN_SCORE = 80

    def __init__(self, db_url: Optional[str] = None):
        """
        Initialise le résolveur avec les données de la base.

        Args:
            db_url: URL de connexion PostgreSQL. Si None, utilise AGENT_DB_URL env.
        """
        self.db_url = db_url or os.environ.get(
            "AGENT_DB_URL",
            "postgresql://artefact_reader:reader_password@localhost:5433/elections_db"
        )
        self.engine = create_engine(self.db_url)

        # Chargement des entités depuis la BDD
        self._regions: List[str] = []           # ← AJOUT: régions
        self._localities: List[str] = []
        self._parties: List[str] = []
        self._candidates: List[str] = []
        self._load_entities()

    def _load_entities(self) -> None:
        """
        Charge les entités uniques depuis la couche sémantique.
        Construit aussi un index des mots individuels pour fuzzy matching.
        """
        try:
            with self.engine.connect() as conn:
                # Régions (noms de régions)
                result = conn.execute(text(
                    "SELECT DISTINCT region FROM vw_results_clean"
                ))
                self._regions = [row[0] for row in result if row[0]]

                # Localités (circonscriptions complètes)
                result = conn.execute(text(
                    "SELECT DISTINCT nom_circonscription FROM vw_results_clean"
                ))
                self._localities = [row[0] for row in result if row[0]]

                # Index des mots individuels extraits des localités ET régions
                # Ex: "NOE, NOUAMOU ET TIAPOUM" → ["NOE", "NOUAMOU", "TIAPOUM"]
                self._locality_words = {}
                for source in [self._regions, self._localities]:
                    for item in source:
                        import re
                        words = re.findall(r"[A-Z]['A-Z]+", item.upper())
                        for word in words:
                            if len(word) > 3:  # Ignorer les mots courts
                                self._locality_words[word] = item

                # Partis
                result = conn.execute(text(
                    "SELECT DISTINCT parti FROM vw_results_clean"
                ))
                self._parties = [row[0] for row in result if row[0]]

                # Candidats
                result = conn.execute(text(
                    "SELECT DISTINCT candidat FROM vw_results_clean"
                ))
                self._candidates = [row[0] for row in result if row[0]]

        except Exception as e:
            print(f"Warning: Impossible de charger les entités depuis la BDD: {e}")
            # Fallback sur listes vides
            self._regions = []
            self._localities = []
            self._locality_words = {}
            self._parties = []
            self._candidates = []

    def resolve_region(self, raw_input: str) -> Tuple[str, float]:
        """
        Résout une région avec fuzzy matching.

        Args:
            raw_input: Nom de la région potentiellement mal orthographié

        Returns:
            Tuple (nom_corrigé, score_de_confiance)
        """
        if not self._regions:
            return raw_input, 0.0

        raw_upper = raw_input.upper()

        # Fuzzy matching sur les noms de régions
        match, score = process.extractOne(
            raw_upper,
            [r.upper() for r in self._regions],
            scorer=fuzz.partial_ratio  # Bon pour les sous-chaînes
        )

        if score >= self.MIN_SCORE:
            idx = [r.upper() for r in self._regions].index(match)
            return self._regions[idx], float(score)

        return raw_input, float(score)

    def resolve_locality(self, raw_input: str) -> Tuple[str, float]:
        """
        Résout une localité (nom de circonscription) avec fuzzy matching.
        Gère aussi la recherche dans les noms composés (ex: "Tiapoum" dans
        "TIAPOUM, SOUS-PREFECTURE").

        Args:
            raw_input: Nom potentiellement mal orthographié

        Returns:
            Tuple (nom_corrigé, score_de_confiance)
        """
        if not self._localities:
            return raw_input, 0.0

        # Normalisation : majuscules pour comparaison
        raw_upper = raw_input.upper()

        # Essai 1: Fuzzy matching sur les mots individuels extraits
        # Permet de trouver "Tiapam" → "TIAPOUM" même dans les noms composés
        if self._locality_words:
            word_list = list(self._locality_words.keys())

            # Utilise partial_ratio pour tolérer les fautes de frappe (ex: Tiapam/Tiapoum)
            match, score = process.extractOne(
                raw_upper,
                word_list,
                scorer=fuzz.partial_ratio
            )

            if score >= self.MIN_SCORE:
                # Retrouve la localité complète associée à ce mot
                return self._locality_words[match], float(score)

        # Essai 2: Sur les noms complets si le mot n'est pas dans l'index
        match, score = process.extractOne(
            raw_upper,
            [loc.upper() for loc in self._localities],
            scorer=fuzz.token_set_ratio
        )

        if score >= self.MIN_SCORE:
            idx = [loc.upper() for loc in self._localities].index(match)
            return self._localities[idx], float(score)

        # Fallback: retourne l'input original
        return raw_input, float(score) if 'score' in locals() else 0.0

    def resolve_party(self, raw_input: str) -> Tuple[str, float]:
        """
        Résout un parti politique avec fuzzy matching.

        Gère également les alias courants (RHDP, R.H.D.P, etc.)

        Args:
            raw_input: Nom du parti potentiellement mal orthographié

        Returns:
            Tuple (nom_corrigé, score_de_confiance)
        """
        # Normalisation des alias communs avant fuzzy matching
        normalized = self._normalize_party_alias(raw_input)

        if not self._parties:
            return normalized, 0.0

        match, score = process.extractOne(
            normalized,
            self._parties,
            scorer=fuzz.partial_ratio  # Meilleur pour les partis avec suffixes (PDCI-RDA)
        )

        if score >= self.MIN_SCORE:
            return match, float(score)

        return normalized, float(score)

    def resolve_candidate(self, raw_input: str) -> Tuple[str, float]:
        """
        Résout un nom de candidat avec fuzzy matching.

        Args:
            raw_input: Nom du candidat potentiellement mal orthographié

        Returns:
            Tuple (nom_corrigé, score_de_confiance)
        """
        if not self._candidates:
            return raw_input, 0.0

        match, score = process.extractOne(
            raw_input,
            self._candidates,
            scorer=fuzz.token_sort_ratio  # Meilleur pour les noms composés
        )

        if score >= self.MIN_SCORE:
            return match, float(score)

        return raw_input, float(score)

    def _normalize_party_alias(self, party_name: str) -> str:
        """
        Normalise les alias courants des partis avant fuzzy matching.

        Args:
            party_name: Nom brut du parti

        Returns:
            Nom normalisé
        """
        # Mapping des alias connus
        aliases = {
            "rhdp": "RHDP",
            "r.h.d.p": "RHDP",
            "r-h-d-p": "RHDP",
            "r h d p": "RHDP",
            "rhd": "RHDP",
            "pdci": "PDCI",
            "p.d.c.i": "PDCI",
            "fpi": "FPI",
            "f.p.i": "FPI",
        }

        normalized = party_name.strip().lower()

        # Suppression des points et tirets pour normalisation
        normalized_clean = normalized.replace(".", "").replace("-", "").replace(" ", "")

        for alias, canonical in aliases.items():
            if normalized == alias or normalized_clean == alias.replace(".", "").replace("-", "").replace(" ", ""):
                return canonical

        return party_name

    def resolve_question(self, question: str) -> Tuple[str, dict]:
        """
        Analyse une question complète et résout toutes les entités détectées.

        Args:
            question: Question en langage naturel

        Returns:
            Tuple (question_corrigée, metadata)
            metadata contient les remplacements effectués et leurs scores.
        """
        corrected = question
        metadata = {
            "replacements": [],
            "confidence_scores": []
        }

        # Recherche de localités dans la question
        for locality in self._localities:
            # Vérifie si une version mal orthographiée pourrait correspondre
            words = question.split()
            for word in words:
                if len(word) > 3:  # Ignore les petits mots
                    score = fuzz.ratio(word.lower(), locality.lower())
                    if 60 <= score < 100:  # Potentiellement une typo
                        corrected = corrected.replace(word, locality)
                        metadata["replacements"].append({
                            "type": "locality",
                            "original": word,
                            "corrected": locality,
                            "score": score
                        })
                        break

        return corrected, metadata


# Instance singleton pour réutilisation
_resolver_instance: Optional[EntityResolver] = None


def get_resolver() -> EntityResolver:
    """
    Retourne l'instance singleton du résolveur.
    """
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = EntityResolver()
    return _resolver_instance


def resolve_locality_quick(raw_input: str) -> str:
    """
    Fonction rapide pour résoudre une localité sans instancier la classe.

    Args:
        raw_input: Nom de la localité

    Returns:
        Nom corrigé ou input original si pas de match.
    """
    resolver = get_resolver()
    corrected, _ = resolver.resolve_locality(raw_input)
    return corrected


if __name__ == "__main__":
    # Tests manuels
    resolver = EntityResolver()

    print("=== Test Entity Resolver ===")
    print()

    # Test régions
    print("Régions:")
    test_regions = [
        ("Abidjan", "ABIDJAN"),     # Devrait trouver "DISTRICT AUTONOME D'ABIDJAN"
        ("Bounkani", "BOUNKANI"),   # Exact
        ("Gontougo", "GONTOUGO"),   # Exact
    ]
    for test_input, should_contain in test_regions:
        corrected, score = resolver.resolve_region(test_input)
        status = "✓" if score >= 80 else "~" if score >= 60 else "✗"
        found = should_contain in corrected.upper()
        match_info = "[OK]" if found else f"[devrait contenir: {should_contain}]"
        print(f"  {status} '{test_input}' → '{corrected}' (score: {score:.1f}) {match_info}")

    print()

    # Test localités (basé sur les vraies données de la BDD)
    # Note: Les localités dans ce dataset ont des noms composés
    test_cases = [
        ("Tiapam", "TIAPOUM"),      # Faute: Tiapam → trouve Tiapoum (dans nom composé)
        ("Korhogo", "KORHOGO"),     # Exact
        ("Bouna", "BOUNA"),         # Exact
        ("Tiapoum", "TIAPOUM"),     # Exact
    ]
    print("Localités:")
    for test_input, should_contain in test_cases:
        corrected, score = resolver.resolve_locality(test_input)
        status = "✓" if score >= 80 else "~" if score >= 60 else "✗"
        found = should_contain in corrected.upper()
        match_info = "[OK]" if found else f"[devrait contenir: {should_contain}]"
        print(f"  {status} '{test_input}' → '{corrected}' (score: {score:.1f}) {match_info}")

    print()

    # Test partis
    test_parties = ["RHDP", "r.h.d.p", "pdci", "RHD"]
    print("Partis:")
    for party in test_parties:
        corrected, score = resolver.resolve_party(party)
        status = "✓" if score >= 80 else "✗"
        print(f"  {status} '{party}' → '{corrected}' (score: {score:.1f})")
