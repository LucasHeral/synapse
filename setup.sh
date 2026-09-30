#!/bin/bash
set -e
cd /Users/lucas.heral/Documents/veille-app
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
./venv/bin/pip install --upgrade pip
./venv/bin/pip install fastapi uvicorn requests pydantic beautifulsoup4
echo "Setup completed successfully in Documents/veille-app."
