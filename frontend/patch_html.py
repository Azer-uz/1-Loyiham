import os, glob

html_files = glob.glob('*.html')
button_html = '<button class="btn-secondary theme-toggle-btn" onclick="toggleTheme()" style="padding:8px 12px;border-radius:8px;font-size:16px;cursor:pointer;background:var(--bg);border:1px solid var(--border);" title="Day/Night Mode">🌙</button>'

for file in html_files:
    if file == 'login.html': continue
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # We want to insert it next to currentUserLabel
    if 'id="currentUserLabel"' in content and 'theme-toggle-btn' not in content:
        # Find the line or tag closing of currentUserLabel
        target = '</span>'
        parts = content.split('id="currentUserLabel"')
        if len(parts) == 2:
            subparts = parts[1].split(target, 1)
            new_content = parts[0] + 'id="currentUserLabel"' + subparts[0] + target + '\n                    ' + button_html + subparts[1]
            with open(file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f'Updated {file}')
