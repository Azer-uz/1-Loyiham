
async function loadEditAccountsSelectCustomers(selectedAccountId) {
    const accSelect = document.getElementById('editPayAccountSelect');
    if (!accSelect) return;
    try {
        let accs = window.allBankAccountsCache;
        if (!accs) {
            const resp = await apiFetch('/settings/accounts');
            if (resp && resp.data) {
                accs = resp.data;
                window.allBankAccountsCache = accs;
            }
        }
        if (accs && accs.length > 0) {
            accSelect.innerHTML = '';
            accs.forEach(acc => {
                const opt = document.createElement('option');
                opt.value = acc.id;
                opt.textContent = `${acc.name || acc.raw_name || 'Bank hisobi'}`;
                if (selectedAccountId && (selectedAccountId === acc.id || selectedAccountId === acc.raw_name)) {
                    opt.selected = true;
                }
                accSelect.appendChild(opt);
            });
        }
    } catch (e) {
        console.warn("Hisoblar yuklanmadi:", e);
    }
}

let currentOffset = 0;
const pageSize = 50;
let totalSize = 0;
let currentDebtFilter = 'all';

// ===== SARALASH HOLATI =====
let currentSortField = 'balance';  // Default: qarz
let currentSortDir = 'desc';        // Default: katta → kichik

// MoySklad formati: Mijoz bizdan qarz bo'lsa manfiy (-) va qizil,
// Biz qarz bo'lsak (ortiqcha to'lov) musbat (+) va yashil.
function formatCustomerBalance(balance) {
    const b = Number(balance) || 0;
    if (Math.abs(b) <= 0.01) return "0 so'm";
    return formatMoney(-b);
}

document.addEventListener('DOMContentLoaded', async () => {
    const user = getCurrentUser();
    const userLabel = document.getElementById('currentUserLabel');
    if (userLabel && user) {
        userLabel.textContent = `👤 ${user.username} (${user.full_name || user.role})`;
    }

    const dateEl = document.getElementById('currentDate');
    if (dateEl) {
        dateEl.textContent =
            new Date().toLocaleDateString('uz-UZ', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    }

    // Tashkilot nomi
    try {
        const orgResp = await apiFetch('/dashboard/organization');
        if (orgResp && orgResp.success && orgResp.data) {
            const orgEl = document.getElementById('orgName');
            if (orgEl) orgEl.textContent = orgResp.data.name;
        }
    } catch (e) {}

    // Real-time qidiruv
    document.getElementById('searchInput').addEventListener('input', debounce(() => {
        currentOffset = 0;
        loadCustomers();
    }, 400));

    await loadCustomers();

    // URL query parametri (?id=...) yoki sessionStorage orqali tashqaridan o'tish (demands.html → customers.html)
    const urlParams = new URLSearchParams(window.location.search);
    const queryCustId = urlParams.get('id');
    const openCustomerId = queryCustId || sessionStorage.getItem('openCustomer');
    if (openCustomerId) {
        sessionStorage.removeItem('openCustomer');
        try {
            await showCustomerDetail(openCustomerId);
        } catch (e) {
            console.warn('Auto-open customer kartochka xatosi:', e);
        }
    }
});

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// ===== QARZ FILTRI =====
function selectDebtFilter(filter) {
    currentDebtFilter = filter;
    document.querySelectorAll('[data-debt]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.debt === filter);
    });
    currentOffset = 0;
    loadCustomers();
}

// ===== SARALASH =====
function sortBy(field) {
    if (currentSortField === field) {
        currentSortDir = currentSortDir === 'asc' ? 'desc' : 'asc';
    } else {
        currentSortField = field;
        currentSortDir = field === 'balance' ? 'desc' : 'asc';
    }
    currentOffset = 0;
    loadCustomers();
}

function updateSortIndicators() {
    document.querySelectorAll('.sortable').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        const arrow = th.querySelector('.sort-arrow');
        if (arrow) arrow.textContent = '↕';
    });

    const activeTh = document.getElementById(`th-${currentSortField}`);
    if (activeTh) {
        activeTh.classList.add(currentSortDir === 'asc' ? 'sorted-asc' : 'sorted-desc');
        const arrow = activeTh.querySelector('.sort-arrow');
        if (arrow) arrow.textContent = currentSortDir === 'asc' ? '▲' : '▼';
    }
}

let currentLoadedCustomers = [];
let currentMeta = {};

// ===== RO'YXATNI YUKLASH =====
async function loadCustomers(forceRefresh = false) {
    const search = document.getElementById('searchInput').value;

    try {
        const params = new URLSearchParams({
            limit: pageSize,
            offset: currentOffset,
            sort_by: currentSortField,
            sort_dir: currentSortDir,
            debt_filter: currentDebtFilter,
        });
        if (search) params.append('search', search);
        if (forceRefresh) params.append('refresh', 'true');

        const response = await apiFetch(`/customers?${params.toString()}`);

        if (response.success) {
            currentLoadedCustomers = response.data || [];
            currentMeta = response.meta || {};
            renderCustomers(response.data);
            totalSize = response.meta.size;
            updateStats(response.meta);
            renderPagination();
            updateSortIndicators();
        }
    } catch (error) {
        console.error('Xato:', error);
        document.getElementById('customersTable').innerHTML =
            `<tr><td colspan="7" class="loading" style="color:red;">Xato: ${error.message}</td></tr>`;
    }
}

