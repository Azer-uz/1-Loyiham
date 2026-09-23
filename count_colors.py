import os
import re
from collections import Counter

frontend_dir = r'c:\Users\user\Documents\Anti APP\moysklad-app\frontend'
colors = Counter()

for root, _, files in os.walk(frontend_dir):
    for file in files:
        if file.endswith(('.html', '.js', '.css')):
            if 'apply_variant' in file or 'patch' in file or 'apply_comprehensive' in file:
                continue
            with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                content = f.read()
                found = re.findall(r'background(-color)?\s*:\s*(#[0-9a-fA-F]{3,6})', content)
                for match in found:
                    colors[match[1].lower()] += 1

for color, count in colors.most_common():
    print(f'{color}: {count}')
