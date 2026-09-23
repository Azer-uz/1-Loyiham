# add_missing_dom_elements.py
import re

pages = [
    'frontend/demands.html',
    'frontend/customers.html',
    'frontend/payments.html',
    'frontend/settings.html',
    'frontend/index.html'
]

for p in pages:
    with open(p, 'r', encoding='utf-8') as f:
        content = f.read()

    # If missing currentDate or orgName, insert them inside .v7-greeting-text-group or .app-navbar
    changed = False
    if 'id="orgName"' not in content:
        # Add inside navbar or greeting
        content = content.replace(
            '<div class="v7-greeting-text-group">',
            '<div class="v7-greeting-text-group"><span id="orgName" style="display:none;"></span>'
        )
        changed = True

    if 'id="currentDate"' not in content:
        content = content.replace(
            '<div class="v7-greeting-text-group">',
            '<div class="v7-greeting-text-group"><span id="currentDate" style="display:none;"></span>'
        )
        changed = True

    if changed:
        with open(p, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {p}")
    else:
        print(f"{p} already has elements")