function renderCustomers(customers) {
    const tbody = document.getElementById('customersTable');

    if (!customers || customers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading">Mijozlar topilmadi</td></tr>';
        return;
    }

    tbody.innerHTML = customers.map((c, index) => `
        <tr>
            <td>${currentOffset + index + 1}</td>
            <td class="customer-name">
                <a href="javascript:void(0)" onclick="showCustomerDetail('${c.id}')" style="color:var(--primary);text-decoration:none;font-weight:700;">${c.name}</a>
            </td>
            <td>${c.phone ? `<a href="tel:${c.phone}" class="phone-link">📞 ${c.phone}</a>` : '—'}</td>
            <td>${c.group || '—'}</td>
            <td>${c.status || '—'}</td>
            <td class="balance-cell ${c.balance > 0.01 ? 'debt' : (c.balance < -0.01 ? 'paid' : 'paid')}">
                ${formatCustomerBalance(c.balance)}
            </td>
            <td>
                <div style="display:flex;gap:4px;align-items:center;">
                    <a href="/demands?action=new&customerId=${c.id}&customerName=${encodeURIComponent(c.name || '')}" class="action-btn" title="Ushbu mijozga yangi sotuv yaratish" style="text-decoration:none;display:inline-flex;align-items:center;justify-content:center;background:#e0f2fe;color:#0284c7;border:1px solid #7dd3fc;font-size:12px;">📦+</a>
                    <button class="action-btn action-btn-view" onclick="showCustomerDetail('${c.id}')" title="Mijoz kartochkasi">👁️</button>
                    <button class="action-btn action-btn-akt" onclick="openAktSverka('${c.id}', '${(c.name || '').replace(/'/g, "\\'")}')" title="Akt Sverka">📑</button>
                    <button class="action-btn action-btn-pay" onclick="openPaymentModal('${c.id}', '${(c.name || '').replace(/'/g, "\\'")}', ${c.balance})" title="To'lov kiritish">💰</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function updateStats(meta) {
    if (!meta) return;
    document.getElementById('totalCustomers').textContent = meta.total_customers || totalSize;
    document.getElementById('totalDebt').textContent = formatMoney(meta.total_debt || 0);
    document.getElementById('debtorsCount').textContent = meta.debtors_count || 0;
}

function renderPagination() {
    const pagination = document.getElementById('pagination');
    const totalPages = Math.ceil(totalSize / pageSize);
    const currentPage = Math.floor(currentOffset / pageSize) + 1;

    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }

    let html = '';
    if (currentPage > 1) html += `<button class="page-btn" onclick="goToPage(${currentPage - 1})">← Oldingi</button>`;

    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    for (let i = startPage; i <= endPage; i++) {
        html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
    }
    if (currentPage < totalPages) html += `<button class="page-btn" onclick="goToPage(${currentPage + 1})">Keyingi →</button>`;

    pagination.innerHTML = html;
}

function goToPage(page) {
    currentOffset = (page - 1) * pageSize;
    loadCustomers();
}

async function showCustomerDetail(customerId) {
    const modal = document.getElementById('customerModal');
    const modalBody = document.getElementById('customerModalBody');
    modal.classList.add('active');
    modalBody.innerHTML = '<div style="text-align:center;padding:40px;"><div class="loading">⏳ Yuklanmoqda...</div></div>';

    try {
        const response = await apiFetch(`/customers/${customerId}`);
        
        if (!response.success) throw new Error('Mijoz topilmadi');
        const c = response.data;
        currentEditCustomer = c;  // ⬅️ Globalga saqlash
        document.getElementById('customerModalTitle').textContent = `👤 ${c.name}`;
        
        // Sotuvlar tarixi qatori
        const demandsRows = c.demands.map(d => `
            <tr>
                <td><a href="/demands?id=${d.id}" onclick="sessionStorage.setItem('openDemand','${d.id}')" class="cust-demand-link" title="Sotuvni ochish"><strong>№${d.name}</strong> ↗️</a></td>
                <td><small style="color:var(--text-light);font-weight:600;">${formatDate(d.moment)}</small></td>
                <td style="text-align:right;font-weight:700;">${formatMoney(d.sum)}</td>
                <td style="text-align:right;font-weight:700;color:var(--success);">${formatMoney(d.payed_sum)}</td>
                <td style="text-align:center;"><span class="payment-badge payment-${d.status}">${d.status_name}</span></td>
            </tr>
        `).join('');
        
        // To'lovlar tarixi qatori
        const paymentsRows = c.payments.map(p => {
            let amountHtml = `<strong>${formatMoney(p.amount)}</strong>`;
            if (p.is_usd === true) {
                amountHtml = `
                    <div style="display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap;">
                        <strong style="color:var(--success);font-size:13px;">$${Number(p.usd_amount).toFixed(2)}</strong>
                        <span style="color:var(--text-light);font-size:11.5px;">(${formatMoney(p.amount)}, kurs: ${formatNumber(p.usd_rate || 0)})</span>
                    </div>
                `;
            }
            return `
                <div class="cust-payment-row">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <span class="payment-type-badge payment-${p.type}">${p.type_name}</span>
                        ${p.name ? `<a href="javascript:void(0)" onclick="openPaymentEditModal('${p.id}', '${p.type}')" class="cust-demand-link" style="color:var(--primary);text-decoration:none;" title="Tahrirlash"><strong>№${p.name}</strong> ✏️</a>` : ''}
                        ${amountHtml}
                    </div>
                    <span style="color:var(--text-light);font-size:11.5px;font-weight:600;">${formatDate(p.moment)}</span>
                </div>
            `;
        }).join('');
        
        // State dropdown
        const stateOptions = (c.all_states || []).map(s => {
            const isSelected = (s.id === c.state_id) || (s.name === c.state);
            return `<option value="${s.id}" ${isSelected ? 'selected' : ''}>${s.name}</option>`;
        }).join('');

        // Guruhlar (Teglar) variantlari (backenddan to'g'ridan-to'g'ri olinadi)
        const availableTags = c.available_tags || ['mijozlar'];
        const tagOptions = availableTags.map(t => `<option value="${t}">`).join('');

        // Dinamik balans nomi va rangi
        let balanceLabel = "Joriy balans";
        if (c.balance > 0.01) {
            balanceLabel = "Joriy balans (Qarz)";
        } else if (c.balance < -0.01) {
            balanceLabel = "Joriy balans (Biz qarz)";
        }

        modalBody.innerHTML = `
            <!-- YUQORI BIRLASHGAN BOSHQARUV TASMASI (Mijoz + Balans + Tugmalar) -->
            <div class="customer-topbar">
                <div class="customer-topbar-left">
                    <div class="customer-name-tag">
                        <span style="font-size:18px;">👤</span>
                        <strong style="font-size:15px; color:var(--text);">${c.name}</strong>
                    </div>
                    <div class="customer-balance-pill ${c.balance > 0.01 ? 'debt' : (c.balance < -0.01 ? 'credit' : 'zero')}" title="${balanceLabel}">
                        <span class="pill-label">${c.balance > 0.01 ? 'Qarzi:' : (c.balance < -0.01 ? 'Haqi:' : 'Balans:')}</span>
                        <strong class="pill-value">${formatCustomerBalance(c.balance)}</strong>
                    </div>
                </div>
                <div class="customer-topbar-right">
                    <a href="/demands?action=new&customerId=${c.id}&customerName=${encodeURIComponent(c.name || '')}" class="btn-top-action" style="background:#0284c7;color:#ffffff;text-decoration:none;box-shadow:0 2px 5px rgba(2,132,199,0.25);" title="Ushbu mijozga yangi sotuv ochish">
                        📦 Yangi sotuv
                    </a>
                    <button type="button" class="btn-top-action btn-save-cust" onclick="saveCustomerEdit('${c.id}')" title="Mijoz ma'lumotlarini saqlash">
                        💾 Saqlash
                    </button>
                    <button type="button" class="btn-top-action btn-pay-cust" onclick="openPaymentModal('${c.id}', '${(c.name || '').replace(/'/g, "\\'")}', ${c.balance})" title="Yangi to'lov qabul qilish">
                        💰 Yangi to'lov
                    </button>
                    <button type="button" class="btn-top-action btn-akt-cust" onclick="openAktSverka('${c.id}', '${(c.name || '').replace(/'/g, "\\'")}')" title="Solishtirma dalolatnoma (Акт сверки)">
                        📑 Akt sverka
                    </button>
                    <button type="button" class="btn-top-action btn-corr-cust" onclick="openCorrectionModal('${c.id}', '${(c.name || '').replace(/'/g, "\\'")}', ${c.balance})" title="Balansni to'g'rilash (Korrektirovka)">
                        📊 Korrektirovka
                    </button>
                    <button type="button" class="btn-top-action btn-del-cust" onclick="deleteCustomer('${c.id}')" title="Mijozni o'chirish">
                        🗑️
                    </button>
                </div>
            </div>

            <!-- ASOSIY 2 USTUNLI GRID (Split CRM View) -->
            <div class="customer-detail-grid">

                <!-- CHAP USTUN (~38%): Mijoz ma'lumotlari & Moliya xulosasi -->
                <div class="customer-detail-left">
                    <!-- 1. Anketa kartochkasi -->
                    <div class="cust-card">
                        <div class="cust-card-title">
                            <span>📝</span> <span>Mijoz ma'lumotlari</span>
                        </div>
                        <div class="cust-form-grid">
                            <div class="cust-form-group">
                                <label>👤 To'liq ism:</label>
                                <input type="text" id="cust_name" value="${c.name}">
                            </div>
                            <div class="cust-form-group">
                                <label>📞 Telefon:</label>
                                <div style="display:flex; gap:6px;">
                                    <input type="text" id="cust_phone" value="${c.phone || ''}" placeholder="+998 90 123 45 67">
                                    ${c.phone ? `
                                    <a href="tel:${c.phone.replace(/[^0-9+]/g, '')}" class="cust-tel-link" title="Qo'ng'iroq qilish">📞</a>
                                    ` : ''}
                                </div>
                            </div>
                            <div class="cust-form-group">
                                <label>👥 Guruh (Teg):</label>
                                <input type="text" id="cust_group" list="groupSuggestions" value="${c.group || ''}" placeholder="Guruh nomini yozing..." autocomplete="off">
                                <datalist id="groupSuggestions">
                                    ${tagOptions}
                                </datalist>
                            </div>
                            <div class="cust-form-group">
                                <label>📌 Status:</label>
                                <select id="cust_state">
                                    <option value="">— Tanlang —</option>
                                    ${stateOptions}
                                </select>
                            </div>
                        </div>
                    </div>

                    <!-- 2. Moliyaviy KPI Ko'rsatkichlari -->
                    <div class="cust-card">
                        <div class="cust-card-title">
                            <span>📊</span> <span>Moliyaviy xulosa</span>
                        </div>
                        <div class="cust-kpi-grid">
                            <div class="cust-kpi-box">
                                <span class="kpi-label">Jami sotuv</span>
                                <strong class="kpi-val">${formatMoney(c.total_sales)}</strong>
                                <span class="kpi-sub">${c.demands_count || (c.demands ? c.demands.length : 0)} ta sotuv</span>
                            </div>
                            <div class="cust-kpi-box success">
                                <span class="kpi-label">Jami to'lov</span>
                                <strong class="kpi-val">${formatMoney(c.total_paid)}</strong>
                                <span class="kpi-sub">${c.payments ? c.payments.length : 0} ta to'lov</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- O'NG USTUN (~62%): Operatsiyalar tarixi (Tablar) -->
                <div class="customer-detail-right">
                    <div class="cust-card" style="padding:10px 14px;">
                        <div class="cust-tabs-header">
                            <div class="cust-tabs-nav">
                                <button type="button" class="cust-tab-btn active" id="tabBtnDemands" onclick="switchCustomerTab('demands')">
                                    📋 Sotuvlar tarixi <span class="tab-badge">${c.demands ? c.demands.length : 0}</span>
                                </button>
                                <button type="button" class="cust-tab-btn" id="tabBtnPayments" onclick="switchCustomerTab('payments')">
                                    💳 To'lovlar tarixi <span class="tab-badge">${c.payments ? c.payments.length : 0}</span>
                                </button>
                            </div>
                        </div>

                        <!-- Tab 1: Sotuvlar tarixi -->
                        <div class="cust-tab-content active" id="tabContentDemands">
                            <div class="cust-table-wrapper">
                                <table class="cust-modern-table">
                                    <thead>
                                        <tr>
                                            <th>Sotuv №</th>
                                            <th>Sana</th>
                                            <th style="text-align:right;">Summa</th>
                                            <th style="text-align:right;">To'langan</th>
                                            <th style="text-align:center;">Holat</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${demandsRows || '<tr><td colspan="5" style="text-align:center;padding:30px;color:var(--text-light);">Sotuvlar tarixi mavjud emas</td></tr>'}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <!-- Tab 2: To'lovlar tarixi -->
                        <div class="cust-tab-content" id="tabContentPayments">
                            <div class="cust-payments-list-wrapper">
                                ${paymentsRows || '<div style="text-align:center;padding:30px;color:var(--text-light);">To\'lovlar tarixi mavjud emas</div>'}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Kartochka xatosi:', error);
        modalBody.innerHTML = `<p style="color:red;padding:20px;text-align:center;">Xato: ${error.message}</p>`;
    }
}

window.switchCustomerTab = function(tab) {
    const tabDemands = document.getElementById('tabContentDemands');
    const tabPayments = document.getElementById('tabContentPayments');
    const btnDemands = document.getElementById('tabBtnDemands');
    const btnPayments = document.getElementById('tabBtnPayments');

    if (tab === 'demands') {
        if (tabDemands) tabDemands.classList.add('active');
        if (tabPayments) tabPayments.classList.remove('active');
        if (btnDemands) btnDemands.classList.add('active');
        if (btnPayments) btnPayments.classList.remove('active');
    } else {
        if (tabDemands) tabDemands.classList.remove('active');
        if (tabPayments) tabPayments.classList.add('active');
        if (btnDemands) btnDemands.classList.remove('active');
        if (btnPayments) btnPayments.classList.add('active');
    }
};

// ===== MIJOZNI TAHRIRLASH =====
async function editCustomer(customerId) {
    const newName = prompt("Mijozning yangi ismi:");
    if (!newName) return;
    
    const newPhone = prompt("Telefon raqami:");
    
    try {
        const updateData = { name: newName };
        if (newPhone) updateData.phone = newPhone;
        
        await apiFetch(`/customers/${customerId}`, {
            method: 'PUT',
            body: JSON.stringify(updateData),
        });
        
        alert('✅ Mijoz ma\'lumotlari yangilandi!');
        closeCustomerModal();
        await loadCustomers();
    } catch (error) {
        alert('❌ Xato: ' + error.message);
    }
}

