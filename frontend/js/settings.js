// frontend/js/settings.js - Said Baraka Sozlamalar Moduli

let paymentMethods = [];
let availableAccounts = [];
let accountsData = [];

document.addEventListener('DOMContentLoaded', async () => {
    await Promise.all([
        loadOrganizationName(),
        loadAccountsData(),
        loadPaymentMethods(),
    ]);
});

// ===== 0. TASHKILOT NOMI SOZLAMALARI =====
async function loadOrganizationName() {
    try {
        const resp = await apiFetch('/settings/organization');
        if (resp && resp.success && resp.data) {
            const input = document.getElementById('settingOrgName');
            if (input) input.value = resp.data.organization_name || 'Said_Baraka';
        }
    } catch (e) {
        console.warn('Tashkilot nomini yuklashda xatolik:', e);
    }
}

async function saveOrganizationName() {
    const input = document.getElementById('settingOrgName');
    const feedback = document.getElementById('orgSaveFeedback');
    if (!input) return;
    const orgName = input.value.trim();
    if (!orgName) {
        alert('Tashkilot nomini kiriting!');
        return;
    }

    try {
        const resp = await apiFetch('/settings/organization', {
            method: 'POST',
            body: JSON.stringify({ organization_name: orgName }),
        });

        if (resp && resp.success) {
            if (feedback) {
                feedback.style.display = 'block';
                feedback.style.color = 'var(--success)';
                feedback.textContent = '✅ Tashkilot nomi muvaffaqiyatli saqlandi!';
                setTimeout(() => { feedback.style.display = 'none'; }, 3000);
            }
            const headerOrg = document.getElementById('orgName');
            if (headerOrg) headerOrg.textContent = orgName;
        } else {
            alert('Xatolik: ' + (resp?.detail || 'Saqlab bo\'lmadi'));
        }
    } catch (e) {
        alert('Xato: ' + e.message);
    }
}

// ===== 1. HISOBLAR BALANSI VA KORREKTIROVKA =====
async function loadAccountsData() {
    const tbody = document.getElementById('accountsTableBody');
    tbody.innerHTML = '<tr><td colspan="6" class="loading">⏳ Hisoblar va qoldiqlar yuklanmoqda...</td></tr>';

    try {
        const resp = await apiFetch('/settings/accounts');
        if (resp.success && resp.data) {
            accountsData = resp.data.accounts || [];

            // 1. Jami qoldiqlarni ko'rsatish
            document.getElementById('totalUzsDisplay').textContent = formatMoney(resp.data.total_uzs_balance || 0);
            document.getElementById('totalUsdDisplay').textContent = `$${new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(resp.data.total_usd_balance || 0)} USD`;
            document.getElementById('totalConsolidatedDisplay').textContent = formatMoney(resp.data.consolidated_uzs_equivalent || 0);
            
            const rate = resp.data.reference_rate || 12800;
            document.getElementById('rateRefText').textContent = `1 USD = ${formatMoney(rate)} hisob kursi bo'yicha`;

            // 2. Jadvalni chizish
            renderAccountsTable(accountsData);
        } else {
            throw new Error(resp.detail || 'Hisoblar yuklanmadi');
        }
    } catch (e) {
        console.error('Accounts yuklash xatosi:', e);
        tbody.innerHTML = `<tr><td colspan="6" class="loading" style="color:red;">Xatolik: ${e.message}</td></tr>`;
    }
}

