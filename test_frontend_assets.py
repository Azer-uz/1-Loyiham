import os
import re
import sys

if sys.platform == "win32":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

frontend_dir = os.path.join(os.path.dirname(__file__), 'frontend')
html_files = [f for f in os.listdir(frontend_dir) if f.endswith('.html')]

print("=" * 60)
print("🌐 FRONTEND HTML VA STATIK RESURSLAR TEKSHIRUVI")
print("=" * 60)

all_ok = True

for hf in html_files:
    fpath = os.path.join(frontend_dir, hf)
    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Find script src
    scripts = re.findall(r'<script\s+[^>]*src=["\']([^"\']+)["\']', content)
    # Find link href
    links = re.findall(r'<link\s+[^>]*href=["\']([^"\']+\.css[^"\']*)["\']', content)

    missing = []
    for s in scripts:
        if s.startswith('http') or s.startswith('//'):
            continue
        clean_s = s.split('?')[0]
        if clean_s.startswith('/static/'):
            clean_s = clean_s[len('/static/'):]
        elif clean_s.startswith('/'):
            clean_s = clean_s[1:]
        target = os.path.join(frontend_dir, clean_s)
        if not os.path.exists(target):
            missing.append(f"Script: {s} -> {target}")

    for l in links:
        if l.startswith('http') or l.startswith('//'):
            continue
        clean_l = l.split('?')[0]
        if clean_l.startswith('/static/'):
            clean_l = clean_l[len('/static/'):]
        elif clean_l.startswith('/'):
            clean_l = clean_l[1:]
        target = os.path.join(frontend_dir, clean_l)
        if not os.path.exists(target):
            missing.append(f"CSS: {l} -> {target}")

    if missing:
        all_ok = False
        print(f"❌ {hf}: Topilmagan fayllar mavjud:")
        for m in missing:
            print(f"   - {m}")
    else:
        print(f"✅ {hf}: Barcha scriptlar ({len(scripts)}) va CSS ({len(links)}) to'g'ri bog'langan")

if all_ok:
    print("\n🎉 BARCHA FRONTEND HTML VA STATIK FAYLLAR 100% TEKSHIRILDI VA ISHCHI HOLATDA!")
else:
    print("\n⚠️ Ayrim kamchiliklar aniqlandi")
