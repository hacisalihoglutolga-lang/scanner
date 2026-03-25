#!/bin/bash
cd "$(dirname "$0")/backend"
echo "→ Backend başlatılıyor: http://localhost:8010"
echo "→ API Docs: http://localhost:8010/docs"
./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8010 --reload
