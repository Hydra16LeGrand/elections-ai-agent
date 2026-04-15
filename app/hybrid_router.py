"""Module de routage hybride SQL vs RAG."""

import os
import json
import re
from typing import Dict, Optional
from ollama import Client
from dotenv import load_dotenv
from app.entity_resolver import EntityResolver, get_resolver

load_dotenv()

OLLAMA_HOST = "https://ollama.com"
MODEL_ROUTER = "qwen3-coder-next"

CONFIDENCE_THRESHOLD = 0.80

client = Client(
    host=OLLAMA_HOST,
    headers={'Authorization': f"Bearer {os.environ.get('OLLAMA_API_KEY')}"}
)


# Prompts de classification

ROUTER_PROMPT = """Tu es un routeur intelligent qui analyse les questions d'utilisateurs sur des données électorales.

Ta mission : Décider si la question doit être traitée par :
- SQL : Pour les questions analytiques (chiffres, comptages, classements, pourcentages)
- RAG : Pour les questions narratives (résumés, explications, contexte, analyse qualitative)
- AMBIGUOUS : Si tu ne peux pas décider avec certitude

RÈGLES DE CLASSIFICATION :

Route SQL si la question demande :
- Des chiffres précis (combien, nombre, total, somme)
- Des classements (top, meilleur, premier)
- Des pourcentages ou taux (participation, score)
- Des comparaisons chiffrées
- Des listes de résultats structurés

Exemples SQL :
- "Combien de bulletins nuls ?"
- "Quel candidat a obtenu le plus de voix ?"
- "Top 10 des partis par nombre de sièges"
- "Taux de participation à Abidjan"
- "Liste des élus du RHDP"

Route RAG si la question demande :
- Un résumé des résultats
- Une explication ou analyse
- Du contexte général
- Une synthèse narrative
- Des informations descriptives

Exemples RAG :
- "Résume les résultats de cette élection"
- "Explique la répartition géographique des votes"
- "Donne un aperçu des tendances"
- "Quels sont les faits marquants ?"

RÉPONSE ATTENDUE :
Réponds UNIQUEMENT avec un objet JSON valide au format :
{"route": "sql|rag|ambiguous", "confidence": 0.95, "reasoning": "explication courte"}

La confiance (confidence) doit être entre 0.0 et 1.0.
"""


CLARIFICATION_PROMPT = """Tu as reçu une question ambiguë d'un utilisateur sur des données électorales.

Question : {question}

Cette question peut être interprétée de deux façons :
1. Demande de données chiffrées précises (SQL)
2. Demande de résumé ou explication narrative (RAG)

Génère une question de clarification courte et polie pour demander à l'utilisateur ce qu'il préfère.

Réponds UNIQUEMENT avec la question de clarification, sans autre texte.
"""

ENTITY_CLARIFICATION_PROMPT = """L'utilisateur a mentionné une localité qui existe dans plusieurs régions.

Localité : {locality}
Régions disponibles : {regions}

Génère une question de clarification courte et polie pour demander à l'utilisateur de préciser quelle région il souhaite.

Réponds UNIQUEMENT avec la question de clarification, sans autre texte.
"""


def detect_entity_ambiguity(question: str) -> Optional[dict]:
    """Détecte si une entité dans la question est ambiguë."""
    resolver = get_resolver()

    words = question.split()
    for word in words:
        if len(word) < 3:
            continue

        resolved, score = resolver.resolve_locality(word)
        if score < 80:
            continue

        is_ambig, regions = resolver.is_ambiguous("locality", resolved)
        if is_ambig:
            return {
                "ambiguous": True,
                "entity_type": "locality",
                "entity_value": resolved,
                "options": regions
            }

    return None


def classify_question(question: str) -> Dict[str, any]:
    """Classe une question en SQL, RAG ou AMBIGUOUS."""
    try:
        response = client.chat(
            model=MODEL_ROUTER,
            messages=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": f"Question: {question}"}
            ],
            options={"temperature": 0.1}
        )

        content = response['message']['content'].strip()
        clean_json = re.sub(r"^```json|```$", "", content, flags=re.MULTILINE).strip()
        result = json.loads(clean_json)

        route = result.get("route", "ambiguous")
        confidence = float(result.get("confidence", 0.5))
        reasoning = result.get("reasoning", "")

        if route not in ["sql", "rag", "ambiguous"]:
            route = "ambiguous"

        return {
            "route": route,
            "confidence": confidence,
            "reasoning": reasoning
        }

    except json.JSONDecodeError:
        return {
            "route": "ambiguous",
            "confidence": 0.0,
            "reasoning": "Erreur de parsing JSON"
        }
    except Exception as e:
        return {
            "route": "ambiguous",
            "confidence": 0.0,
            "reasoning": f"Erreur API: {str(e)}"
        }


def ask_clarification(question: str) -> str:
    """Génère une question de clarification."""
    try:
        prompt = CLARIFICATION_PROMPT.format(question=question)

        response = client.chat(
            model=MODEL_ROUTER,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3}
        )

        return response['message']['content'].strip()

    except Exception:
        return ("Je peux répondre de deux façons :\n"
                "1. Donner des chiffres précis (classements, pourcentages)\n"
                "2. Fournir un résumé narratif des résultats\n\n"
                "Que préférez-vous ?")


def route_with_fallback(question: str) -> Dict[str, any]:
    """Route une question avec fallback sur clarification si confiance faible."""
    # Vérifier les ambiguïtés d'entités avant la classification
    ambiguity = detect_entity_ambiguity(question)
    if ambiguity:
        return {
            "route": "entity_clarification",
            "entity_type": ambiguity["entity_type"],
            "entity_value": ambiguity["entity_value"],
            "options": ambiguity["options"],
            "clarification_question": f"Dans quelle région se trouve {ambiguity['entity_value']} ?"
        }

    classification = classify_question(question)
    route = classification["route"]
    confidence = classification["confidence"]

    if route == "ambiguous" or confidence < CONFIDENCE_THRESHOLD:
        clarification = ask_clarification(question)
        return {
            "route": "clarification",
            "original_route": route,
            "confidence": confidence,
            "clarification_question": clarification,
            "reasoning": classification["reasoning"]
        }

    return {
        "route": route,
        "confidence": confidence,
        "reasoning": classification["reasoning"]
    }


if __name__ == "__main__":
    print("Test Hybrid Router")

    test_questions = [
        "Combien de bulletins nuls ont été enregistrés ?",
        "Quel candidat a obtenu le plus de voix à Abidjan ?",
        "Résume les résultats de cette élection",
        "Parle-moi de Tiapoum",
    ]

    for question in test_questions:
        print(f"Q: {question}")
        result = route_with_fallback(question)

        if result["route"] == "clarification":
            print(f"  [CLARIFICATION]")
            print(f"  Confiance: {result['confidence']:.2f}")
        else:
            print(f"  Route: {result['route'].upper()}")
            print(f"  Confiance: {result['confidence']:.2f}")
        print()
