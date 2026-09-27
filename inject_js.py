import sys

with open('frontend/js/payments.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    js_content = ''.join(lines[988:1191])

with open('frontend/js/customers.js', 'r', encoding='utf-8') as f:
    cust_js = f.read()

if 'function openPaymentEditModal' not in cust_js:
    with open('frontend/js/customers.js', 'a', encoding='utf-8') as f:
        f.write('\n\n// ===== TO\'LOVNI TAHRIRLASH (IN-APP) =====\n')
        f.write(js_content)
    print('JS injected into customers.js')
else:
    print('JS already exists in customers.js')
