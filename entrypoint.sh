#!/bin/bash
set -e

LOG_FILE="/app/ingestion/init.log"

# Ensure log directory exists
mkdir -p /app/ingestion
touch "$LOG_FILE"

# Function to log to both stdout and file
log() {
    echo "$@" | tee -a "$LOG_FILE"
}

# Check if this is the ingestion service (command contains ingest.py)
if [[ "$*" == *"ingest.py"* ]]; then
    log "=========================================="
    log "Entrypoint - Ingestion Mode"
    log "=========================================="
    log "Executing: $@"
    exec "$@"
fi

# Standard UI mode
log "=========================================="
log "Entrypoint - Service startup"
log "=========================================="
log "Logs also written to: $LOG_FILE"

# Run warmup to pre-build RAG index
log "🔧 Phase 1: Warmup (pre-building RAG index)..."
python app/warmup.py 2>&1 | tee -a "$LOG_FILE" || {
    log "⚠️ Warmup failed, but continuing..."
}

log ""
log "=========================================="
log "🚀 Phase 2: Starting Streamlit"
log "=========================================="

# Start Streamlit
exec streamlit run app/ui.py --server.port=8501 --server.address=0.0.0.0 "$@"
