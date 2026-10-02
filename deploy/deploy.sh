#!/usr/bin/env bash
# ==============================================================================
# Said Baraka Loyihasi - Tezkor Yangilash (Deploy) Skripti
# Ishlatish: ./deploy.sh
# ==============================================================================

set -e

echo "🚀 Yangilanishlar o'rnatilmoqda..."
cd /var/www/moysklad-app

# 1. GitHub dan so'nggi o'zgarishlarni tortib olish
echo "⬇️ 1/3: GitHub'dan yangi kodlar olinmoqda..."
git stash || true
git pull origin main

# 2. Yangi Python kutubxonalari bo'lsa o'rnatish
echo "📦 2/3: Bog'liqliklar tekshirilmoqda..."
cd /var/www/moysklad-app/backend
./venv/bin/pip install -r requirements.txt --quiet

# 3. Backend xizmatini qayta ishga tushirish
echo "🔄 3/3: Backend xizmati qayta ishga tushirilmoqda..."
systemctl restart moysklad

echo "✨ Muvaffaqiyatli yangilandi! Tizim eng so'nggi versiyada ishlamoqda."
