#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "================================================="
echo "  🚀 Lancement de SYNAPSE - Hub de Veille"
echo "================================================="

UV="/Users/lucas.heral/.local/bin/uv"

# Sync virtualenv
$UV sync

# Open browser
(sleep 1.5 && open "http://localhost:8000") &

# Start Uvicorn backend server
cd backend
exec $UV run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