// ===== BALANSNI TUZATISH (Корректировка взаиморасчетов) =====
async function createCorrection(customerId) {
    const newBalance = prompt("Yangi balans (so'mda):");
    if (!newBalance || isNaN(newBalance)) return;
    
    const reason = prompt("Sabab (ixtiyoriy):", "Balansni tuzatish");
    
    try {
        await apiFetch('/customers/correction', {
            method: 'POST',
            body: JSON.stringify({
                counterparty_id: customerId,
                new_balance: parseFloat(newBalance),
                reason: reason || "Balansni tuzatish",
            }),
        });
        
        alert('✅ Balans tuzatildi!');
        closeCustomerModal();
        await loadCustomers();
    } catch (error) {
        alert('❌ Xato: ' + error.message);
    }
}

// ===== MIJOZNI O'CHIRISH =====
async function deleteCustomer(customerId) {
    if (!confirm('Haqiqatan ham bu mijozni o\'chirmoqchimisiz?\n\n⚠️ Bu amalni qaytarib bo\'lmaydi!')) return;
    
    try {
        await apiFetch(`/customers/${customerId}`, { method: 'DELETE' });
        alert('✅ Mijoz o\'chirildi!');
        closeCustomerModal();
        await loadCustomers();
    } catch (error) {
        alert('❌ Xato: ' + error.message);
    }
}

// ===== MIJOZNI SAQLASH (Ism, Telefon, Guruh, Status, Balans) =====
async function saveCustomerEdit(customerId) {
    const name = document.getElementById('cust_name').value.trim();
    const phone = document.getElementById('cust_phone').value.trim();
    const groupVal = document.getElementById('cust_group')?.value?.trim();
    const stateId = document.getElementById('cust_state')?.value;
    
    if (!name) { alert('Ismni kiriting!'); return; }
    
    try {
        const updateData = { name };
        if (phone) updateData.phone = phone;
        if (groupVal !== undefined) {
            updateData.group = groupVal;
            updateData.tags = groupVal ? [groupVal] : [];
        }
        if (stateId) {
            updateData.state = {
                meta: {
                    href: `https://api.moysklad.ru/api/remap/1.2/entity/counterparty/metadata/states/${stateId}`,
                    type: "state",
                    mediaType: "application/json"
                }
            };
        }
        
        await apiFetch(`/customers/${customerId}`, {
            method: 'PUT',
            body: JSON.stringify(updateData),
        });
        
        alert('✅ Mijoz ma\'lumotlari yangilandi!');
        closeCustomerModal();
        await loadCustomers();
    } catch (error) {
        alert('❌ Xato: ' + error.message);
    }
}

// ===== BALANS KORREKTIROVKASI MODALI =====
let currentCorrectionCustomerId = null;
let currentCorrectionCurrentBalance = 0;

function setCorrectionZero() {
    const finalInput = document.getElementById('corr_final_balance');
    const adjInput = document.getElementById('corr_adjustment_sum');
    if (finalInput && adjInput) {
        finalInput.value = '0.00';
        const diff = -currentCorrectionCurrentBalance;
        adjInput.value = (Math.abs(diff % 1) > 0.001) ? diff.toFixed(2) : String(Math.round(diff));
    }
}
window.setCorrectionZero = setCorrectionZero;

function openCorrectionModal(customerId, customerName, currentBalance) {
    currentCorrectionCustomerId = customerId;
    currentCorrectionCurrentBalance = Number(currentBalance) || 0;

    const modal = document.getElementById('correctionModal');
    modal.classList.add('active');
    if (typeof window.bringModalToFront === 'function') {
        window.bringModalToFront(modal);
    }

    const orgEl = document.getElementById('orgName');
    const orgInput = document.getElementById('corr_org_name');
    if (orgInput) {
        orgInput.value = (orgEl && orgEl.textContent.trim()) ? orgEl.textContent.trim() : 'Said_Baraka';
    }

    const custInput = document.getElementById('corr_customer_name');
    if (custInput) {
        custInput.value = customerName;
    }

    const currBalEl = document.getElementById('corr_current_balance_text');
    if (currBalEl) {
        currBalEl.textContent = formatMoney(currentCorrectionCurrentBalance);
    }

    const adjInput = document.getElementById('corr_adjustment_sum');
    const finalInput = document.getElementById('corr_final_balance');

    if (adjInput) adjInput.value = '';
    if (finalInput) {
        finalInput.value = (Math.abs(currentCorrectionCurrentBalance % 1) > 0.001)
            ? currentCorrectionCurrentBalance.toFixed(2)
            : String(Math.round(currentCorrectionCurrentBalance));
    }

    // 2 tomonlama jonli (live) hisoblash (tiyinlar bilan):
    // Итоговый остаток = Текущий остаток + Сумма корректировки
    if (adjInput && finalInput) {
        adjInput.oninput = () => {
            const raw = adjInput.value.trim();
            if (raw === '' || raw === '-') {
                finalInput.value = (Math.abs(currentCorrectionCurrentBalance % 1) > 0.001)
                    ? currentCorrectionCurrentBalance.toFixed(2)
                    : String(Math.round(currentCorrectionCurrentBalance));
            } else {
                const adjVal = parseAmount(raw);
                const calcFinal = currentCorrectionCurrentBalance + adjVal;
                finalInput.value = (Math.abs(calcFinal % 1) > 0.001) ? calcFinal.toFixed(2) : String(Math.round(calcFinal));
            }
        };

        finalInput.oninput = () => {
            const raw = finalInput.value.trim();
            if (raw === '' || raw === '-') {
                adjInput.value = '';
            } else {
                const finalVal = parseAmount(raw);
                const calcAdj = finalVal - currentCorrectionCurrentBalance;
                adjInput.value = (Math.abs(calcAdj % 1) > 0.001) ? calcAdj.toFixed(2) : String(Math.round(calcAdj));
            }
        };
    }

    const now = new Date();
    const localIso = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 19);
    const momentInput = document.getElementById('corr_moment');
    if (momentInput) momentInput.value = localIso;

    const reasonInput = document.getElementById('corr_reason');
    if (reasonInput) reasonInput.value = 'KORREKTIROVKA: Balansni tuzatish';

    if (window.initGhostZeros) window.initGhostZeros(document.getElementById('correctionModal'));
}

function closeCorrectionModal() {
    document.getElementById('correctionModal').classList.remove('active');
    currentCorrectionCustomerId = null;
    currentCorrectionCurrentBalance = 0;
}

async function submitCorrection() {
    if (!currentCorrectionCustomerId) return;
    const adjInput = document.getElementById('corr_adjustment_sum');
    const finalInput = document.getElementById('corr_final_balance');
    const moment = document.getElementById('corr_moment')?.value;
    const reason = document.getElementById('corr_reason')?.value.trim() || 'Balansni tuzatish';

    let adjVal = adjInput?.value.trim() !== '' ? parseAmount(adjInput?.value) : NaN;
    let finalVal = finalInput?.value.trim() !== '' ? parseAmount(finalInput?.value) : NaN;

    if (isNaN(adjVal) && isNaN(finalVal)) {
        alert('Korrektirovka summasi yoki umumiy qoldiqni kiriting!');
        return;
    }

    if (isNaN(adjVal) && !isNaN(finalVal)) {
        adjVal = finalVal - currentCorrectionCurrentBalance;
    }
    if (!isNaN(adjVal) && isNaN(finalVal)) {
        finalVal = currentCorrectionCurrentBalance + adjVal;
    }

    const btn = document.getElementById('saveCorrectionBtn');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Saqlanmoqda...'; }

    try {
        await apiFetch('/customers/correction', {
            method: 'POST',
            body: JSON.stringify({
                counterparty_id: currentCorrectionCustomerId,
                adjustment_amount: adjVal,
                new_balance: finalVal,
                reason,
                moment: moment || null,
            }),
        });
        alert(`✅ Balans muvaffaqiyatli tuzatildi! Yakuniy qoldiq: ${formatMoney(finalVal)}`);
        closeCorrectionModal();
        closeCustomerModal();
        await loadCustomers();
    } catch (error) {
        alert('❌ Xato: ' + error.message);
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '💾 Сохранить (Saqlash)'; }
    }
}

document.getElementById('correctionModal').addEventListener('click', (e) => {
    if (e.target.id === 'correctionModal') closeCorrectionModal();
});

// ===== TO'LOV VA FIFO (SOTUVLARGA BOG'LASH) TIZIMI =====
let unpaidDemandsData = [];
let demandAllocations = {};
let manualPinnedDemands = {};
let isFifoAuto = true;

function getPaymentTotalUzs() {
    const cash = parseAmount(document.getElementById('pay_cash')?.value);
    const card = parseAmount(document.getElementById('pay_card')?.value);
    const usd = parseAmount(document.getElementById('pay_usd')?.value);
    const rate = parseAmount(document.getElementById('pay_usd_rate')?.value) || 11800;
    return cash + card + Math.round(usd * rate);
}

function handleLinkDemandsToggle() {
    const toggle = document.getElementById('pay_link_demands_toggle');
    const container = document.getElementById('unpaidDemandsContainer');
    const summaryBar = document.getElementById('fifoSummaryBar');
    const isChecked = toggle ? toggle.checked : true;
    if (container) container.style.display = isChecked ? 'block' : 'none';
    if (summaryBar) summaryBar.style.display = isChecked && unpaidDemandsData.length > 0 ? 'flex' : 'none';
}

function resetToAutoFifo() {
    isFifoAuto = true;
    manualPinnedDemands = {};
    const modeBadge = document.getElementById('fifoModeBadge');
    if (modeBadge) {
        modeBadge.textContent = '⚡ Avto-taqsimlash';
        modeBadge.className = 'fifo-mode-badge auto';
        modeBadge.style.background = '';
        modeBadge.style.color = '';
    }
    recalculateFifo(true);
}

