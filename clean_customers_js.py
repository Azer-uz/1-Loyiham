import os

customers_js_path = os.path.join(os.path.dirname(__file__), 'frontend', 'js', 'customers.js')

with open(customers_js_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = 'window.print();\n}'
idx = content.find(target)
if idx != -1:
    base = content[:idx + len(target)]
    
    new_tail = """

// ================= TO'LOVNI TAHRIRLASH, SOTUVGA BOG'LASH VA O'CHIRISH =================
let currentEditingTx = null;

async function openPaymentEditModal(paymentId, docType) {
    if (!paymentId) return;

    let tx = null;
    if (typeof currentEditCustomer !== 'undefined' && currentEditCustomer && currentEditCustomer.payments) {
        tx = currentEditCustomer.payments.find(t => t.id === paymentId);
    }

    currentEditingTx = tx || { id: paymentId, type: docType || 'cashin' };

    const modal = document.getElementById('editPaymentModal');
    if (!modal) return;

    const payIdEl = document.getElementById('editPayId');
    const payDocTypeEl = document.getElementById('editPayDocType');
    if (payIdEl) payIdEl.value = paymentId;
    if (payDocTypeEl) payDocTypeEl.value = (tx && tx.type) || docType || 'cashin';

    const typeLabel = tx ? (tx.type_name || "To'lov") : "To'lov";
    const titleEl = document.getElementById('editPayTitle');
    const subEl = document.getElementById('editPayDocSubtitle');
    if (titleEl) titleEl.textContent = `✏️ ${typeLabel}ni Tahrirlash`;
    if (subEl) {
        subEl.textContent = tx 
            ? `Hujjat: №${tx.name || '—'} | Mijoz: ${currentEditCustomer ? currentEditCustomer.name : '—'}`
            : `ID: ${paymentId}`;
    }

    const isDollar = tx && (tx.is_usd || (tx.usd_amount && tx.usd_amount > 0));
    const currSelect = document.getElementById('editPayCurrency');
    if (currSelect) currSelect.value = isDollar ? 'USD' : 'UZS';

    const amtInput = document.getElementById('editPayAmount');
    if (amtInput) amtInput.value = tx ? formatNumber(tx.amount || 0) : '0';

    const usdGroup = document.getElementById('editPayUsdGroup');
    const usdInput = document.getElementById('editPayUsdAmount');
    const rateInput = document.getElementById('editPayUsdRate');

    if (isDollar && usdGroup) {
        usdGroup.style.display = 'block';
        if (usdInput) usdInput.value = tx ? formatNumber(tx.usd_amount || Math.round((tx.amount || 0) / (window.currentUSDRate || 12800)), true) : '0';
        if (rateInput) rateInput.value = formatNumber(tx.usd_rate || window.currentUSDRate || 12800);
    } else if (usdGroup) {
        usdGroup.style.display = 'none';
        if (usdInput) usdInput.value = '';
        if (rateInput) rateInput.value = formatNumber(window.currentUSDRate || 12800);
    }

    const momentInput = document.getElementById('editPayMoment');
    if (momentInput) {
        if (tx && tx.moment) {
            const cleanMoment = tx.moment.substring(0, 16).replace(' ', 'T');
            momentInput.value = cleanMoment;
        } else {
            const now = new Date();
            momentInput.value = now.toISOString().substring(0, 16);
        }
    }

    const purposeInput = document.getElementById('editPayPurpose');
    if (purposeInput) purposeInput.value = tx ? (tx.purpose || '') : '';

    const linkSelect = document.getElementById('editPayLinkDemand');
    if (linkSelect) {
        linkSelect.innerHTML = '<option value="">(Bog\\'lanmagan / Alohida to\\'lov)</option>';
        if (typeof currentEditCustomer !== 'undefined' && currentEditCustomer && currentEditCustomer.demands && currentEditCustomer.demands.length > 0) {
            currentEditCustomer.demands.forEach(d => {
                const opt = document.createElement('option');
                opt.value = d.id;
                const rem = d.remaining ? ` | Qarz: ${formatMoney(d.remaining)}` : '';
                opt.textContent = `№ ${d.name} (${d.moment ? d.moment.substring(0, 10) : ''}) — ${formatMoney(d.sum)}${rem}`;
                if (tx && (tx.linked_demand_id === d.id || tx.demand_id === d.id)) {
                    opt.selected = true;
                }
                linkSelect.appendChild(opt);
            });
        }
    }

    modal.classList.add('active');
}

function closeEditPaymentModal() {
    const modal = document.getElementById('editPaymentModal');
    if (modal) modal.classList.remove('active');
    currentEditingTx = null;
}

function toggleEditCurrencyInputs() {
    const curr = document.getElementById('editPayCurrency')?.value;
    const usdGroup = document.getElementById('editPayUsdGroup');
    if (curr === 'USD') {
        if (usdGroup) usdGroup.style.display = 'block';
        const amt = parseAmount(document.getElementById('editPayAmount')?.value);
        const rate = parseAmount(document.getElementById('editPayUsdRate')?.value) || (window.currentUSDRate || 12800);
        if (amt > 0 && document.getElementById('editPayUsdAmount')) {
            document.getElementById('editPayUsdAmount').value = (amt / rate).toFixed(2);
        }
    } else {
        if (usdGroup) usdGroup.style.display = 'none';
    }
}

function recalcEditUzsFromUsd() {
    const usdVal = parseAmount(document.getElementById('editPayUsdAmount')?.value);
    const rate = parseAmount(document.getElementById('editPayUsdRate')?.value) || (window.currentUSDRate || 12800);
    if (usdVal > 0 && document.getElementById('editPayAmount')) {
        document.getElementById('editPayAmount').value = formatNumber(Math.round(usdVal * rate));
    }
}

async function handleEditPaymentSubmit(event) {
    event.preventDefault();
    const paymentId = document.getElementById('editPayId')?.value;
    const docType = document.getElementById('editPayDocType')?.value || 'cashin';
    const amount = parseAmount(document.getElementById('editPayAmount')?.value);
    const curr = document.getElementById('editPayCurrency')?.value;
    const momentVal = document.getElementById('editPayMoment')?.value;
    const purpose = document.getElementById('editPayPurpose')?.value?.trim() || '';
    const linkedDemandId = document.getElementById('editPayLinkDemand')?.value;

    if (isNaN(amount) || amount <= 0) {
        alert("Iltimos, to'g'ri to'lov summasini kiriting!");
        return;
    }

    const saveBtn = document.getElementById('saveEditPaymentBtn');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = '⏳ Saqlanmoqda...';
    }

    const payload = {
        amount: amount,
        purpose: purpose,
        moment: (momentVal || new Date().toISOString().substring(0, 16)).replace('T', ' ') + ':00',
    };

    if (curr === 'USD') {
        const usdAmount = parseAmount(document.getElementById('editPayUsdAmount')?.value);
        const usdRate = parseAmount(document.getElementById('editPayUsdRate')?.value) || (window.currentUSDRate || 12800);
        payload.usd_amount = usdAmount;
        payload.usd_rate = usdRate;
    }

    if (linkedDemandId) {
        payload.linked_demand_id = linkedDemandId;
    } else {
        payload.unlink_demands = true;
    }

    try {
        const resp = await apiFetch(`/payments/${docType}/${paymentId}`, {
            method: 'PUT',
            body: JSON.stringify(payload)
        });

        if (resp && resp.success) {
            alert("✅ To'lov muvaffaqiyatli tahrirlandi!");
            closeEditPaymentModal();
            if (typeof currentEditCustomer !== 'undefined' && currentEditCustomer && currentEditCustomer.id) {
                await showCustomerDetail(currentEditCustomer.id);
            }
            await loadCustomers();
        } else {
            throw new Error(resp?.detail || 'To\\'lovni yangilashda xatolik');
        }
    } catch (e) {
        alert(`❌ Xatolik: ${e.message}`);
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = '💾 Saqlash';
        }
    }
}

async function deleteCurrentPayment() {
    const paymentId = document.getElementById('editPayId')?.value;
    const docType = document.getElementById('editPayDocType')?.value || 'cashin';
    if (!paymentId) return;

    if (!confirm("Rostdan ham ushbu to'lovni butunlay o'chirmoqchimisiz?")) {
        return;
    }

    try {
        const resp = await apiFetch(`/payments/${docType}/${paymentId}`, {
            method: 'DELETE'
        });

        if (resp && resp.success) {
            alert("✅ To'lov o'chirildi!");
            closeEditPaymentModal();
            if (typeof currentEditCustomer !== 'undefined' && currentEditCustomer && currentEditCustomer.id) {
                await showCustomerDetail(currentEditCustomer.id);
            }
            await loadCustomers();
        } else {
            throw new Error(resp?.detail || 'O\\'chirishda xatolik');
        }
    } catch (e) {
        alert(`❌ Xato: ${e.message}`);
    }
}

// ===== YANGI MIJOZ =====
function openNewCustomerModal() {
    const n = document.getElementById('newCustName');
    const p = document.getElementById('newCustPhone');
    const d = document.getElementById('newCustDesc');
    if (n) n.value = '';
    if (p) p.value = '';
    if (d) d.value = '';
    const modal = document.getElementById('newCustomerModal');
    if (modal) modal.classList.add('active');
}

function closeNewCustomerModal() {
    const modal = document.getElementById('newCustomerModal');
    if (modal) modal.classList.remove('active');
}

async function handleNewCustomerSubmit(e) {
    e.preventDefault();
    const name = document.getElementById('newCustName')?.value?.trim();
    const phone = document.getElementById('newCustPhone')?.value?.trim();
    const desc = document.getElementById('newCustDesc')?.value?.trim();

    if(!name) {
        alert("Iltimos, mijoz ismini kiriting!");
        return;
    }

    const btn = document.getElementById('saveNewCustomerBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳...';
    }

    try {
        const payload = {
            name: name,
            phone: phone || '',
            description: desc || ''
        };
        const resp = await apiFetch('/customers', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        
        if(resp && resp.success) {
            alert('✅ Yangi mijoz yaratildi!');
            closeNewCustomerModal();
            await loadCustomers();
        } else {
            throw new Error(resp?.detail || 'Xatolik');
        }
    } catch(err) {
        alert('❌ Xato: ' + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '💾 Saqlash';
        }
    }
}
"""
    with open(customers_js_path, 'w', encoding='utf-8') as f:
        f.write(base + new_tail)
    print("SUCCESS")
else:
    print("TARGET NOT FOUND")
