import os, glob, re

html_files = glob.glob('*.html')
nav_html_template = """
            <nav class="top-horizontal-nav">
                <a href="/" class="nav-link{active_dashboard}">
                    <span class="icon">📊</span>
                    <span class="label">Dashboard</span>
                </a>
                <a href="/static/demands.html" class="nav-link{active_demands}">
                    <span class="icon">📦</span>
                    <span class="label">Sotuvlar</span>
                </a>
                <a href="/static/customers.html" class="nav-link{active_customers}">
                    <span class="icon">👥</span>
                    <span class="label">Mijozlar</span>
                </a>
                <a href="/static/payments.html" class="nav-link{active_payments}">
                    <span class="icon">💰</span>
                    <span class="label">Kassa & Valyuta</span>
                </a>
                <a href="/static/settings.html" class="nav-link{active_settings}">
                    <span class="icon">⚙️</span>
                    <span class="label">Sozlamalar</span>
                </a>
            </nav>
"""

for file in html_files:
    if file == 'login.html': continue
    
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Determine active state
    actives = {
        'active_dashboard': ' active' if file == 'index.html' else '',
        'active_demands': ' active' if file == 'demands.html' else '',
        'active_customers': ' active' if file == 'customers.html' else '',
        'active_payments': ' active' if file == 'payments.html' else '',
        'active_settings': ' active' if file == 'settings.html' else ''
    }
    nav_html = nav_html_template.format(**actives)

    # Regex to remove sidebar
    sidebar_pattern = r'<!-- Desktop Sidebar -->\s*<aside class="sidebar">.*?</aside>'
    content = re.sub(sidebar_pattern, '', content, flags=re.DOTALL)
    
    # Just in case there is no comment:
    sidebar_pattern_2 = r'<aside class="sidebar">.*?</aside>'
    content = re.sub(sidebar_pattern_2, '', content, flags=re.DOTALL)

    # Insert top nav before top-header if not already there
    if 'class="top-horizontal-nav"' not in content:
        content = content.replace('<header class="top-header">', nav_html + '            <header class="top-header">')
    
    with open(file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Patched HTML: {file}")