function renderAccountsTable(accounts) {
    const tbody = document.getElementById('accountsTableBody');
    if (!accounts || accounts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="loading">Hisoblar topilmadi</td></tr>';
        return;
    }

    tbody.innerHTML = accounts.map(a => {
        const isDol = a.is_dollar || a.currency === 'USD';
        const typeBadge = a.type === 'cash' ? '💵 Naqd Kassa' : (isDol ? '💵 Valyuta Hisob' : '🏦 Bank Hisob');
        const curBadge = isDol ? '<span class="method-tag tag-usd">USD ($)</span>' : '<span class="method-tag tag-uzs">UZS (so\'m)</span>';

        let formattedBalance = '';
        if (isDol) {
            formattedBalance = `$${new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(a.current_balance)} USD`;
        } else {
            formattedBalance = formatMoney(a.current_balance);
        }

        let statusHtml = '<span style="color:var(--text-light); font-size:12px;">Oddiy</span>';
        if (a.has_correction) {
            statusHtml = `<span style="color:#b45309; background:#fef3c7; font-size:11px; font-weight:700; padding:2px 8px; border-radius:4px;" title="Korrektirovka: ${a.correction ? a.correction.reason : ''}">✏️ Korrektirovka qilingan</span>`;
        }

        return `
            <tr>
                <td style="font-weight:700; color:var(--primary);">
                    ${a.name}
                    ${a.accountnumber ? `<div style="font-size:11px; color:var(--text-light);">${a.accountnumber}</div>` : ''}
                </td>
                <td><span style="font-size:12px; font-weight:600;">${typeBadge}</span></td>
                <td>${curBadge}</td>
                <td style="text-align:right; font-weight:800; font-size:15px; color:${isDol ? '#b45309' : 'var(--primary)'};">
                    ${formattedBalance}
                </td>
                <td>${statusHtml}</td>
                <td style="text-align:center;">
                    <button class="btn-correct" onclick="openAdjustmentModal('${a.id}', '${a.name.replace(/'/g, "\\'")}', '${a.currency}', ${a.current_balance})">
                        ✏️ Korrektirovka
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

// ===== KORREKTIROVKA MODALI =====
function openAdjustmentModal(accId, accName, currency, currentBalance) {
    document.getElementById('adjAccountId').value = accId;
    document.getElementById('adjAccountName').textContent = accName;
    document.getElementById('adjAccountCurrency').textContent = currency;
    document.getElementById('adjBalanceLabel').textContent = `Yangi haqiqiy qoldiq (${currency}) *`;
    document.getElementById('adjNewBalance').value = formatNumber(currentBalance || 0, true);
    document.getElementById('adjReason').value = '';
    document.getElementById('adjustmentModal').classList.add('active');
}

function closeAdjustmentModal() {
    document.getElementById('adjustmentModal').classList.remove('active');
}

async function handleAdjustmentSubmit(event) {
    event.preventDefault();
    const accId = document.getElementById('adjAccountId').value;
    const newBal = parseAmount(document.getElementById('adjNewBalance').value);
    const reason = document.getElementById('adjReason').value.trim();

    if (isNaN(newBal)) {
        alert("Iltimos, haqiqiy summa kiriting!");
        return;
    }

    const btn = document.getElementById('saveAdjBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Saqlanmoqda...';

    try {
        const resp = await apiFetch('/settings/accounts/adjust-balance', {
            method: 'POST',
            body: JSON.stringify({
                account_id: accId,
                new_balance: newBal,
                reason: reason || "Kassa sanash",
            })
        });

        if (resp.success) {
            alert(`✅ ${resp.message}`);
            closeAdjustmentModal();
            await loadAccountsData();
        } else {
            throw new Error(resp.detail || 'Korrektirovkani saqlashda xatolik');
        }
    } catch (e) {
        alert(`❌ Xato: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 Balansni Saqlash';
    }
}

// ===== 2. TO'LOV TURLARI BOSHQARUVI =====
async function loadPaymentMethods() {
    const listEl = document.getElementById('paymentMethodsList');
    try {
        const resp = await apiFetch('/settings/payment-methods');
        if (resp.success && resp.data) {
            paymentMethods = resp.data.methods || [];
            availableAccounts = resp.data.available_accounts || [];
            renderPaymentMethods(paymentMethods);
        }
    } catch (e) {
        console.error('To\'lov turlari yuklanmadi:', e);
        listEl.innerHTML = `<div style="color:red; padding:16px;">Xatolik: ${e.message}</div>`;
    }
}

function renderPaymentMethods(methods) {
    const listEl = document.getElementById('paymentMethodsList');
    if (!methods || methods.length === 0) {
        listEl.innerHTML = '<div style="color:var(--text-light); padding:16px;">To\'lov turlari mavjud emas</div>';
        return;
    }

    listEl.innerHTML = methods.map(m => {
        const isDol = m.currency === 'USD';
        const tagClass = isDol ? 'tag-usd' : 'tag-uzs';
        const accountsCount = m.linked_account_ids ? m.linked_account_ids.length : 0;
        const accountsText = (m.linked_accounts_detail && m.linked_accounts_detail.length > 0)
            ? m.linked_accounts_detail.map(a => a.name).join(', ')
            : 'Hisob raqam biriktirilmagan';

        return `
            <div class="method-item-row" id="methodRow_${m.id}">
                <div class="method-item-left">
                    <div class="method-icon">${m.icon || '💵'}</div>
                    <div class="method-details">
                        <h4>
                            ${m.name}
                            <span class="method-tag ${tagClass}">${m.currency}</span>
                            ${m.is_system ? '<span style="font-size:10px; background: var(--bg); color:#475569; padding:2px 6px; border-radius:4px;">Asosiy</span>' : ''}
                        </h4>
                        <p>
                            🔗 <strong>Bog'langan hisoblar:</strong> ${accountsText}
                            ${isDol && m.default_rate ? ` • <span style="color:#b45309;">Kurs: ${formatMoney(m.default_rate)}</span>` : ''}
                        </p>
                    </div>
                </div>
                <div class="method-actions">
                    <label class="switch" title="${m.is_active ? 'Faol' : 'O\'chirilgan'}">
                        <input type="checkbox" ${m.is_active ? 'checked' : ''} onchange="toggleMethod('${m.id}')">
                        <span class="slider"></span>
                    </label>
                    <button class="btn-print" style="padding:6px 10px; font-size:12px;" onclick="openEditMethodModal('${m.id}')" title="Tahrirlash">
                        ✏️
                    </button>
                    ${!m.is_system ? `
                        <button class="btn-print" style="padding:6px 10px; font-size:12px; color:var(--danger);" onclick="deleteMethod('${m.id}', '${m.name.replace(/'/g, "\\'")}')" title="O'chirish">
                            🗑️
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

async function toggleMethod(methodId) {
    try {
        const resp = await apiFetch(`/settings/payment-methods/${methodId}/toggle`, { method: 'POST' });
        if (resp.success) {
            console.log(resp.message);
        }
    } catch (e) {
        alert(`❌ Xatolik: ${e.message}`);
        await loadPaymentMethods();
    }
}

// ===== YANGI / TAHRIRLASH MODALI =====
function populateMethodAccountsCheckboxes(selectedIds = []) {
    const container = document.getElementById('methodAccountsCheckboxes');
    if (!container) return;

    if (!availableAccounts || availableAccounts.length === 0) {
        container.innerHTML = '<div style="color:var(--text-light); font-size:12px;">Mavjud hisoblar yo\'q</div>';
        return;
    }

    container.innerHTML = availableAccounts.map(acc => {
        const isChecked = selectedIds.includes(acc.id);
        return `
            <label style="display:flex; align-items:center; gap:8px; font-size:13px; cursor:pointer;">
                <input type="checkbox" name="methodAccountCheckbox" value="${acc.id}" ${isChecked ? 'checked' : ''}>
                <span>${acc.name} <small style="color:var(--text-light);">(${acc.currency})</small></span>
            </label>
        `;
    }).join('');
}

function toggleMethodCurrencyFields() {
    const cur = document.getElementById('methodCurrencySelect').value;
    const rateGroup = document.getElementById('methodRateGroup');
    if (rateGroup) {
        rateGroup.style.display = cur === 'USD' ? 'block' : 'none';
    }
}

function openNewMethodModal() {
    document.getElementById('methodModalTitle').textContent = '➕ Yangi To\'lov Turi';
    document.getElementById('editMethodId').value = '';
    document.getElementById('methodNameInput').value = '';
    document.getElementById('methodCurrencySelect').value = 'UZS';
    document.getElementById('methodRateInput').value = '12 800';
    document.getElementById('methodDescInput').value = '';
    toggleMethodCurrencyFields();
    populateMethodAccountsCheckboxes([]);
    document.getElementById('methodModal').classList.add('active');
}

function openEditMethodModal(methodId) {
    const m = paymentMethods.find(x => x.id === methodId);
    if (!m) return;

    document.getElementById('methodModalTitle').textContent = `✏️ '${m.name}' Tahrirlash`;
    document.getElementById('editMethodId').value = m.id;
    document.getElementById('methodNameInput').value = m.name;
    document.getElementById('methodCurrencySelect').value = m.currency || 'UZS';
    document.getElementById('methodRateInput').value = formatNumber(m.default_rate || '12800', true);
    document.getElementById('methodDescInput').value = m.description || '';
    toggleMethodCurrencyFields();
    populateMethodAccountsCheckboxes(m.linked_account_ids || []);
    document.getElementById('methodModal').classList.add('active');
}

function closeMethodModal() {
    document.getElementById('methodModal').classList.remove('active');
}

async function handleMethodSubmit(event) {
    event.preventDefault();
    const editId = document.getElementById('editMethodId').value;
    const name = document.getElementById('methodNameInput').value.trim();
    const currency = document.getElementById('methodCurrencySelect').value;
    const rate = parseAmount(document.getElementById('methodRateInput').value) || 12800;
    const desc = document.getElementById('methodDescInput').value.trim();

    // Checkboxlardan tanlangan hisoblar
    const checkedAccs = Array.from(document.querySelectorAll('input[name="methodAccountCheckbox"]:checked')).map(cb => cb.value);

    if (!name) {
        alert("To'lov turi nomini kiriting!");
        return;
    }

    const btn = document.getElementById('saveMethodBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Saqlanmoqda...';

    try {
        const payload = {
            name: name,
            icon: currency === 'USD' ? '💵' : (name.toLowerCase().includes('karta') || name.toLowerCase().includes('terminal') ? '💳' : '💵'),
            currency: currency,
            linked_account_ids: checkedAccs,
            default_rate: rate,
            description: desc,
        };

        let resp;
        if (editId) {
            resp = await apiFetch(`/settings/payment-methods/${editId}`, {
                method: 'PUT',
                body: JSON.stringify(payload),
            });
        } else {
            resp = await apiFetch('/settings/payment-methods', {
                method: 'POST',
                body: JSON.stringify(payload),
            });
        }

        if (resp.success) {
            alert(`✅ ${resp.message}`);
            closeMethodModal();
            await loadPaymentMethods();
        } else {
            throw new Error(resp.detail || 'Saqlashda xatolik');
        }
    } catch (e) {
        alert(`❌ Xato: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 Saqlash';
    }
}

async function deleteMethod(methodId, name) {
    if (!confirm(`Rostdan ham '${name}' to'lov turini o'chirmoqchimisiz?`)) {
        return;
    }

    try {
        const resp = await apiFetch(`/settings/payment-methods/${methodId}`, { method: 'DELETE' });
        if (resp.success) {
            alert(`✅ ${resp.message}`);
            await loadPaymentMethods();
        } else {
            throw new Error(resp.detail || 'O\'chirishda xatolik');
        }
    } catch (e) {
        alert(`❌ Xato: ${e.message}`);
    }
}
