# frontend/patch_all_navbars.py
import re
from pathlib import Path

pages = [
    ("index.html", "dashboard"),
    ("demands.html", "demands"),
    ("customers.html", "customers"),
    ("payments.html", "payments"),
    ("supply.html", "supply"),
    ("settings.html", "none"),
]

frontend_dir = Path(__file__).parent

def make_tabs(active_key):
    items = [
        ("/", "dashboard", "📊", "Dashboard"),
        ("/demands", "demands", "📦", "Sotuvlar"),
        ("/customers", "customers", "👥", "Mijozlar"),
        ("/payments", "payments", "💰", "To'lovlar"),
        ("/supply", "supply", "🏬", "Asosiy ombor"),
    ]
    lines = ['<nav class="navbar-tabs">']
    for href, key, icon, label in items:
        act = ' active' if key == active_key else ''
        lines.append(f'                    <a href="{href}" class="nav-tab-item{act}">')
        lines.append(f'                        <span>{icon}</span>')
        lines.append(f'                        <span>{label}</span>')
        lines.append('                    </a>')
    lines.append('                </nav>')
    return '\n'.join(lines)

for filename, active_key in pages:
    fpath = frontend_dir / filename
    if not fpath.exists():
        print(f"Skipping {filename} (not found)")
        continue
    
    content = fpath.read_text(encoding='utf-8')
    new_tabs = make_tabs(active_key)
    
    # Replace navbar-tabs
    pattern = r'<nav class="navbar-tabs">.*?</nav>'
    if re.search(pattern, content, flags=re.DOTALL):
        content = re.sub(pattern, new_tabs, content, count=1, flags=re.DOTALL)
        print(f"Updated tabs in {filename}")
    else:
        print(f"No navbar-tabs found in {filename}")
    
    # For supply.html: ensure api.js is included
    if filename == "supply.html" and "/static/js/api.js" not in content:
        content = content.replace('</body>', '<script src="/static/js/api.js"></script>\n</body>')
        print("Added /static/js/api.js to supply.html")

    # In dropdown menus, ensure settings link is /settings
    content = content.replace('href="/static/settings.html"', 'href="/settings"')
    
    fpath.write_text(content, encoding='utf-8')
    print(f"Saved {filename}")

print("All navbars successfully standardized!")
