import os
import re

js_path = r'c:\Users\user\Documents\Anti APP\moysklad-app\frontend\js\customers.js'
with open(js_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the action buttons generated in JS
content = content.replace('style="flex:1;min-width:110px;background:var(--success);"', 'style="flex:1;min-width:110px;background:var(--success) !important; color:white !important; border:none;"')
content = content.replace('style="flex:1;min-width:110px;background:var(--info);"', 'style="flex:1;min-width:110px;background:var(--info) !important; color:white !important; border:none;"')
content = content.replace('style="flex:1;min-width:110px;background:var(--accent);"', 'style="flex:1;min-width:110px;background:var(--accent) !important; color:white !important; border:none;"')
content = content.replace('style="flex:1;min-width:110px;background:var(--danger);"', 'style="flex:1;min-width:110px;background:var(--danger) !important; color:white !important; border:none;"')
content = content.replace('style="background:var(--warning);color:#fff;font-weight:700;padding:8px 16px;"', 'style="background:var(--warning) !important;color:white !important;border:none;font-weight:700;padding:8px 16px;"')
content = content.replace('style="background:#eef4ff;border-color:#c3d9ff;color:#1a56db;"', 'style="background:#eef4ff !important;border-color:#c3d9ff !important;color:#1a56db !important;"')
content = content.replace('style="background:#f0fff4;border-color:#bbf7d0;color:#16a34a;"', 'style="background:#f0fff4 !important;border-color:#bbf7d0 !important;color:#16a34a !important;"')

with open(js_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Done JS')
