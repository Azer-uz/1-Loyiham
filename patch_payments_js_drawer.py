import os

payments_js_path = os.path.join(os.path.dirname(__file__), 'frontend', 'js', 'payments.js')

with open(payments_js_path, 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Update loadCustomersForModal to fetch /customers?limit=2000
old_lcm = """async function loadCustomersForModal() {
    try {
        const resp = await apiFetch('/customers');
        if (resp.success && resp.data) {
            customersList = resp.data.customers || [];"""

new_lcm = """async function loadCustomersForModal() {
    try {
        const resp = await apiFetch('/customers?limit=2000');
        if (resp && resp.success && resp.data) {
            customersList = Array.isArray(resp.data) ? resp.data : (resp.data.customers || []);"""

if old_lcm in code:
    code = code.replace(old_lcm, new_lcm)
    print("Updated loadCustomersForModal")

# 2. Add Drawer Logic and handlers at the end of payments.js
drawer_js = """

// ================= BIRLASHGAN TEZKOR TO'LOV PANELI (DRAWER) =================
let currentDrawerTab = 'income'; // 'income' | 'expense'
let currentDrawerExpenseType = 'cash'; // 'cash' | 'card' | 'usd'

function openQuickPayDrawer(tab = 'income') {
    const backdrop = document.getElementById('quickPayDrawerBackdrop');
    const drawer = document.getElementById('quickPayDrawer');
    if (!drawer || !backdrop) return;

    // Accounts populated
    populateDrawerAccounts();

    // Default dates
    const now = new Date();
    const nowIso = now.toISOString().substring(0, 16);
    const incMoment = document.getElementById('drawerIncomeMoment');
    const expMoment = document.getElementById('drawerExpMoment');
    if (incMoment) incMoment.value = nowIso;
    if (expMoment) expMoment.value = nowIso;

    switchDrawerTab(tab);
    backdrop.classList.add('active');
    drawer.classList.add('active');

    // Focus first input
    setTimeout(() => {
        if (tab === 'income') {
            document.getElementById('drawerIncomeCustomerSearch')?.focus();
        } else {
            document.getElementById('drawerExpAmount')?.focus();
        }
    }, 200);
}

function closeQuickPayDrawer() {
    const backdrop = document.getElementById('quickPayDrawerBackdrop');
    const drawer = document.getElementById('quickPayDrawer');
    if (backdrop) backdrop.classList.remove('active');
    if (drawer) drawer.classList.remove('active');
    const sugg = document.getElementById('drawerCustSuggestionsList');
    if (sugg) sugg.style.display = 'none';
}

function switchDrawerTab(tab) {
    currentDrawerTab = tab;
    const btnInc = document.getElementById('tabBtnIncome');
    const btnExp = document.getElementById('tabBtnExpense');
    const secInc = document.getElementById('drawerIncomeSection');
    const secExp = document.getElementById('drawerExpenseSection');

    if (btnInc) btnInc.classList.toggle('active', tab === 'income');
    if (btnExp) btnExp.classList.toggle('active', tab === 'expense');
    if (secInc) secInc.classList.toggle('active', tab === 'income');
    if (secExp) secExp.classList.toggle('active', tab === 'expense');

    if (tab === 'expense') {
        setDrawerExpenseType(currentDrawerExpenseType || 'cash');
    }
}

function populateDrawerAccounts() {
    const cardSelect = document.getElementById('drawerPayCardAccount');
    const usdSelect = document.getElementById('drawerPayUsdAccount');
    const expAccSelect = document.getElementById('drawerExpAccountSelect');

    const uzsCards = orgAccounts.filter(a => a.type !== 'cash' && !a.is_dollar && a.currency !== 'USD');
    const usdAccounts = orgAccounts.filter(a => a.is_dollar || a.currency === 'USD');

    if (cardSelect) {
        cardSelect.innerHTML = uzsCards.map(a => `<option value="${a.id}">💳 ${a.name}</option>`).join('');
    }
    if (usdSelect) {
        usdSelect.innerHTML = usdAccounts.map(a => `<option value="${a.id}">💲 ${a.name}</option>`).join('');
    }

    // Populate expense items
    const expItemSel = document.getElementById('drawerExpItemSelect');
    if (expItemSel && expenseItems && expenseItems.length > 0) {
        expItemSel.innerHTML = '<option value="">Toifani tanlang...</option>' +
            expenseItems.map(item => `<option value="${item.id}">🏷️ ${item.name}</option>`).join('');
    }
}

// --- Customer Search in Drawer ---
function showDrawerCustList() {
    const box = document.getElementById('drawerCustSuggestionsList');
    if (!box) return;
    filterDrawerCustList(document.getElementById('drawerIncomeCustomerSearch')?.value || '');
}

function filterDrawerCustList(query) {
    const box = document.getElementById('drawerCustSuggestionsList');
    if (!box) return;
    const q = (query || '').toLowerCase().trim();
    const list = customersList || [];

    const filtered = q ? list.filter(c => 
        (c.name && c.name.toLowerCase().includes(q)) || 
        (c.phone && c.phone.toLowerCase().includes(q))
    ) : list.slice(0, 50);

    if (filtered.length === 0) {
        box.innerHTML = `
            <div style="padding:10px 12px; font-size:12px; color:#64748b; text-align:center;">
                Mijoz topilmadi.
                <button type="button" onclick="openNewCustomerModal()" style="display:block; margin:6px auto 0; padding:4px 10px; font-size:12px; background:#16a34a; color:#fff; border-radius:4px; border:none; cursor:pointer;">➕ Yangi mijoz yaratish</button>
            </div>
        `;
    } else {
        box.innerHTML = filtered.map(c => {
            const bal = Number(c.balance || 0);
            const balText = bal > 0 ? `<span style="color:#ef4444;font-size:11px;font-weight:700;">(Qarz: ${formatMoney(bal)})</span>` : (bal < 0 ? `<span style="color:#16a34a;font-size:11px;font-weight:700;">(Haq: ${formatMoney(Math.abs(bal))})</span>` : '');
            return `
                <div onclick="selectDrawerCust('${c.id}', '${(c.name || '').replace(/'/g, "\\\\'")}')" style="padding:7px 12px; cursor:pointer; font-size:12.5px; border-bottom:1px solid #f1f5f9; display:flex; justify-content:space-between; align-items:center; transition:background 0.15s;" onmouseover="this.style.background='#f0f9ff'" onmouseout="this.style.background='transparent'">
                    <div>
                        <strong style="color:var(--text-color);">👤 ${c.name}</strong>
                        ${c.phone ? `<span style="color:#64748b;font-size:11.5px;margin-left:6px;">📞 ${c.phone}</span>` : ''}
                    </div>
                    <div>${balText}</div>
                </div>
            `;
        }).join('');
    }
    box.style.display = 'block';
}

async function selectDrawerCust(id, name) {
    const input = document.getElementById('drawerIncomeCustomerSearch');
    const hidden = document.getElementById('drawerIncomeCustomerId');
    const box = document.getElementById('drawerCustSuggestionsList');
    if (input) input.value = name;
    if (hidden) hidden.value = id;
    if (box) box.style.display = 'none';

    // Fetch customer balance & unpaid demands
    let bal = 0;
    try {
        const bResp = await apiFetch(`/payments/balance/${id}`);
        if (bResp && bResp.success && bResp.data) {
            bal = bResp.data.balance || 0;
        }
    } catch (e) {}

    const banner = document.getElementById('drawerCustDebtBanner');
    const debtVal = document.getElementById('drawerCustDebtValue');
    if (banner && debtVal) {
        banner.style.display = 'flex';
        const isDebt = bal > 0;
        debtVal.textContent = isDebt ? `Qarzi: ${formatMoney(bal)}` : (bal < 0 ? `Haqi: ${formatMoney(Math.abs(bal))}` : '0 so\'m (Hisobi teng)');
        debtVal.style.color = isDebt ? '#ef4444' : (bal < 0 ? '#16a34a' : '#64748b');
    }

    // Check unpaid demands for quick-fill button
    const demandsContainer = document.getElementById('drawerCustDemandsList');
    if (demandsContainer) {
        demandsContainer.innerHTML = '';
        try {
            const dResp = await apiFetch(`/demands?limit=6&offset=0&search=${encodeURIComponent(name)}`);
            if (dResp && dResp.success && dResp.data) {
                const unpaid = dResp.data.filter(d => (d.remaining || 0) > 0.01);
                if (unpaid.length > 0) {
                    demandsContainer.innerHTML = '<span style="font-size:11px;color:#64748b;font-weight:700;width:100%;">To\'lanmagan sotuvlar (1-bosish bilan summani to\'ldirish):</span>' +
                        unpaid.map(d => `
                            <button type="button" class="drawer-chip-btn" onclick="quickFillDrawerIncomeAmount(${d.remaining})" title="Ushbu sotuv qoldig'ini kiritish">
                                📦 №${d.name}: <strong>${formatMoney(d.remaining)}</strong>
                            </button>
                        `).join('');
                }
            }
        } catch (e) {}
    }
}

function quickFillDrawerIncomeAmount(amt) {
    const cashInput = document.getElementById('drawerPayCash');
    if (cashInput) {
        cashInput.value = formatNumber(Math.round(amt));
        updateDrawerTotals();
    }
}

function updateDrawerTotals() {
    const cash = parseAmount(document.getElementById('drawerPayCash')?.value);
    const card = parseAmount(document.getElementById('drawerPayCard')?.value);
    const usd = parseAmount(document.getElementById('drawerPayUsd')?.value);

    const rate = window.currentUSDRate || 12800;
    const totalUzs = cash + card + (usd * rate);

    const totalEl = document.getElementById('drawerIncomeTotalUzs');
    const totalUsdEl = document.getElementById('drawerIncomeTotalUsd');
    if (totalEl) totalEl.textContent = formatMoney(totalUzs);
    if (totalUsdEl) totalUsdEl.textContent = `$${(totalUzs / rate).toFixed(2)} USD`;
}

// --- Expense Controls in Drawer ---
function setDrawerExpenseType(type) {
    currentDrawerExpenseType = type;
    document.getElementById('drawerExpTypeCash')?.classList.toggle('active', type === 'cash');
    document.getElementById('drawerExpTypeCard')?.classList.toggle('active', type === 'card');
    document.getElementById('drawerExpTypeUsd')?.classList.toggle('active', type === 'usd');

    const accSelect = document.getElementById('drawerExpAccountSelect');
    if (!accSelect) return;

    if (type === 'cash') {
        const cashAccs = orgAccounts.filter(a => a.type === 'cash' || (!a.is_dollar && a.currency === 'UZS' && (a.name || '').toLowerCase().includes('naqd')));
        accSelect.innerHTML = (cashAccs.length > 0 ? cashAccs : orgAccounts.filter(a => !a.is_dollar)).map(a => `<option value="${a.id}">💵 ${a.name}</option>`).join('');
    } else if (type === 'card') {
        const cardAccs = orgAccounts.filter(a => a.type !== 'cash' && !a.is_dollar && a.currency !== 'USD');
        accSelect.innerHTML = (cardAccs.length > 0 ? cardAccs : orgAccounts).map(a => `<option value="${a.id}">💳 ${a.name}</option>`).join('');
    } else if (type === 'usd') {
        const usdAccs = orgAccounts.filter(a => a.is_dollar || a.currency === 'USD');
        accSelect.innerHTML = usdAccs.map(a => `<option value="${a.id}">💲 ${a.name}</option>`).join('');
    }
    updateDrawerExpUsdPreview();
}

function selectDrawerExpenseItemQuick(categoryName) {
    const select = document.getElementById('drawerExpItemSelect');
    if (!select) return;

    let found = false;
    for (let i = 0; i < select.options.length; i++) {
        if (select.options[i].text.toLowerCase().includes(categoryName.toLowerCase())) {
            select.selectedIndex = i;
            found = true;
            break;
        }
    }
    if (!found) {
        document.getElementById('drawerExpDesc').value = categoryName;
    }
}

function updateDrawerExpUsdPreview() {
    const amt = parseAmount(document.getElementById('drawerExpAmount')?.value);
    const rate = window.currentUSDRate || 12800;
    const previewEl = document.getElementById('drawerExpUsdPreview');
    if (!previewEl) return;

    if (currentDrawerExpenseType === 'usd') {
        previewEl.textContent = `~ ${formatMoney(amt * rate)} so'm (kurs: ${formatNumber(rate)})`;
    } else {
        previewEl.textContent = `~ $${(amt / rate).toFixed(2)} USD (kurs: ${formatNumber(rate)})`;
    }
}

// --- Submit Handlers ---
async function handleDrawerIncomeSubmit(e) {
    e.preventDefault();
    const custId = document.getElementById('drawerIncomeCustomerId')?.value;
    const cash = parseAmount(document.getElementById('drawerPayCash')?.value);
    const card = parseAmount(document.getElementById('drawerPayCard')?.value);
    const usd = parseAmount(document.getElementById('drawerPayUsd')?.value);
    const cardAcc = document.getElementById('drawerPayCardAccount')?.value;
    const usdAcc = document.getElementById('drawerPayUsdAccount')?.value;
    const moment = document.getElementById('drawerIncomeMoment')?.value;
    const desc = document.getElementById('drawerIncomeDesc')?.value?.trim() || "Mijozdan to'lov";

    if (!custId) {
        alert("Iltimos, avval mijozni tanlang!");
        return;
    }
    if (cash <= 0 && card <= 0 && usd <= 0) {
        alert("Naqd, karta yoki dollar summasidan kamida bittasini kiriting!");
        return;
    }

    const btn = document.getElementById('saveDrawerIncomeBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳ Saqlanmoqda...';
    }

    try {
        const payload = {
            counterparty_id: custId,
            cash_amount: cash,
            card_amount: card,
            usd_amount: usd,
            usd_rate: window.currentUSDRate || 12800.0,
            account_id: cardAcc || null,
            usd_account_id: usdAcc || null,
            description: desc,
            moment: moment ? (moment.replace('T', ' ') + ':00') : undefined
        };

        const resp = await apiFetch('/payments/customer-payment', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        if (resp && resp.success) {
            alert("✅ Kirim to'lov muvaffaqiyatli qabul qilindi!");
            closeQuickPayDrawer();
            await loadCashflow();
        } else {
            throw new Error(resp?.detail || 'Kirimni saqlashda xatolik');
        }
    } catch (err) {
        alert(`❌ Xato: ${err.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '💾 Kirimni Saqlash (Ctrl+Enter)';
        }
    }
}

async function handleDrawerExpenseSubmit(e) {
    e.preventDefault();
    const type = currentDrawerExpenseType || 'cash';
    const accId = document.getElementById('drawerExpAccountSelect')?.value;
    const amount = parseAmount(document.getElementById('drawerExpAmount')?.value);
    const itemId = document.getElementById('drawerExpItemSelect')?.value;
    const moment = document.getElementById('drawerExpMoment')?.value;
    const desc = document.getElementById('drawerExpDesc')?.value?.trim();

    if (isNaN(amount) || amount <= 0) {
        alert("Iltimos, to'g'ri xarajat summasini kiriting!");
        return;
    }
    if (!accId) {
        alert("Iltimos, chiqim hisobini tanlang!");
        return;
    }

    const btn = document.getElementById('saveDrawerExpBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳ Saqlanmoqda...';
    }

    try {
        const payload = {
            payment_type: type,
            account_id: accId,
            amount: amount,
            expense_item_id: itemId || null,
            description: desc || "Xarajat",
            moment: moment ? (moment.replace('T', ' ') + ':00') : undefined
        };

        const resp = await apiFetch('/payments/expense', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        if (resp && resp.success) {
            alert("✅ Xarajat muvaffaqiyatli saqlandi!");
            closeQuickPayDrawer();
            await loadCashflow();
        } else {
            throw new Error(resp?.detail || 'Xarajatni saqlashda xatolik');
        }
    } catch (err) {
        alert(`❌ Xato: ${err.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '💾 Xarajatni Saqlash (Ctrl+Enter)';
        }
    }
}

// --- Smart Keyboard Navigation ---
document.addEventListener('keydown', (e) => {
    const drawer = document.getElementById('quickPayDrawer');
    if (!drawer || !drawer.classList.contains('active')) return;

    // Esc to close
    if (e.key === 'Escape') {
        closeQuickPayDrawer();
        return;
    }

    // Ctrl + Enter or Cmd + Enter to Save
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        if (currentDrawerTab === 'income') {
            document.getElementById('saveDrawerIncomeBtn')?.click();
        } else {
            document.getElementById('saveDrawerExpBtn')?.click();
        }
        return;
    }

    // Enter in input -> move to next input instead of submitting
    if (e.key === 'Enter' && e.target.tagName === 'INPUT' && !e.target.closest('#newCustomerModal')) {
        e.preventDefault();
        const form = e.target.closest('form');
        if (form) {
            const inputs = Array.from(form.querySelectorAll('input:not([type="hidden"]), select, textarea'));
            const idx = inputs.indexOf(e.target);
            if (idx !== -1 && idx < inputs.length - 1) {
                inputs[idx + 1].focus();
            }
        }
    }
});

// Click outside suggestion box in drawer to close it
document.addEventListener('click', (e) => {
    const box = document.getElementById('drawerCustSuggestionsList');
    const input = document.getElementById('drawerIncomeCustomerSearch');
    if (box && input && !input.contains(e.target) && !box.contains(e.target)) {
        box.style.display = 'none';
    }
});
"""

if '// ================= BIRLASHGAN TEZKOR TO\'LOV PANELI (DRAWER) =================' not in code:
    code += drawer_js
    print("Appended Drawer JS to payments.js")

with open(payments_js_path, 'w', encoding='utf-8') as f:
    f.write(code)

print("SUCCESS: Updated payments.js")
