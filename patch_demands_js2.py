import codecs

with codecs.open('frontend/js/demands.js', 'r', 'utf-8') as f:
    js = f.read()

target = """<select id="editCustomerSelect" class="form-control" style="font-weight:bold; margin-bottom: 5px;">"""
new_target = """<div style="display:flex; gap: 5px; align-items:center;">
                                <select id="editCustomerSelect" class="form-control" style="font-weight:bold; margin-bottom: 5px;">"""

target2 = """</select>
                            <small style="color:var(--text-light);font-size:12px;">Qarz:"""
new_target2 = """</select>
                                <button type="button" class="btn-icon" onclick="openNewCustomerModal()" style="padding: 6px 10px; background:var(--success); color:white; border-radius:6px; cursor:pointer;" title="Yangi mijoz qo'shish">➕</button>
                            </div>
                            <small style="color:var(--text-light);font-size:12px;">Qarz:"""

js = js.replace(target, new_target).replace(target2, new_target2)

with codecs.open('frontend/js/demands.js', 'w', 'utf-8') as f:
    f.write(js)
print('demands.js patched for new customer button')
