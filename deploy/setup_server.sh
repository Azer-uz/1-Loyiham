#!/usr/bin/env bash
# ==============================================================================
# Said Baraka Loyihasi - VPS Serverni Boshlang'ich Sozlash Skripti
# Operatsion tizim: Ubuntu 22.04 / 24.04 LTS
# ==============================================================================

set -e

echo "🚀 [1/6] Tizim yangilanmoqda va kerakli paketlar o'rnatilmoqda..."
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx ufw curl

echo "🛡️ [2/6] Xavfsizlik devori (UFW Firewall) sozlanmoqda..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo "📂 [3/6] Loyiha katalogi yaratilmoqda..."
mkdir -p /var/www/moysklad-app
cd /var/www/moysklad-app

if [ ! -d ".git" ]; then
    echo "⬇️ GitHub repozitoriyasidan kod yuklab olinmoqda..."
    git clone https://github.com/Azer-uz/1-Loyiham.git .
else
    echo "🔄 Eng so'nggi kodlar tortib olinmoqda..."
    git pull origin main
fi

echo "🐍 [4/6] Python Virtual muhit (venv) va kutubxonalar o'rnatilmoqda..."
cd /var/www/moysklad-app/backend
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# .env tekshirish
if [ ! -f ".env" ]; then
    echo "⚠️ .env fayli topilmadi. .env shabloni nusxalanmoqda..."
    cp ../deploy/env.example .env
    echo "ILTIMOS: /var/www/moysklad-app/backend/.env fayliga MoySklad login/parolini yozing!"
fi

echo "⚙️ [5/6] Systemd xizmati va Nginx sozlanmoqda..."
cp /var/www/moysklad-app/deploy/moysklad.service /etc/systemd/system/moysklad.service
systemctl daemon-reload
systemctl enable moysklad
systemctl restart moysklad

cp /var/www/moysklad-app/deploy/nginx.conf /etc/nginx/sites-available/moysklad
ln -sf /etc/nginx/sites-available/moysklad /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# Deploy skriptiga ijro ruxsatini berish
chmod +x /var/www/moysklad-app/deploy/deploy.sh
ln -sf /var/www/moysklad-app/deploy/deploy.sh /root/deploy.sh

echo "=============================================================================="
echo "✅ Server sozlash muvaffaqiyatli yakunlandi!"
echo "🌐 Brauzerda server IP manzilini ochib tekshirishingiz mumkin."
echo "🔄 Keyinchalik yangilanishlar uchun serverda shunchaki: ./deploy.sh buyrug'ini bering!"
echo "=============================================================================="