function fillTotalDebtAmount() {
    const totalRemaining = (unpaidDemandsData || []).reduce((acc, d) => acc + (d.remaining || 0), 0);
    const targetAmt = totalRemaining > 0 ? totalRemaining : Math.max(0, window.currentPaymentCustomerDebt || 0);
    
    document.getElementById('pay_cash').value = formatNumber(Math.round(targetAmt));
    document.getElementById('pay_card').value = '';
    document.getElementById('pay_usd').value = '';
    
    isFifoAuto = true;
    manualPinnedDemands = {};
    const modeBadge = document.getElementById('fifoModeBadge');
    if (modeBadge) {
        modeBadge.textContent = '⚡ Avto-taqsimlash';
        modeBadge.className = 'fifo-mode-badge auto';
        modeBadge.style.background = '';
        modeBadge.style.color = '';
    }
    
    if (typeof window.updatePaymentAmounts === 'function') {
        window.updatePaymentAmounts();
    } else {
        recalculateFifo(true);
    }
}

function setSoloDemandPayment(demandId, demandRemaining) {
    document.getElementById('pay_cash').value = formatNumber(Math.round(demandRemaining));
    document.getElementById('pay_card').value = '';
    document.getElementById('pay_usd').value = '';
    
    // Avtomatik taqsimlashni faqat shu tanlangan sotuvga yo'naltirish
    isFifoAuto = false;
    manualPinnedDemands = { [demandId]: Math.round(demandRemaining) };
    
    const modeBadge = document.getElementById('fifoModeBadge');
    if (modeBadge) {
        modeBadge.textContent = '🎯 Tanlangan sotuv';
        modeBadge.className = 'fifo-mode-badge solo';
        modeBadge.style.background = '';
        modeBadge.style.color = '';
    }
    
    if (typeof window.updatePaymentAmounts === 'function') {
        window.updatePaymentAmounts();
    }
    recalculateFifo(false, null);
}

function onManualDemandAllocChange(demandId, newVal) {
    isFifoAuto = false;
    const modeBadge = document.getElementById('fifoModeBadge');
    if (modeBadge) {
        modeBadge.textContent = '✋ Qo\'lda sozlangan';
        modeBadge.className = 'fifo-mode-badge manual';
        modeBadge.style.background = '';
        modeBadge.style.color = '';
    }
    
    const val = Math.max(0, parseAmount(newVal));
    manualPinnedDemands[demandId] = val;
    // activeInputDemandId uzatiladi, shu sababli ayni shu inputning DOM'i buzilmaydi va kursor yo'qolmaydi!
    recalculateFifo(false, demandId);
}

function toggleDemandCheckbox(demandId, isChecked) {
    isFifoAuto = false;
    const modeBadge = document.getElementById('fifoModeBadge');
    if (modeBadge) {
        modeBadge.textContent = '✋ Qo\'lda sozlangan';
        modeBadge.className = 'fifo-mode-badge manual';
        modeBadge.style.background = '';
        modeBadge.style.color = '';
    }

    const d = unpaidDemandsData.find(item => item.id === demandId);
    if (!isChecked) {
        manualPinnedDemands[demandId] = 0;
    } else {
        // Tanlangan sotuvga qancha to'lov qolganini ajratamiz
        const totalPayment = getPaymentTotalUzs();
        const otherPinnedSum = Object.entries(manualPinnedDemands)
            .filter(([id]) => id !== demandId)
            .reduce((sum, [, a]) => sum + a, 0);
        const available = Math.max(0, totalPayment - otherPinnedSum);
        const needed = d ? d.remaining : 0;
        manualPinnedDemands[demandId] = Math.min(needed, available > 0 ? available : needed);
    }
    recalculateFifo(false, null);
}

function recalculateFifo(forceRender = false, activeInputDemandId = null) {
    const totalPayment = getPaymentTotalUzs();
    
    if (isFifoAuto) {
        let budget = totalPayment;
        demandAllocations = {};
        for (const d of unpaidDemandsData) {
            if (budget <= 0.01) {
                demandAllocations[d.id] = 0;
            } else {
                const take = Math.min(budget, d.remaining || 0);
                demandAllocations[d.id] = take;
                budget -= take;
            }
        }
    } else {
        // Qo'lda sozlangan rejim:
        // 1. Foydalanuvchi qaysi sotuvga summa kiritgan/belgilagan bo'lsa, o'shani ajratamiz
        demandAllocations = {};
        let pinnedTotal = 0;
        for (const [did, amt] of Object.entries(manualPinnedDemands)) {
            const d = unpaidDemandsData.find(item => item.id === did);
            const maxAllowed = d ? d.remaining : amt;
            const validAmt = Math.min(amt, maxAllowed);
            demandAllocations[did] = validAmt;
            pinnedTotal += validAmt;
        }

        // 2. Jami to'lovdan ortgan qolgan summa:
        let remainingBudget = Math.max(0, totalPayment - pinnedTotal);

        // 3. Qolgan summani belgilangan/pinlanmagan boshqa eski sotuvlarga (FIFO bo'yicha) taqsimlaymiz!
        for (const d of unpaidDemandsData) {
            if (manualPinnedDemands.hasOwnProperty(d.id)) {
                continue; // foydalanuvchi o'zi belgilagan sotuv
            }
            if (remainingBudget <= 0.01) {
                demandAllocations[d.id] = 0;
            } else {
                const take = Math.min(remainingBudget, d.remaining || 0);
                demandAllocations[d.id] = take;
                remainingBudget -= take;
            }
        }
    }

    if (forceRender) {
        renderFifoDemandsList();
    } else {
        updateFifoDom(activeInputDemandId);
    }
}

function renderFifoDemandsList() {
    const list = document.getElementById('unpaidDemandsList');
    if (!list) return;
    
    if (!unpaidDemandsData || unpaidDemandsData.length === 0) {
        list.innerHTML = `
            <div class="no-demands-alert">
                <span style="font-size:20px;">✅</span>
                <span>Ushbu mijozda qarzdor sotuvlar yo'q. Kiritilgan to'lov mijoz hisobiga (ortiqcha to'lov / avans) sifatida o'tadi.</span>
            </div>
        `;
        const summaryBar = document.getElementById('fifoSummaryBar');
        if (summaryBar) summaryBar.style.display = 'none';
        return;
    }

    let html = '';
    unpaidDemandsData.forEach((d) => {
        const alloc = demandAllocations[d.id] || 0;
        const isFullyPaid = alloc >= (d.remaining - 0.01);
        const isPartial = alloc > 0.01 && !isFullyPaid;
        
        let statusBadge = '';
        let cardClass = 'demand-card unpaid';
        
        if (isFullyPaid) {
            statusBadge = `<span class="demand-badge fully-paid">To'liq yopiladi ✅</span>`;
            cardClass = 'demand-card fully-paid';
        } else if (isPartial) {
            const left = Math.max(0, d.remaining - alloc);
            statusBadge = `<span class="demand-badge partial-paid">Qisman: ${formatMoney(alloc)} (qoladi: ${formatMoney(left)}) ⏳</span>`;
            cardClass = 'demand-card partial-paid';
        } else {
            statusBadge = `<span class="demand-badge unpaid">Bog'lanmaydi ⭕</span>`;
            cardClass = 'demand-card unpaid';
        }

        html += `
            <div id="demand_card_${d.id}" class="${cardClass}">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <input type="checkbox" id="demand_chk_${d.id}" style="width:16px;height:16px;cursor:pointer;" ${alloc > 0.01 ? 'checked' : ''} onchange="toggleDemandCheckbox('${d.id}', this.checked)">
                        <div>
                            <strong class="demand-num" style="color:var(--primary);font-size:13px;">№ ${d.name}</strong>
                            <small class="demand-date" style="color:var(--text-light);margin-left:4px;">(${formatDate(d.moment)})</small>
                        </div>
                    </div>
                    <div style="display:flex;align-items:center;gap:6px;">
                        <div id="demand_badge_${d.id}">${statusBadge}</div>
                        <button type="button" class="btn-solo-demand" onclick="setSoloDemandPayment('${d.id}', ${d.remaining})" title="Faqat shu sotuvni to'lash">
                            Faqat shuni yopish
                        </button>
                    </div>
                </div>

                <div class="demand-meta-row" style="display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--text-light);padding-top:4px;border-top:1px dashed #e2e8f0;flex-wrap:wrap;gap:4px;">
                    <div>
                        Jami: <strong>${formatMoney(d.sum)}</strong> | Qoldiq: <strong style="color:var(--danger);">${formatMoney(d.remaining)}</strong>
                    </div>
                    <div style="display:flex;align-items:center;gap:6px;">
                        <span style="font-size:11px;font-weight:600;">Bog'lanadi:</span>
                        <input type="text" inputmode="numeric" id="demand_alloc_${d.id}" class="demand-alloc-input format-number" placeholder="0" value="${alloc > 0 ? formatNumber(Math.round(alloc)) : '0'}" oninput="onManualDemandAllocChange('${d.id}', this.value)" style="width:115px;padding:4px 6px;font-size:12px;font-weight:700;text-align:right;border-radius:4px;">
                        <span style="font-size:11px;">so'm</span>
                    </div>
                </div>
            </div>
        `;
    });

    list.innerHTML = html;
    if (window.initGhostZeros) window.initGhostZeros(list);

    updateFifoSummaryBar();
}

