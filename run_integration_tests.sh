#!/bin/bash
# Script pour exécuter les tests d'intégration avec appels LLM
# Nécessite: OLLAMA_API_KEY définie dans l'environnement

echo "Tests d'intégration avec appels LLM réels"
echo "=========================================="
echo ""
echo "ATTENTION: Ces tests font des appels API et peuvent être facturés."
echo "Appuyez sur Ctrl+C pour annuler, ou attendez 3 secondes..."
sleep 3
echo ""

# Activer l'environnement
source venv/bin/activate

# Exécuter les tests d'intégration uniquement
python -m pytest tests/integration/ -v --tb=short -m "integration and slow" "$@"

echo ""
echo "Tests d'intégration terminés."