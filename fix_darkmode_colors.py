import os
import re

frontend_dir = r'c:\Users\user\Documents\Anti APP\moysklad-app\frontend'

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace inline background styles
    new_content = re.sub(
        r'background(-color)?\s*:\s*(#fff|#ffffff|white)\s*(!important)?',
        r'background\1: var(--card) \3',
        content,
        flags=re.IGNORECASE
    )
    
    # Also fix text colors if they are hardcoded black/gray in style tags or CSS blocks where we can safely replace them
    # Just focusing on backgrounds for now as requested
    
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

print('Done applying CSS variables.')