function updateFifoDom(activeInputDemandId = null) {
    const list = document.getElementById('unpaidDemandsList');
    if (!list || !list.children.length || list.querySelector('.loading')) {
        renderFifoDemandsList();
        return;
    }

    for (const d of unpaidDemandsData) {
        const alloc = demandAllocations[d.id] || 0;
        const isFullyPaid = alloc >= (d.remaining - 0.01);
        const isPartial = alloc > 0.01 && !isFullyPaid;

        // 1. Faqat aktiv yozilayotgan bo'lmagan inputlarni yangilaymiz (kursor yo'qolmasligi uchun!)
        if (d.id !== activeInputDemandId) {
            const inputEl = document.getElementById(`demand_alloc_${d.id}`);
            if (inputEl) {
                const formatted = alloc > 0 ? formatNumber(Math.round(alloc)) : '0';
                if (inputEl.value !== formatted) {
                    inputEl.value = formatted;
                }
            }
        }

        // 2. Checkbox holatini yangilash
        const chkEl = document.getElementById(`demand_chk_${d.id}`);
        if (chkEl) {
            chkEl.checked = alloc > 0.01;
        }

        // 3. Status badge va kartochka class'ini yangilash (inline style ishlatilmaydi!)
        const badgeEl = document.getElementById(`demand_badge_${d.id}`);
        const cardEl = document.getElementById(`demand_card_${d.id}`);
        if (badgeEl && cardEl) {
            cardEl.style.borderColor = '';
            cardEl.style.background = '';
            if (isFullyPaid) {
                badgeEl.innerHTML = `<span class="demand-badge fully-paid">To'liq yopiladi ✅</span>`;
                cardEl.className = 'demand-card fully-paid';
            } else if (isPartial) {
                const left = Math.max(0, d.remaining - alloc);
                badgeEl.innerHTML = `<span class="demand-badge partial-paid">Qisman: ${formatMoney(alloc)} (qoladi: ${formatMoney(left)}) ⏳</span>`;
                cardEl.className = 'demand-card partial-paid';
            } else {
                badgeEl.innerHTML = `<span class="demand-badge unpaid">Bog'lanmaydi ⭕</span>`;
                cardEl.className = 'demand-card unpaid';
            }
        }
    }

    updateFifoSummaryBar();
}

function updateFifoSummaryBar() {
    const summaryBar = document.getElementById('fifoSummaryBar');
    if (!summaryBar) return;

    let totalAllocated = 0;
    let totalDemandsDebt = 0;
    const totalPayment = getPaymentTotalUzs();

    for (const d of unpaidDemandsData) {
        const alloc = demandAllocations[d.id] || 0;
        totalAllocated += alloc;
        totalDemandsDebt += (d.remaining || 0);
    }

    summaryBar.style.display = 'flex';
    const totalAllocatedEl = document.getElementById('fifoTotalAllocatedText');
    if (totalAllocatedEl) totalAllocatedEl.textContent = formatMoney(totalAllocated);

    const remainingDebt = Math.max(0, totalDemandsDebt - totalAllocated);
    const remEl = document.getElementById('fifoRemainingDebtText');
    if (remEl) remEl.textContent = formatMoney(remainingDebt);

    const excessEl = document.getElementById('fifoExcessText');
    if (excessEl) {
        if (totalPayment > totalAllocated) {
            excessEl.style.display = 'block';
            excessEl.innerHTML = `Ortiqcha (avans): <strong>${formatMoney(totalPayment - totalAllocated)}</strong>`;
        } else {
            excessEl.style.display = 'none';
        }
    }
}

async function loadCustomerUnpaidDemandsForFifo(customerId) {
    const loading = document.getElementById('unpaidDemandsLoading');
    const list = document.getElementById('unpaidDemandsList');
    const toggle = document.getElementById('pay_link_demands_toggle');
    if (toggle) toggle.checked = true;
    
    if (loading) loading.style.display = 'block';
    if (list) list.innerHTML = '<div style="color:var(--text-light);padding:10px;text-align:center;">⏳ Ochiq sotuvlar qidirilmoqda...</div>';
    
    isFifoAuto = true;
    demandAllocations = {};
    manualPinnedDemands = {};
    unpaidDemandsData = [];

    const modeBadge = document.getElementById('fifoModeBadge');
    if (modeBadge) {
        modeBadge.textContent = '⚡ Avto-taqsimlash';
        modeBadge.className = 'fifo-mode-badge auto';
        modeBadge.style.background = '';
        modeBadge.style.color = '';
    }

    try {
        const resp = await apiFetch(`/customers/${customerId}/unpaid-demands`);
        if (loading) loading.style.display = 'none';
        
        if (resp && resp.success && Array.isArray(resp.data)) {
            unpaidDemandsData = resp.data;
        } else {
            unpaidDemandsData = [];
        }
    } catch (e) {
        if (loading) loading.style.display = 'none';
        console.warn('Unpaid demands yuklashda xato:', e);
        unpaidDemandsData = [];
    }
    
    recalculateFifo(true);
}

async function loadAccountsForPaymentModal() {
    const accountSelect = document.getElementById('pay_account');
    const usdAccountSelect = document.getElementById('pay_usd_account');
    if (!accountSelect) return;

    accountSelect.innerHTML = '<option value="">— Tanlang —</option>';
    if (usdAccountSelect) usdAccountSelect.innerHTML = '<option value="">— Tanlang (ixtiyoriy) —</option>';

    try {
        const orgResp = await apiFetch('/dashboard/organization');
        if (orgResp.success && orgResp.data && orgResp.data.id) {
            const accountsResp = await apiFetch(`/payments/accounts/${orgResp.data.id}`);
            if (accountsResp.success) {
                (accountsResp.data || []).forEach(a => {
                    const opt = document.createElement('option');
                    opt.value = a.id;
                    opt.textContent = a.name;
                    if (a.isDefault) opt.selected = true;
                    accountSelect.appendChild(opt);

                    if (usdAccountSelect) {
                        const optUsd = document.createElement('option');
                        optUsd.value = a.id;
                        optUsd.textContent = `💲 ${a.name}`;
                        usdAccountSelect.appendChild(optUsd);
                    }
                });
            }
        }
    } catch (e) {
        console.warn('Hisob raqamlar yuklanmadi:', e);
    }
}

async function openPaymentModal(customerId, customerName, currentBalance) {
    document.getElementById('paymentModal').classList.add('active');
    const custNameEl = document.getElementById('paymentCustomerName');
    if (custNameEl) custNameEl.textContent = customerName;
    const badgeEl = document.getElementById('paymentCustomerNameBadge');
    if (badgeEl) badgeEl.textContent = customerName;

    window.currentPaymentCustomerId = customerId;
    window.currentPaymentCustomerName = customerName;
    window.currentPaymentCustomerDebt = currentBalance > 0.01 ? currentBalance : 0;
    
    manualPinnedDemands = {};
    demandAllocations = {};
    isFifoAuto = true;

    const balEl = document.getElementById('paymentCurrentBalance');
    if (balEl) {
        balEl.textContent = formatCustomerBalance(currentBalance);
        balEl.className = currentBalance > 0.01 ? 'debt' : (currentBalance < -0.01 ? 'paid' : '');
        balEl.style.color = currentBalance > 0.01 ? 'var(--danger)' : (currentBalance < -0.01 ? 'var(--success)' : 'inherit');
    }
    
    // Inputlarni tozalash (ghost zero)
    document.getElementById('pay_cash').value = '';
    document.getElementById('pay_card').value = '';
    document.getElementById('pay_usd').value = '';
    document.getElementById('pay_usd_rate').value = formatNumber(window.currentUSDRate || window.appReferenceRate || 12800);
    document.getElementById('pay_description').value = '';
    document.getElementById('pay_usd_equiv').textContent = '~ 0 so\'m';
    if (document.getElementById('pay_total_display')) {
        document.getElementById('pay_total_display').textContent = '0 so\'m';
    }
    
    const cardAccGroup = document.getElementById('pay_card_account_group');
    if (cardAccGroup) cardAccGroup.style.display = 'none';
    const usdAccGroup = document.getElementById('pay_usd_account_group');
    if (usdAccGroup) usdAccGroup.style.display = 'none';

    // USD kurs hisoblash va FIFO avto-taqsimlash listener
    window.updatePaymentAmounts = () => {
        const usd = parseAmount(document.getElementById('pay_usd')?.value);
        const rate = parseAmount(document.getElementById('pay_usd_rate')?.value) || (window.currentUSDRate || 12800);
        const equiv = Math.round(usd * rate);
        document.getElementById('pay_usd_equiv').textContent = `~ ${formatMoney(equiv)}`;
        
        const cash = parseAmount(document.getElementById('pay_cash')?.value);
        const card = parseAmount(document.getElementById('pay_card')?.value);
        const totalDisplay = document.getElementById('pay_total_display');
        if (totalDisplay) totalDisplay.textContent = formatMoney(cash + card + equiv);

        if (cardAccGroup) cardAccGroup.style.display = card > 0 ? 'block' : 'none';
        if (usdAccGroup) usdAccGroup.style.display = usd > 0 ? 'block' : 'none';

        recalculateFifo(false);
    };

    document.getElementById('pay_usd').oninput = window.updatePaymentAmounts;
    document.getElementById('pay_usd_rate').oninput = window.updatePaymentAmounts;
    document.getElementById('pay_cash').oninput = window.updatePaymentAmounts;
    document.getElementById('pay_card').oninput = window.updatePaymentAmounts;

    if (window.initGhostZeros) window.initGhostZeros(document.getElementById('paymentModal'));
    
    // Hisob raqamlarni yuklash
    loadAccountsForPaymentModal();
    
    // FIFO ochiq sotuvlarni yuklash va variant ko'rsatish
    await loadCustomerUnpaidDemandsForFifo(customerId);
}

function closePaymentModal() {
    document.getElementById('paymentModal').classList.remove('active');
    unpaidDemandsData = [];
    demandAllocations = {};
    manualPinnedDemands = {};
    isFifoAuto = true;
}

