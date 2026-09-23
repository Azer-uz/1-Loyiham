import os
import re

html_path = r'c:\Users\user\Documents\Anti APP\moysklad-app\frontend\customers.html'
with open(html_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the Akt Sverka buttons
content = content.replace('style="background: var(--primary); padding: 8px 14px;"', 'style="background: var(--primary) !important; color: white !important; padding: 8px 14px; border: none;"')
content = content.replace('style="background: var(--info); padding: 8px 14px;"', 'style="background: var(--info) !important; color: white !important; padding: 8px 14px; border: none;"')

with open(html_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done')
