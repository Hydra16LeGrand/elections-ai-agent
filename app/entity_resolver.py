"""Module de résolution d'entités avec fuzzy matching."""

import os
from typing import Optional, List, Tuple
from thefuzz import fuzz, process
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


class EntityResolver:
    """Résolveur d'entités géographiques et politiques."""

    MIN_SCORE = 80

    def __init__(self, db_url: Optional[str] = None):
        """Initialise le résolveur avec les données de la base."""
        self.db_url = db_url or os.environ.get(
            "AGENT_DB_URL",
            "postgresql://artefact_reader:reader_password@db:5432/elections_db"
        )
        self.engine = create_engine(self.db_url)

        self._regions: List[str] = []
        self._localities: List[str] = []
        self._parties: List[str] = []
        self._candidates: List[str] = []
        self._load_entities()

    def _load_entities(self) -> None:
        """Charge les entités depuis la base."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT DISTINCT region FROM vw_results_clean"
                ))
                self._regions = [row[0] for row in result if row[0]]

                result = conn.execute(text(
                    "SELECT DISTINCT nom_circonscription FROM vw_results_clean"
                ))
                self._localities = [row[0] for row in result if row[0]]

                self._locality_words = {}
                for source in [self._regions, self._localities]:
                    for item in source:
                        import re
                        words = re.findall(r"[A-Z]['A-Z]+", item.upper())
                        for word in words:
                            if len(word) > 3:
                                self._locality_words[word] = item

                result = conn.execute(text(
                    "SELECT DISTINCT parti FROM vw_results_clean"
                ))
                self._parties = [row[0] for row in result if row[0]]

                result = conn.execute(text(
                    "SELECT DISTINCT candidat FROM vw_results_clean"
                ))
                self._candidates = [row[0] for row in result if row[0]]

        except Exception as e:
            print(f"Warning: Impossible de charger les entités: {e}")
            self._regions = []
            self._localities = []
            self._locality_words = {}
            self._parties = []
            self._candidates = []

    def resolve_region(self, raw_input: str) -> Tuple[str, float]:
        """Résout une région avec fuzzy matching."""
        if not self._regions:
            return raw_input, 0.0

        raw_upper = raw_input.upper()

        match, score = process.extractOne(
            raw_upper,
            [r.upper() for r in self._regions],
            scorer=fuzz.partial_ratio
        )

        if score >= self.MIN_SCORE:
            idx = [r.upper() for r in self._regions].index(match)
            return self._regions[idx], float(score)

        return raw_input, float(score)

    def resolve_locality(self, raw_input: str) -> Tuple[str, float]:
        """Résout une localité avec fuzzy matching."""
        if not self._localities:
            return raw_input, 0.0

        raw_upper = raw_input.upper()

        if self._locality_words:
            word_list = list(self._locality_words.keys())

            match, score = process.extractOne(
                raw_upper,
                word_list,
                scorer=fuzz.partial_ratio
            )

            if score >= self.MIN_SCORE:
                return self._locality_words[match], float(score)

        match, score = process.extractOne(
            raw_upper,
            [loc.upper() for loc in self._localities],
            scorer=fuzz.token_set_ratio
        )

        if score >= self.MIN_SCORE:
            idx = [loc.upper() for loc in self._localities].index(match)
            return self._localities[idx], float(score)

        return raw_input, float(score) if 'score' in locals() else 0.0

    def resolve_party(self, raw_input: str) -> Tuple[str, float]:
        """Résout un parti avec gestion des alias."""
        normalized = self._normalize_party_alias(raw_input)

        if not self._parties:
            return normalized, 0.0

        match, score = process.extractOne(
            normalized,
            self._parties,
            scorer=fuzz.partial_ratio
        )

        if score >= self.MIN_SCORE:
            return match, float(score)

        return normalized, float(score)

    def resolve_candidate(self, raw_input: str) -> Tuple[str, float]:
        """Résout un candidat avec fuzzy matching."""
        if not self._candidates:
            return raw_input, 0.0

        match, score = process.extractOne(
            raw_input,
            self._candidates,
            scorer=fuzz.token_sort_ratio
        )

        if score >= self.MIN_SCORE:
            return match, float(score)

        return raw_input, float(score)

    def _normalize_party_alias(self, party_name: str) -> str:
        """Normalise les alias de partis (RHDP, R.H.D.P, etc.)."""
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
        normalized_clean = normalized.replace(".", "").replace("-", "").replace(" ", "")

        for alias, canonical in aliases.items():
            if normalized == alias or normalized_clean == alias.replace(".", "").replace("-", "").replace(" ", ""):
                return canonical

        return party_name

    def resolve_question(self, question: str) -> Tuple[str, dict]:
        """Analyse une question et résout les entités."""
        corrected = question
        metadata = {
            "replacements": [],
            "confidence_scores": []
        }

        for locality in self._localities:
            words = question.split()
            for word in words:
                if len(word) > 3:
                    score = fuzz.ratio(word.lower(), locality.lower())
                    if 60 <= score < 100:
                        corrected = corrected.replace(word, locality)
                        metadata["replacements"].append({
                            "type": "locality",
                            "original": word,
                            "corrected": locality,
                            "score": score
                        })
                        break

        return corrected, metadata

    def get_locality_regions(self, locality: str) -> List[str]:
        """Retourne toutes les régions où cette localité existe."""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("SELECT DISTINCT region FROM vw_results_clean WHERE nom_circonscription = :locality"),
                    {"locality": locality}
                )
                return [row[0] for row in result if row[0]]
        except Exception:
            return []

    def is_ambiguous(self, entity_type: str, value: str) -> Tuple[bool, List[str]]:
        """Détecte si une entité est ambiguë (existe dans plusieurs contextes)."""
        if entity_type == "locality":
            regions = self.get_locality_regions(value)
            if len(regions) > 1:
                return True, regions
            return False, regions
        return False, []


_resolver_instance: Optional[EntityResolver] = None


def get_resolver() -> EntityResolver:
    """Retourne le singleton du résolveur."""
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = EntityResolver()
    return _resolver_instance


def resolve_locality_quick(raw_input: str) -> str:
    """Résout une localité sans instancier la classe."""
    resolver = get_resolver()
    corrected, _ = resolver.resolve_locality(raw_input)
    return corrected


if __name__ == "__main__":
    resolver = EntityResolver()

    print("Test Entity Resolver")

    test_cases = [
        ("Tiapam", "TIAPOUM"),
        ("Korhogo", "KORHOGO"),
        ("Bouna", "BOUNA"),
    ]
    for test_input, should_contain in test_cases:
        corrected, score = resolver.resolve_locality(test_input)
        status = "OK" if score >= 80 else "KO"
        print(f"  {status} '{test_input}' → '{corrected}' (score: {score:.1f})")
