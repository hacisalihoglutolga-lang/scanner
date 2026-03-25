#!/bin/bash
set -e

echo "=== BIST Scanner Kurulum ==="

# Backend
echo ""
echo "→ Python bağımlılıkları kuruluyor..."
cd "$(dirname "$0")/backend"
python3 -m venv venv
./venv/bin/pip install -r requirements.txt -q

# Frontend
echo ""
echo "→ Node bağımlılıkları kuruluyor..."
cd ../frontend
npm install

echo ""
echo "→ Frontend build ediliyor..."
npm run build

echo ""
echo "✓ Kurulum tamamlandı!"
echo ""
echo "Başlatmak için:"
echo "  ./start_backend.sh"
echo ""
echo "Uygulama: http://localhost:8010"