async function submitCustomerPayment() {
    const cashAmount = parseAmount(document.getElementById('pay_cash').value);
    const cardAmount = parseAmount(document.getElementById('pay_card').value);
    const usdAmount = parseAmount(document.getElementById('pay_usd')?.value);
    const usdRate = parseAmount(document.getElementById('pay_usd_rate')?.value) || 12800;
    const usdAccountId = document.getElementById('pay_usd_account')?.value || null;
    const accountId = document.getElementById('pay_account').value;
    const description = document.getElementById('pay_description').value;
    
    const usdSumUzs = usdAmount * usdRate;
    const totalAmount = cashAmount + cardAmount + usdSumUzs;

    if (totalAmount <= 0) {
        alert('Hech qanday to\'lov summasi kiritilmadi!');
        return;
    }
    
    // Bog'lanuvchi sotuvlar (FIFO yoki qo'lda belgilangan)
    const isLinkingChecked = document.getElementById('pay_link_demands_toggle')?.checked;
    const linkedDemands = [];
    const selectedDemandIds = [];

    if (isLinkingChecked) {
        for (const [did, amt] of Object.entries(demandAllocations)) {
            if (amt > 0.01) {
                linkedDemands.push({ demand_id: did, amount: amt });
                selectedDemandIds.push(did);
            }
        }
    }
    
    const saveBtn = document.querySelector('#paymentModal button[onclick="submitCustomerPayment()"]');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = '⏳ Saqlanmoqda...'; }
    
    try {
        const bodyData = {
            counterparty_id: window.currentPaymentCustomerId,
            cash_amount: cashAmount,
            card_amount: cardAmount,
            usd_amount: usdAmount,
            usd_rate: usdRate,
            usd_account_id: usdAccountId || null,
            account_id: accountId || null,
            linked_demands: linkedDemands.length > 0 ? linkedDemands : null,
            demand_ids: selectedDemandIds.length > 0 ? selectedDemandIds : null,
            auto_fifo: isFifoAuto,
            description: description || `${window.currentPaymentCustomerName} uchun to'lov`,
        };
        
        const resp = await apiFetch('/payments/customer', {
            method: 'POST',
            body: JSON.stringify(bodyData),
        });
        
        if (resp && resp.success) {
            const linkedCount = resp.data?.linked_demands_count || linkedDemands.length;
            const linkMsg = linkedCount > 0 ? ` (${linkedCount} ta sotuvga bog'landi)` : '';
            alert(`✅ To'lov qabul qilindi! Jami: ${formatMoney(totalAmount)}${linkMsg}`);
            closePaymentModal();
            closeCustomerModal();
            await loadCustomers();
        } else {
            throw new Error(resp?.detail || 'Noma\'lum xatolik');
        }
    } catch (error) {
        alert('❌ Xato: ' + error.message);
    } finally {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = '💾 To\'lovni amalga oshirish'; }
    }
}

async function createNewGroup() {
    const groupName = prompt("Yangi guruh nomi:");
    if (!groupName || !groupName.trim()) return;
    
    try {
        const response = await apiFetch('/customers/groups', {
            method: 'POST',
            body: JSON.stringify({ name: groupName.trim() }),
        });
        
        if (response.success) {
            alert('✅ Guruh yaratildi!');
            // Modalni qayta ochish
            const customerId = currentEditCustomer?.id;
            if (customerId) {
                await showCustomerDetail(customerId);
            }
        }
    } catch (error) {
        alert('❌ Xato: ' + error.message);
    }
}

// Global o'zgaruvchi (joriy mijoz ID ni saqlash)
let currentEditCustomer = null;

function closeCustomerModal() {
    document.getElementById('customerModal').classList.remove('active');
}

document.getElementById('customerModal').addEventListener('click', (e) => {
    if (e.target.id === 'customerModal') closeCustomerModal();
});

// ================= AKT SVERKA (SOLISHTIRMA DALOLATNOMA) =================
let currentAktCustomerId = null;
let currentAktCustomerName = '';
let currentAktData = null;

async function openAktSverka(customerId, customerName) {
    currentAktCustomerId = customerId;
    currentAktCustomerName = customerName || 'Mijoz';

    const modal = document.getElementById('aktSverkaModal');
    modal.classList.add('active');
    document.getElementById('aktSverkaModalTitle').textContent = `📑 Solishtirma dalolatnoma (Акт сверки) — ${currentAktCustomerName}`;

    selectAktPeriod('all', false);
    await loadAktSverka();
}

function closeAktSverkaModal() {
    const modal = document.getElementById('aktSverkaModal');
    if (modal) modal.classList.remove('active');
}

function selectAktPeriod(period, reload = true) {
    document.querySelectorAll('[data-akt-period]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.aktPeriod === period);
    });

    const now = new Date();
    let fromStr = '';
    let toStr = now.toISOString().split('T')[0];

    if (period === 'today') {
        fromStr = toStr;
    } else if (period === 'this_week') {
        const day = now.getDay() || 7;
        const monday = new Date(now);
        monday.setDate(now.getDate() - day + 1);
        fromStr = monday.toISOString().split('T')[0];
    } else if (period === 'this_month') {
        const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
        fromStr = firstDay.toISOString().split('T')[0];
    } else if (period === 'last_month') {
        const firstDay = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        const lastDay = new Date(now.getFullYear(), now.getMonth(), 0);
        fromStr = firstDay.toISOString().split('T')[0];
        toStr = lastDay.toISOString().split('T')[0];
    } else if (period === 'this_year') {
        fromStr = `${now.getFullYear()}-01-01`;
    } else if (period === 'all') {
        fromStr = '';
        toStr = '';
    }

    document.getElementById('aktDateFrom').value = fromStr;
    document.getElementById('aktDateTo').value = toStr;

    if (reload) {
        loadAktSverka();
    }
}

async function copyAktSverkaTelegramText() {
    if (!currentAktData) {
        if (typeof showToast === 'function') showToast("Ma'lumotlar yuklanmagan!", "warning");
        else alert("Ma'lumotlar yuklanmagan!");
        return;
    }
    const { organization, counterparty, period, initial_balance, operations, summary } = currentAktData;

    let text = `📑 *O'ZARO HISOB-KITOBLAR SOLISHTIRMA DALOLATNOMASI (АКТ СВЕРКИ)*\n`;
    text += `🏢 *Tashkilot:* ${organization.name || 'Said_Baraka'}\n`;
    text += `👤 *Mijoz:* ${counterparty.name || 'Mijoz'}${counterparty.phone ? ' (Tel: ' + counterparty.phone + ')' : ''}\n`;
    text += `📅 *Davr:* ${period.date_from || 'Boshidan'} dan ${period.date_to || 'Hozirgacha'} gacha\n\n`;
    text += `🏁 *Boshlang'ich qoldiq:* ${formatMoney(initial_balance)}\n`;
    text += `━━━━━━━━━━━━━━━━━━━━━\n`;

    if (operations && operations.length > 0) {
        operations.forEach((op, idx) => {
            const dateStr = (op.moment || '').substring(0, 16);
            let change = '';
            if (op.debit > 0) change = `➕ Sotuv: ${formatMoney(op.debit)}`;
            if (op.credit > 0) {
                const usdTxt = (op.is_usd && op.usd_amount) ? ` ($${Number(op.usd_amount).toFixed(2)})` : '';
                change = `➖ To'lov: ${formatMoney(op.credit)}${usdTxt}`;
            }
            const docNum = op.doc_number && op.doc_number !== '—' ? ` №${op.doc_number}` : '';
            text += `${idx + 1}. ${dateStr} | ${op.type_name}${docNum}\n   ${change} ➔ Qoldiq: ${formatMoney(op.balance_after)}\n`;
        });
    } else {
        text += `(Ushbu davrda operatsiyalar mavjud emas)\n`;
    }

    text += `━━━━━━━━━━━━━━━━━━━━━\n`;
    text += `📈 *Jami Sotuv (Debet):* ${formatMoney(summary.total_debit)}\n`;
    text += `📉 *Jami To'lov (Kredit):* ${formatMoney(summary.total_credit)}\n`;
    text += `🏁 *YAKUNIY QARZDORLIK:* ${formatMoney(summary.closing_balance)}\n`;
    text += `⚖️ *Xulosa:* ${summary.status_text || ''}\n`;

    try {
        await navigator.clipboard.writeText(text);
        if (typeof showToast === 'function') showToast("✅ Telegram uchun matn nusxalandi!", "success");
        else alert("✅ Telegram uchun matn nusxalandi!");
    } catch (e) {
        const ta = document.createElement('textarea');
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        if (typeof showToast === 'function') showToast("✅ Telegram uchun matn nusxalandi!", "success");
        else alert("✅ Telegram uchun matn nusxalandi!");
    }
}

function downloadAktSverkaFile() {
    if (!currentAktData) {
        if (typeof showToast === 'function') showToast("Ma'lumotlar yuklanmagan!", "warning");
        else alert("Ma'lumotlar yuklanmagan!");
        return;
    }
    const aktArea = document.getElementById('aktPrintArea');
    if (!aktArea) return;

    const custName = (currentAktData.counterparty?.name || 'Mijoz').replace(/[^a-zA-Z0-9_Ѐ-ӿ]/g, '_');
    const filename = `Akt_Sverka_${custName}_${new Date().toISOString().substring(0, 10)}.html`;

    const htmlContent = `<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<title>Akt Sverki — ${currentAktData.counterparty?.name || ''}</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding: 30px; background: #fff; color: #1e293b; margin: 0; }
.akt-document { max-width: 900px; margin: 0 auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 16px 0; }
th, td { border: 1px solid #cbd5e1; padding: 8px 10px; }
th { background: #0284c7; color: white; text-align: left; }
.text-right { text-align: right; }
.text-center { text-align: center; }
@media print {
    body { padding: 0; }
    @page { margin: 1cm; size: A4; }
}
</style>
</head>
<body>
<div class="akt-document">
${aktArea.innerHTML}
</div>
</body>
</html>`;

    const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    if (typeof showToast === 'function') showToast("📄 Pechat varianti fayl sifatida yuklandi!", "success");
    else alert("📄 Pechat varianti fayl sifatida yuklandi!");
}

// Alias for backwards compatibility
function copyAktSverkaText() {
    copyAktSverkaTelegramText();
}

