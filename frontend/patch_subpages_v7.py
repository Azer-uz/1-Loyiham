# frontend/patch_subpages_v7.py
import re

def get_navbar(active_key):
    tabs = [
        ("Dashboard", "/", "📊", "dashboard"),
        ("Sotuvlar", "/static/demands.html", "📦", "demands"),
        ("Mijozlar", "/static/customers.html", "👥", "customers"),
        ("Kassa & Valyuta", "/static/payments.html", "💰", "payments"),
        ("Sozlamalar", "/static/settings.html", "⚙️", "settings"),
    ]
    
    tab_html = ""
    for name, url, icon, key in tabs:
        active_cls = " active" if key == active_key else ""
        tab_html += f"""                    <a href="{url}" class="nav-tab-item{active_cls}">
                        <span>{icon}</span>
                        <span>{name}</span>
                    </a>\n"""
                    
    return f"""    <!-- Top Modern Navbar (Variant 7) -->
    <header class="app-navbar">
        <div class="app-navbar-inner">
            <div class="navbar-brand-group">
                <a href="/" class="brand-link">
                    <div class="brand-icon-box">📦</div>
                    <span class="brand-title">Wholesale Hub</span>
                </a>
                <nav class="navbar-tabs">
{tab_html}                </nav>
            </div>

            <div class="navbar-right-group">
                <div class="nav-search-bar">
                    <span style="color:var(--text-muted);font-size:13px;">🔍</span>
                    <input type="text" placeholder="Qidiruv..." id="globalSearch">
                </div>
                <button class="nav-icon-circle-btn" title="Bildirishnomalar">🔔</button>
                <button class="nav-icon-circle-btn theme-toggle-btn" onclick="toggleTheme()" title="Day/Night Mode">🌙</button>
                <button class="nav-sync-pill" onclick="triggerSyncNow()" title="MoySklad bilan sinxronlash">
                    🔄 Sinxronlash
                </button>
                <div class="nav-user-pill">
                    <div class="user-avatar-circle">👤</div>
                    <span class="user-name-text" id="currentUserLabel">admin</span>
                    <button class="user-logout-btn" onclick="logout()" title="Tizimdan chiqish">🚪</button>
                </div>
            </div>
        </div>
    </header>"""

# 1. Update demands.html
demands_path = r"c:\Users\user\Documents\Anti APP\moysklad-app\frontend\demands.html"
with open(demands_path, "r", encoding="utf-8") as f:
    demands_content = f.read()

# Replace from <div class="app-layout"> ... </header>
demands_header_replacement = f"""{get_navbar('demands')}
    <div class="app-layout">
        <main class="main-content">
            <div class="v7-greeting-bar">
                <div class="v7-greeting-text-group">
                    <h1 class="v7-greeting-title">Sotuvlar Ro'yxati</h1>
                    <span class="v7-greeting-subtitle">Barcha sotuv hujjatlari va kassa cheklari</span>
                </div>
                <div style="display:flex;align-items:center;gap:10px;">
                    <button class="v7-btn-new-order" onclick="openReceiptSettingsModal()" style="background:var(--card); color:var(--text) !important; border:1px solid var(--border); box-shadow:none;">
                        ⚙️ Chek sozlamalari
                    </button>
                </div>
            </div>"""

demands_pattern = re.compile(r'<div class="app-layout">.*?<nav class="top-horizontal-nav">.*?</header>', re.DOTALL)
if demands_pattern.search(demands_content):
    demands_content = demands_pattern.sub(demands_header_replacement, demands_content, count=1)
    with open(demands_path, "w", encoding="utf-8") as f:
        f.write(demands_content)
    print("demands.html updated successfully!")
else:
    print("demands.html pattern not matched!")

# 2. Update customers.html
cust_path = r"c:\Users\user\Documents\Anti APP\moysklad-app\frontend\customers.html"
with open(cust_path, "r", encoding="utf-8") as f:
    cust_content = f.read()

cust_header_replacement = f"""{get_navbar('customers')}
    <div class="app-layout">
        <main class="main-content">
            <div class="v7-greeting-bar">
                <div class="v7-greeting-text-group">
                    <h1 class="v7-greeting-title">Mijozlar</h1>
                    <span class="v7-greeting-subtitle">Barcha mijozlar va qarzdorliklar</span>
                </div>
                <div>
                    <a href="/static/demands.html" class="v7-btn-new-order">➕ Yangi Sotuv</a>
                </div>
            </div>"""

cust_pattern = re.compile(r'<div class="app-layout">.*?<nav class="top-horizontal-nav">.*?</header>', re.DOTALL)
if cust_pattern.search(cust_content):
    cust_content = cust_pattern.sub(cust_header_replacement, cust_content, count=1)
    with open(cust_path, "w", encoding="utf-8") as f:
        f.write(cust_content)
    print("customers.html updated successfully!")
else:
    print("customers.html pattern not matched!")

# 3. Update payments.html
pay_path = r"c:\Users\user\Documents\Anti APP\moysklad-app\frontend\payments.html"
with open(pay_path, "r", encoding="utf-8") as f:
    pay_content = f.read()

pay_header_replacement = f"""{get_navbar('payments')}
    <div class="app-layout">
        <main class="main-content">
            <div class="v7-greeting-bar">
                <div class="v7-greeting-text-group">
                    <h1 class="v7-greeting-title">Kassa & Valyuta Boshqaruvi</h1>
                    <span class="v7-greeting-subtitle">Dollar kursi, hisoblar va xarajatlar tahlili</span>
                </div>
                <div class="actions-bar" style="display:flex; align-items:center; gap:8px;">
                    <button class="btn-primary-action" onclick="openExpenseModal()">
                        💸 Yangi Xarajat
                    </button>
                    <button class="btn-accent-action" onclick="openCustomerPaymentModal()">
                        📥 Kirim Kiritish
                    </button>
                    <button class="btn-print" onclick="printCashflowReport()">
                        🖨️ Chop Etish
                    </button>
                </div>
            </div>"""

pay_pattern = re.compile(r'<div class="app-layout">.*?<nav class="top-horizontal-nav">.*?</header>', re.DOTALL)
if pay_pattern.search(pay_content):
    pay_content = pay_pattern.sub(pay_header_replacement, pay_content, count=1)
    with open(pay_path, "w", encoding="utf-8") as f:
        f.write(pay_content)
    print("payments.html updated successfully!")
else:
    print("payments.html pattern not matched!")

# 4. Update settings.html
settings_path = r"c:\Users\user\Documents\Anti APP\moysklad-app\frontend\settings.html"
with open(settings_path, "r", encoding="utf-8") as f:
    settings_content = f.read()

settings_header_replacement = f"""{get_navbar('settings')}
    <div class="app-layout">
        <main class="main-content">
            <div class="v7-greeting-bar">
                <div class="v7-greeting-text-group">
                    <h1 class="v7-greeting-title">Sozlamalar</h1>
                    <span class="v7-greeting-subtitle">Tizim va to'lov turlari parametrlari</span>
                </div>
            </div>"""

settings_pattern = re.compile(r'<div class="app-layout">.*?<nav class="top-horizontal-nav">.*?</header>', re.DOTALL)
if settings_pattern.search(settings_content):
    settings_content = settings_pattern.sub(settings_header_replacement, settings_content, count=1)
    with open(settings_path, "w", encoding="utf-8") as f:
        f.write(settings_content)
    print("settings.html updated successfully!")
else:
    print("settings.html pattern not matched!")
