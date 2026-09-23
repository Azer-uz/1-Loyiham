import os
import re

frontend_dir = r'c:\Users\user\Documents\Anti APP\moysklad-app\frontend'

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace hardcoded light gray backgrounds
    new_content = re.sub(
        r'background(-color)?\s*:\s*(#f8f9fa|#f1f5f9|#f4f7fb|#f3f4f6|#f9fafb)\s*(!important)?',
        r'background\1: var(--bg) \3',
        content,
        flags=re.IGNORECASE
    )
    
    # Replace hardcoded dark text colors
    new_content = re.sub(
        r'color\s*:\s*(#000|#000000|#333|#333333|#111|#111111|#222|#222222|black)\s*(!important)?',
        r'color: var(--text) \2',
        new_content,
        flags=re.IGNORECASE
    )
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated: {filepath}')

for root, _, files in os.walk(frontend_dir):
    for file in files:
        if file.endswith(('.html', '.js', '.css')):
            if 'apply_variant' in file or 'patch' in file or 'apply_comprehensive' in file:
                continue
            process_file(os.path.join(root, file))

print('Done applying CSS variables for grays and blacks.')