async function loadAktSverka() {
    if (!currentAktCustomerId) return;

    const body = document.getElementById('aktSverkaBody');
    body.innerHTML = '<div style="text-align:center;padding:40px;"><div class="loading">⏳ Yuklanmoqda...</div></div>';

    const dateFrom = document.getElementById('aktDateFrom').value;
    const dateTo = document.getElementById('aktDateTo').value;

    const params = new URLSearchParams();
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);

    try {
        const resp = await apiFetch(`/customers/${currentAktCustomerId}/akt-sverka?${params.toString()}`);
        if (resp.success && resp.data) {
            currentAktData = resp.data;
            renderAktSverka(resp.data);
        } else {
            throw new Error(resp.message || 'Akt sverka ma\'lumotlarini olib bo\'lmadi');
        }
    } catch (e) {
        console.error('Akt sverka yuklash xatosi:', e);
        body.innerHTML = `<div style="text-align:center;padding:30px;color:red;">❌ Xatolik: ${e.message}</div>`;
    }
}

function renderAktSverka(data) {
    const body = document.getElementById('aktSverkaBody');
    const { organization, counterparty, period, initial_balance, operations, summary } = data;

    const rowsHtml = operations.map((op, i) => {
        let creditHtml = op.credit > 0 ? formatMoney(op.credit) : '—';
        if (op.credit > 0 && op.is_usd && op.usd_amount) {
            creditHtml = `
                <div>${formatMoney(op.credit)}</div>
                <div style="font-size:11px;color:var(--accent);font-weight:700;">($${Number(op.usd_amount).toFixed(2)})</div>
            `;
        }
        return `
        <tr>
            <td style="text-align:center;padding:8px 4px;width:35px;border-bottom:1px solid #e2e8f0;">${i + 1}</td>
            <td style="padding:8px;white-space:nowrap;width:95px;border-bottom:1px solid #e2e8f0;">${formatDate(op.moment)}</td>
            <td style="padding:8px;border-bottom:1px solid #e2e8f0;">
                <strong style="color:var(--primary);">${op.type_name}</strong>
                ${op.doc_number && op.doc_number !== '—' ? `<span style="color:var(--accent);font-weight:700;"> №${op.doc_number}</span>` : ''}
            </td>
            <td style="padding:8px;color:#555;font-size:12px;border-bottom:1px solid #e2e8f0;">${op.description || '—'}</td>
            <td style="padding:8px;text-align:right;font-weight:600;color:var(--primary);border-bottom:1px solid #e2e8f0;">${op.debit > 0 ? formatMoney(op.debit) : '—'}</td>
            <td style="padding:8px;text-align:right;font-weight:600;color:var(--success);border-bottom:1px solid #e2e8f0;">${creditHtml}</td>
            <td style="padding:8px;text-align:right;font-weight:700;color:${op.balance_after > 0 ? 'var(--danger)' : 'var(--success)'};border-bottom:1px solid #e2e8f0;">
                ${formatMoney(op.balance_after)}
            </td>
        </tr>
    `;
    }).join('');

    body.innerHTML = `
        <div id="aktPrintArea" class="akt-document">
            <!-- Rasmiy sarlavha -->
            <div style="text-align:center;margin-bottom:20px;border-bottom:2px solid var(--primary);padding-bottom:12px;">
                <h2 style="font-size:18px;color:var(--primary);margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px;">
                    O'ZARO HISOB-KITOBLAR SOLISHTIRMA DALOLATNOMASI (АКТ СВЕРКИ)
                </h2>
                <div style="font-size:13px;color:var(--text-light);font-weight:600;">
                    Davr: <strong>${period.date_from || 'Boshidan'}</strong> dan <strong>${period.date_to || 'Hozirgacha'}</strong> gacha
                </div>
            </div>

            <!-- Tomonlar ma'lumotlari -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;background:#f8fafd;padding:12px 16px;border-radius:8px;border:1px solid var(--border);">
                <div>
                    <div style="font-size:11px;font-weight:700;color:var(--text-light);text-transform:uppercase;">BIZNING TASHKILOT:</div>
                    <div style="font-size:15px;font-weight:700;color:var(--primary);margin-top:2px;">${organization.name}</div>
                    ${organization.inn ? `<div style="font-size:12px;color:#666;">INN: ${organization.inn}</div>` : ''}
                    ${organization.phone ? `<div style="font-size:12px;color:#666;">Tel: ${organization.phone}</div>` : ''}
                </div>
                <div>
                    <div style="font-size:11px;font-weight:700;color:var(--text-light);text-transform:uppercase;">MIJOZ (KONTRAGENT):</div>
                    <div style="font-size:15px;font-weight:700;color:var(--primary);margin-top:2px;">${counterparty.name}</div>
                    ${counterparty.phone ? `<div style="font-size:12px;color:#666;">Tel: ${counterparty.phone}</div>` : ''}
                    ${counterparty.email ? `<div style="font-size:12px;color:#666;">Email: ${counterparty.email}</div>` : ''}
                </div>
            </div>

            <!-- Asosiy Sverka Jadvali -->
            <div style="overflow-x:auto;">
                <table class="akt-table" style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:16px;">
                    <thead>
                        <tr style="background:var(--primary);color:white;">
                            <th style="padding:10px 6px;text-align:center;width:35px;">№</th>
                            <th style="padding:10px 8px;text-align:left;width:95px;">Sana</th>
                            <th style="padding:10px 8px;text-align:left;">Hujjat turi</th>
                            <th style="padding:10px 8px;text-align:left;">Izoh</th>
                            <th style="padding:10px 8px;text-align:right;width:120px;">Sotuv (Debet)</th>
                            <th style="padding:10px 8px;text-align:right;width:120px;">To'lov (Kredit)</th>
                            <th style="padding:10px 8px;text-align:right;width:120px;">Qoldiq (Saldo)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <!-- Boshlang'ich saldo -->
                        <tr style="background:#edf4fe;font-weight:700;">
                            <td colspan="4" style="padding:10px 8px;border-bottom:1px solid #cbd5e1;">
                                🏁 BOSHLANG'ICH QOLDIQ (${period.date_from || 'Davr boshi'} holatiga)
                            </td>
                            <td style="padding:10px 8px;text-align:right;border-bottom:1px solid #cbd5e1;">—</td>
                            <td style="padding:10px 8px;text-align:right;border-bottom:1px solid #cbd5e1;">—</td>
                            <td style="padding:10px 8px;text-align:right;border-bottom:1px solid #cbd5e1;color:${initial_balance > 0 ? 'var(--danger)' : 'var(--success)'};">
                                ${formatMoney(initial_balance)}
                            </td>
                        </tr>

                        ${rowsHtml || '<tr><td colspan="7" style="text-align:center;padding:20px;color:var(--text-light);border-bottom:1px solid #e2e8f0;">Ushbu davrda hech qanday operatsiya bo\'lmagan</td></tr>'}

                        <!-- Davr aylanmasi (Обороты) -->
                        <tr style="background: var(--bg);font-weight:700;border-top:2px solid #94a3b8;">
                            <td colspan="4" style="padding:10px 8px;">DAVR BO'YICHA JAMI AYLANMA:</td>
                            <td style="padding:10px 8px;text-align:right;color:var(--primary);">${formatMoney(summary.total_debit)}</td>
                            <td style="padding:10px 8px;text-align:right;color:var(--success);">${formatMoney(summary.total_credit)}</td>
                            <td style="padding:10px 8px;text-align:right;">—</td>
                        </tr>

                        <!-- Yakuniy saldo -->
                        <tr style="background:#e6f4ea;font-weight:800;font-size:14px;border-top:2px solid #86efac;">
                            <td colspan="4" style="padding:12px 8px;">
                                🏁 YAKUNIY QOLDIQ (${period.date_to || 'Hozirgi'} holatiga):
                            </td>
                            <td colspan="2" style="padding:12px 8px;text-align:right;font-size:12px;color:#555;font-weight:600;">
                                Netto o'zgarish: ${formatMoney(summary.total_debit - summary.total_credit)}
                            </td>
                            <td style="padding:12px 8px;text-align:right;color:${summary.closing_balance > 0 ? 'var(--danger)' : 'var(--success)'};">
                                ${formatMoney(summary.closing_balance)}
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Xulosa kartasi -->
            <div style="background: var(--card);border:1px solid #ffe299;padding:12px 16px;border-radius:8px;margin-bottom:20px;display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <div style="font-size:11px;color:#8a6d3b;font-weight:700;text-transform:uppercase;">XULOSA:</div>
                    <div style="font-size:15px;font-weight:800;color:#2c3e50;margin-top:2px;">${summary.status_text}</div>
                </div>
                <div style="font-size:24px;">⚖️</div>
            </div>

            <!-- Imzolar qismi (Print uchun) -->
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-top:24px;padding-top:16px;border-top:1px dashed #ccc;">
                <div>
                    <div style="font-weight:700;margin-bottom:18px;">${organization.name} nomidan:</div>
                    <div style="border-bottom:1px solid #000;margin-bottom:6px;height:24px;"></div>
                    <div style="font-size:12px;color:#666;display:flex;justify-content:space-between;">
                        <span>(Imzo / F.I.SH)</span>
                        <span>M.O'.</span>
                    </div>
                </div>
                <div>
                    <div style="font-weight:700;margin-bottom:18px;">${counterparty.name} nomidan:</div>
                    <div style="border-bottom:1px solid #000;margin-bottom:6px;height:24px;"></div>
                    <div style="font-size:12px;color:#666;display:flex;justify-content:space-between;">
                        <span>(Imzo / F.I.SH)</span>
                        <span>M.O'.</span>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function printAktSverka() {
    window.print();
}

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

    // Summa va to'lov turi
    let currentMethod = 'cash';
    const isDollar = Boolean(tx && (tx.account_type === 'dollar' || tx.is_usd === true || (tx.usd_amount && tx.usd_amount > 0)));
    if (isDollar) {
        currentMethod = 'usd';
    } else if (docType === 'paymentin' || docType === 'paymentout' || (tx && (tx.doc_type === 'paymentin' || tx.doc_type === 'paymentout' || tx.type === 'card' || tx.account_type === 'bank' || tx.account_id))) {
        currentMethod = 'card';
    } else {
        currentMethod = 'cash';
    }

    const methodSelect = document.getElementById('editPayMethod') || document.getElementById('editPayCurrency');
    if (methodSelect) {
        methodSelect.value = currentMethod;
    }

    const amtInput = document.getElementById('editPayAmount');
    const usdGroup = document.getElementById('editPayUsdGroup');
    const usdInput = document.getElementById('editPayUsdAmount');
    const rateInput = document.getElementById('editPayUsdRate');
    const accGroup = document.getElementById('editPayAccountGroup');

    await loadEditAccountsSelectCustomers((tx && (tx.account_id || (tx.account && tx.account.id))) || null);

    if (currentMethod === 'usd') {
        if (usdGroup) usdGroup.style.display = 'block';
        if (accGroup) accGroup.style.display = 'none';
        const actualUsd = (tx && tx.usd_amount) ? tx.usd_amount : ((tx && tx.amount && tx.usd_rate) ? (tx.amount / tx.usd_rate) : 0);
        const actualRate = (tx && tx.usd_rate) || window.currentUSDRate || 12800;
        const actualUzs = (tx && tx.amount) ? tx.amount : Math.round(actualUsd * actualRate);
        if (usdInput) usdInput.value = formatNumber(actualUsd, true);
        if (rateInput) rateInput.value = formatNumber(actualRate);
        if (amtInput) amtInput.value = formatNumber(Math.round(actualUzs));
    } else if (currentMethod === 'card') {
        if (usdGroup) usdGroup.style.display = 'none';
        if (accGroup) accGroup.style.display = 'block';
        if (amtInput) amtInput.value = tx ? formatNumber(tx.amount || 0) : '0';
    } else {
        if (usdGroup) usdGroup.style.display = 'none';
        if (accGroup) accGroup.style.display = 'none';
        if (amtInput) amtInput.value = tx ? formatNumber(tx.amount || 0) : '0';
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

    let linkedDemandId = (tx && (tx.linked_demand_id || tx.demand_id)) || null;

    // Backenddan to'liq hujjatni olib, bog'langan sotuvni 100% tekshirish
    try {
        const fullDocResp = await apiFetch(`/payments/${(tx && tx.type) || docType || 'cashin'}/${paymentId}`);
        if (fullDocResp && fullDocResp.success && fullDocResp.data) {
            const docData = fullDocResp.data;
            const rawOps = docData.operations;
            const ops = Array.isArray(rawOps) ? rawOps : (rawOps && Array.isArray(rawOps.rows) ? rawOps.rows : []);
            for (const op of ops) {
                const href = (op.meta && op.meta.href) || op.href || '';
                if (href.includes('/entity/demand/')) {
                    linkedDemandId = href.split('/').pop();
                    break;
                }
            }
            if (!linkedDemandId && docData.demand && docData.demand.meta && docData.demand.meta.href) {
                linkedDemandId = docData.demand.meta.href.split('/').pop();
            }
        }
    } catch (err) {
        console.warn('Payment doc fetch warning in customers.js:', err);
    }

    const linkSelect = document.getElementById('editPayLinkDemand');
    if (linkSelect) {
        linkSelect.innerHTML = '<option value="">(Bog\'lanmagan / Alohida to\'lov)</option>';
        if (typeof currentEditCustomer !== 'undefined' && currentEditCustomer && currentEditCustomer.demands && currentEditCustomer.demands.length > 0) {
            currentEditCustomer.demands.forEach(d => {
                const opt = document.createElement('option');
                opt.value = d.id;
                const rem = d.remaining ? ` | Qarz: ${formatMoney(d.remaining)}` : '';
                opt.textContent = `№ ${d.name} (${d.moment ? d.moment.substring(0, 10) : ''}) — ${formatMoney(d.sum)}${rem}`;
                if (linkedDemandId && linkedDemandId === d.id) {
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

function toggleEditPaymentMethod() {
    const methodSelect = document.getElementById('editPayMethod') || document.getElementById('editPayCurrency');
    const method = methodSelect ? methodSelect.value : 'cash';
    const usdGroup = document.getElementById('editPayUsdGroup');
    const accGroup = document.getElementById('editPayAccountGroup');
    const usdInput = document.getElementById('editPayUsdAmount');
    const rateInput = document.getElementById('editPayUsdRate');

    if (method === 'usd' || method === 'USD') {
        if (usdGroup) usdGroup.style.display = 'block';
        if (accGroup) accGroup.style.display = 'none';
        if (!rateInput.value || parseAmount(rateInput.value) <= 0) {
            rateInput.value = formatNumber(window.currentUSDRate || 12800);
        }
        const amt = parseAmount(document.getElementById('editPayAmount')?.value);
        const rate = parseAmount(rateInput?.value) || (window.currentUSDRate || 12800);
        const curUsd = parseAmount(usdInput?.value);
        if (curUsd > 0) {
            recalcEditUzsFromUsd();
        } else if (amt > 0 && rate > 0) {
            usdInput.value = formatNumber(amt / rate, true);
        }
    } else if (method === 'card') {
        if (usdGroup) usdGroup.style.display = 'none';
        if (accGroup) accGroup.style.display = 'block';
        loadEditAccountsSelectCustomers(currentEditingTx?.account_id || currentEditingTx?.account?.id);
    } else {
        if (usdGroup) usdGroup.style.display = 'none';
        if (accGroup) accGroup.style.display = 'none';
    }
}

function toggleEditCurrencyInputs() {
    toggleEditPaymentMethod();
}

function recalcEditUzsFromUsd() {
    const usdVal = parseAmount(document.getElementById('editPayUsdAmount')?.value);
    const rate = parseAmount(document.getElementById('editPayUsdRate')?.value) || (window.currentUSDRate || 12800);
    if (usdVal > 0 && document.getElementById('editPayAmount')) {
        document.getElementById('editPayAmount').value = formatNumber(Math.round(usdVal * rate));
    }
}

function recalcEditUsdFromUzs() {
    const methodSelect = document.getElementById('editPayMethod') || document.getElementById('editPayCurrency');
    const method = methodSelect ? methodSelect.value : 'cash';
    if (method === 'usd' || method === 'USD') {
        const amt = parseAmount(document.getElementById('editPayAmount')?.value);
        const rate = parseAmount(document.getElementById('editPayUsdRate')?.value) || (window.currentUSDRate || 12800);
        if (amt > 0 && rate > 0 && document.getElementById('editPayUsdAmount')) {
            document.getElementById('editPayUsdAmount').value = formatNumber(amt / rate, true);
        }
    }
}

async function handleEditPaymentSubmit(event) {
    event.preventDefault();
    const paymentId = document.getElementById('editPayId')?.value;
    const docType = document.getElementById('editPayDocType')?.value || 'cashin';
    const amount = parseAmount(document.getElementById('editPayAmount')?.value);
    const methodSelect = document.getElementById('editPayMethod') || document.getElementById('editPayCurrency');
    const method = methodSelect ? methodSelect.value : 'cash';
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

    if (method === 'usd' || method === 'USD') {
        const usdAmount = parseAmount(document.getElementById('editPayUsdAmount')?.value);
        const usdRate = parseAmount(document.getElementById('editPayUsdRate')?.value) || (window.currentUSDRate || 12800);
        payload.usd_amount = usdAmount;
        payload.usd_rate = usdRate;
    } else if (method === 'card') {
        const accId = document.getElementById('editPayAccountSelect')?.value;
        if (accId) {
            payload.account_id = accId;
        }
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
            throw new Error(resp?.detail || 'To\'lovni yangilashda xatolik');
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
            throw new Error(resp?.detail || 'O\'chirishda xatolik');
        }
    } catch (e) {
        alert(`❌ Xato: ${e.message}`);
    }
}

// ===== YANGI MIJOZ =====
function openNewCustomerModal() {
    const n = document.getElementById('newCustName');
    const p = document.getElementById('newCustPhone');
    const g = document.getElementById('newCustGroup');
    const a = document.getElementById('newCustAddress');
    const d = document.getElementById('newCustDesc');
    if (n) n.value = '';
    if (p) p.value = '';
    if (g) g.value = '';
    if (a) a.value = '';
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
    const group = document.getElementById('newCustGroup')?.value?.trim();
    const address = document.getElementById('newCustAddress')?.value?.trim();
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
            group: group || '',
            address: address || '',
            description: desc || ''
        };
        const resp = await apiFetch('/customers', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        
        if(resp && resp.success) {
            alert('✅ Yangi mijoz muvaffaqiyatli yaratildi!');
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
            btn.textContent = '💾 Mijozni Saqlash';
        }
    }
}

// --- Keyboard Navigation for Modals ---
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const aktModal = document.getElementById('aktSverkaModal');
        if (aktModal && aktModal.classList.contains('active')) {
            closeAktSverkaModal();
            return;
        }
        const payModal = document.getElementById('paymentModal');
        if (payModal && payModal.classList.contains('active')) {
            closePaymentModal();
            return;
        }
        const editPayModal = document.getElementById('editPaymentModal');
        if (editPayModal && editPayModal.classList.contains('active')) {
            closeEditPaymentModal();
            return;
        }
        const custModal = document.getElementById('customerModal');
        if (custModal && custModal.classList.contains('active')) {
            closeCustomerModal();
            return;
        }
    }

    const payModal = document.getElementById('paymentModal');
    if (payModal && payModal.classList.contains('active')) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            submitCustomerPayment();
        }
    }
});

// Modal tashqarisiga (backdrop) bosganda yopish
window.addEventListener('click', (e) => {
    const aktModal = document.getElementById('aktSverkaModal');
    if (e.target === aktModal) {
        closeAktSverkaModal();
    }
    const editPayModal = document.getElementById('editPaymentModal');
    if (e.target === editPayModal) {
        closeEditPaymentModal();
    }
});

