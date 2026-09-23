import glob, re

for js_file in glob.glob('frontend/js/*.js'):
    with open(js_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if 'document.getElementById' in line and ('currentDate' in line or 'orgName' in line or 'currentUserLabel' in line):
            print(f"{js_file}:{i+1} -> {line.strip()}")
