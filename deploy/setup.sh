#!/bin/bash
# Sunucuya SSH ile bağlanıp tek seferlik çalıştırılır
# Kullanım: bash setup.sh
set -e

echo "=== BIST Scanner Sunucu Kurulumu ==="

# 1. Sistem güncellemesi
apt-get update -qq
apt-get install -y -qq git nginx python3 python3-venv python3-pip curl

# 2. Node.js 20 kurulumu
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y nodejs

# 3. Repo kopyalama
mkdir -p /opt/bist-scanner
git clone https://github.com/hacisalihoglutolga-lang/scanner.git /opt/bist-scanner
cd /opt/bist-scanner

# 4. Python venv + bağımlılıklar
cd backend
python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt
cd ..

# 5. Frontend build
cd frontend
npm ci --silent
npm run build
cd ..

# 6. Systemd servisi
cp deploy/bist-scanner.service /etc/systemd/system/
chown -R www-data:www-data /opt/bist-scanner
systemctl daemon-reload
systemctl enable bist-scanner
systemctl start bist-scanner

# 7. Nginx
cp deploy/nginx.conf /etc/nginx/sites-available/bist-scanner
ln -sf /etc/nginx/sites-available/bist-scanner /etc/nginx/sites-enabled/bist-scanner
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo ""
echo "=== Kurulum tamamlandı ==="
echo "Sunucu IP'sine tarayıcıdan eriş: http://$(curl -s ifconfig.me)"
