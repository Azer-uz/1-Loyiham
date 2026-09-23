import os
import re

frontend_dir = r'c:\Users\user\Documents\Anti APP\moysklad-app\frontend'

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Fix the mistakes created by the previous regex
    # Matches: var(--card) fff, var(--card)  fff, etc.
    new_content = re.sub(r'var\(--card\)\s+[0-9a-fA-F]*', r'var(--card)', content)
    new_content = re.sub(r'var\(--bg\)\s+[0-9a-fA-F]*', r'var(--bg)', new_content)
    new_content = re.sub(r'var\(--text\)\s+[0-9a-fA-F]*', r'var(--text)', new_content)
    
    # Also fix empty  !important like ar(--card) !important which should be ar(--card) !important 
    # But wait, ar(--card)  is fine in CSS. Let's clean it up anyway
    new_content = re.sub(r'var\(--card\)\s+!important', r'var(--card) !important', new_content)
    new_content = re.sub(r'var\(--card\)\s+;', r'var(--card);', new_content)

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Fixed: {filepath}')

for root, _, files in os.walk(frontend_dir):
    for file in files:
        if file.endswith(('.html', '.js', '.css')):
            process_file(os.path.join(root, file))

print('Done fixing.')
