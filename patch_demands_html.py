import re

with open('frontend/demands.html', 'r', encoding='utf-8') as f:
    html = f.read()

btn_html = '<button class="btn-new-income" onclick="showCreateDemand()" style="margin-left: 10px; background:var(--success); color:white; padding:8px 16px; border:none; border-radius:8px; cursor:pointer; font-weight:700;">➕ Yangi sotuv</button>'

if 'showCreateDemand()' not in html:
    html = html.replace('<button class="btn-primary" onclick="openFilterModal()">', btn_html + '\n                    <button class="btn-primary" onclick="openFilterModal()">')
    with open('frontend/demands.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print('demands.html patched')
else:
    print('already patched demands.html')
