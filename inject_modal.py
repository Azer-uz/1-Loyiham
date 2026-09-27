import sys

with open('frontend/payments.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    html_content = ''.join(lines[1057:1133])

with open('frontend/customers.html', 'r', encoding='utf-8') as f:
    cust_html = f.read()

if 'id="editPaymentModal"' not in cust_html:
    cust_html = cust_html.replace('</body>', html_content + '\n</body>')
    with open('frontend/customers.html', 'w', encoding='utf-8') as f:
        f.write(cust_html)
    print('Modal injected into customers.html')
else:
    print('Modal already exists in customers.html')
