import codecs

modal_html = """
    <!-- Yangi Mijoz Modali -->
    <div id="newCustomerModal" class="modal">
        <div class="modal-content" style="max-width: 440px;">
            <div class="modal-header">
                <h2>➕ Yangi Mijoz Qo'shish</h2>
                <button class="close-btn" onclick="closeNewCustomerModal()">&times;</button>
            </div>
            <div class="modal-body">
                <form id="newCustomerForm" onsubmit="handleNewCustomerSubmit(event)">
                    <div class="form-group">
                        <label for="newCustName">Mijoz Ismi *</label>
                        <input type="text" id="newCustName" class="form-control" placeholder="Masalan: Ali Valiyev" required>
                    </div>
                    <div class="form-group">
                        <label for="newCustPhone">Telefon raqami</label>
                        <input type="text" id="newCustPhone" class="form-control" placeholder="+998901234567">
                    </div>
                    <div class="form-group">
                        <label for="newCustDesc">Izoh / Manzil</label>
                        <input type="text" id="newCustDesc" class="form-control" placeholder="Qo'shimcha ma'lumot...">
                    </div>
                    <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px;">
                        <button type="button" class="btn-print" onclick="closeNewCustomerModal()">Bekor qilish</button>
                        <button type="submit" id="saveNewCustomerBtn" class="btn-primary-action">
                            💾 Saqlash
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>
"""

with codecs.open('frontend/demands.html', 'r', 'utf-8') as f:
    d_html = f.read()
if 'id="newCustomerModal"' not in d_html:
    with codecs.open('frontend/demands.html', 'w', 'utf-8') as f:
        f.write(d_html.replace('</body>', modal_html + '\n</body>'))

with codecs.open('frontend/customers.html', 'r', 'utf-8') as f:
    c_html = f.read()
if 'id="newCustomerModal"' not in c_html:
    btn_html = '<button class="btn-new-income" onclick="openNewCustomerModal()" style="margin-left: 10px; background:var(--success); color:white; padding:8px 16px; border:none; border-radius:8px; cursor:pointer; font-weight:700;">➕ Mijoz qo\'shish</button>'
    c_html = c_html.replace('<button class="btn-primary" onclick="openFilterModal()">', btn_html + '\n                    <button class="btn-primary" onclick="openFilterModal()">')
    with codecs.open('frontend/customers.html', 'w', 'utf-8') as f:
        f.write(c_html.replace('</body>', modal_html + '\n</body>'))

js_code = """
// ===== YANGI MIJOZ =====
function openNewCustomerModal() {
    document.getElementById('newCustName').value = '';
    document.getElementById('newCustPhone').value = '';
    document.getElementById('newCustDesc').value = '';
    document.getElementById('newCustomerModal').classList.add('active');
}

function closeNewCustomerModal() {
    document.getElementById('newCustomerModal').classList.remove('active');
}

async function handleNewCustomerSubmit(e) {
    e.preventDefault();
    const name = document.getElementById('newCustName').value.trim();
    const phone = document.getElementById('newCustPhone').value.trim();
    const desc = document.getElementById('newCustDesc').value.trim();

    if(!name) return;

    const btn = document.getElementById('saveNewCustomerBtn');
    btn.disabled = true;
    btn.textContent = '⏳...';

    try {
        const payload = {
            name: name,
            phone: phone,
            description: desc
        };
        const resp = await apiFetch('/customers', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        
        if(resp && resp.success) {
            alert('✅ Mijoz yaratildi!');
            closeNewCustomerModal();
            
            if(typeof appCustomers !== 'undefined') {
                const cResp = await apiFetch('/customers');
                if (cResp && cResp.success && cResp.data) {
                    appCustomers = cResp.data.customers || [];
                    const sel = document.getElementById('editCustomerSelect');
                    if(sel) {
                        sel.innerHTML = '<option value="">👤 Mijozni tanlang...</option>' +
                            appCustomers.map(c => `<option value="${c.id}">👤 ${c.name}</option>`).join('');
                        sel.value = resp.data.id || '';
                    }
                }
            } else if (typeof loadCustomers !== 'undefined') {
                loadCustomers();
            }
        } else {
            throw new Error(resp?.detail || 'Xatolik');
        }
    } catch(err) {
        alert('❌ Xato: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 Saqlash';
    }
}
"""

with codecs.open('frontend/js/demands.js', 'a', 'utf-8') as f:
    f.write(js_code)

with codecs.open('frontend/js/customers.js', 'a', 'utf-8') as f:
    f.write(js_code)

print('New customer logic injected')
