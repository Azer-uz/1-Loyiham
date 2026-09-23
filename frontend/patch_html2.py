import os

files = ['payments.html', 'settings.html']
button_html = '<button class="btn-secondary theme-toggle-btn" onclick="toggleTheme()" style="padding:8px 12px;border-radius:8px;font-size:16px;cursor:pointer;background:var(--bg);border:1px solid var(--border);" title="Day/Night Mode">🌙</button>'

for file in files:
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'id="currentUserLabel"' in content and 'theme-toggle-btn' not in content:
        parts = content.split('id="currentUserLabel"')
        target = '</span>'
        subparts = parts[1].split(target, 1)
        new_content = parts[0] + 'id="currentUserLabel"' + subparts[0] + target + '\n                    ' + button_html + subparts[1]
        with open(file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated {file}')
    elif 'class="header-date"' in content and 'theme-toggle-btn' not in content:
        new_content = content.replace('<div class="header-date"', button_html + '\n                    <div class="header-date"')
        with open(file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated {file} via header-date')
