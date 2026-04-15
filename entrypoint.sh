#!/bin/bash
set -e

echo "=========================================="
echo "Entrypoint - Démarrage du service"
echo "=========================================="

# Exécute le warmup pour pré-construire l'index RAG
echo "🔧 Phase 1: Warmup (pré-construction de l'index RAG)..."
python app/warmup.py || {
    echo "⚠️ Warmup échoué, mais on continue..."
}

echo ""
echo "=========================================="
echo "🚀 Phase 2: Démarrage de Streamlit"
echo "=========================================="

# Lance Streamlit avec les arguments passés
exec streamlit run app/ui.py --server.port=8501 --server.address=0.0.0.0 "$@"
