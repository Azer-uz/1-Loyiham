// ===== GLOBAL O'ZGARUVCHILAR =====
let currentOffset = 0;
const pageSize = 50;
let totalSize = 0;
let currentPeriod = 'today';
let currentStateFilter = 'all';
let currentEditDemand = null;
let demandStates = [];
let orgAccounts = [];
let oplataAttribute = null;
let currentLoadedDemands = [];
let currentOrgName = 'Said_Baraka';
let appPaymentMethods = [];
let appAccountsList = [];
let appReferenceRate = 12850;

// ===== SARALASH HOLATI =====
let demandSortField = null;
let demandSortDir = 'asc';

async function loadPaymentSettings() {
    try {
        const [methodsResp, accsResp, rateResp] = await Promise.all([
            apiFetch('/settings/payment-methods').catch(() => null),
            apiFetch('/settings/accounts').catch(() => null),
            apiFetch('/settings/reference-rate').catch(() => null)
        ]);
        if (methodsResp && methodsResp.success && methodsResp.data) {
            appPaymentMethods = methodsResp.data.methods || (Array.isArray(methodsResp.data) ? methodsResp.data : []);
            const usdM = appPaymentMethods.find(m => m.id === 'usd' || m.currency === 'USD');
            if (usdM && usdM.default_rate) {
                appReferenceRate = usdM.default_rate;
            }
        }
        if (accsResp && accsResp.success && accsResp.data) {
            appAccountsList = accsResp.data.accounts || (Array.isArray(accsResp.data) ? accsResp.data : []);
        }
        if (rateResp && rateResp.success && rateResp.data && rateResp.data.rate && !appPaymentMethods.some(m => (m.id === 'usd' || m.currency === 'USD') && m.default_rate)) {
            appReferenceRate = rateResp.data.rate;
        }
        window.appReferenceRate = appReferenceRate;
    } catch (e) {
        console.warn("To'lov sozlamalarini olishda xatolik:", e);
    }
}

// Oylar nomlari (O'zbekcha)
const UZ_MONTHS = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
];

let activeDatePivot = new Date(); // Hozirgi ko'rilayotgan sana/oy
currentPeriod = 'today'; // Standart davr: 'today' (Bugun - juda tez ochiladi)

function getLocalDateString(d) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function updateDateRangeUI(applyLoad = true) {
    const fromInput = document.getElementById('dateFrom');
    const toInput = document.getElementById('dateTo');
    const labelEl = document.getElementById('periodDisplayLabel');
    const navEl = document.getElementById('periodNavigator');

    let fromDate, toDate, labelText;

    if (currentPeriod === 'month') {
        const year = activeDatePivot.getFullYear();
        const month = activeDatePivot.getMonth();
        fromDate = new Date(year, month, 1);
        toDate = new Date(year, month + 1, 0); // Oydagi oxirgi kun (28, 29, 30 yoki 31)
        labelText = `${UZ_MONTHS[month]} ${year}`;
        if (navEl) navEl.style.display = 'inline-flex';
    } else if (currentPeriod === 'today') {
        fromDate = new Date(activeDatePivot.getFullYear(), activeDatePivot.getMonth(), activeDatePivot.getDate());
        toDate = new Date(activeDatePivot.getFullYear(), activeDatePivot.getMonth(), activeDatePivot.getDate());
        const d = activeDatePivot.getDate();
        const m = UZ_MONTHS[activeDatePivot.getMonth()];
        const y = activeDatePivot.getFullYear();
        labelText = `${d}-${m} ${y}`;
        if (navEl) navEl.style.display = 'inline-flex';
    } else if (currentPeriod === 'yesterday') {
        fromDate = new Date(activeDatePivot.getFullYear(), activeDatePivot.getMonth(), activeDatePivot.getDate());
        toDate = new Date(activeDatePivot.getFullYear(), activeDatePivot.getMonth(), activeDatePivot.getDate());
        const d = activeDatePivot.getDate();
        const m = UZ_MONTHS[activeDatePivot.getMonth()];
        const y = activeDatePivot.getFullYear();
        labelText = `Kecha (${d}-${m})`;
        if (navEl) navEl.style.display = 'inline-flex';
    } else if (currentPeriod === 'week') {
        toDate = new Date(activeDatePivot.getFullYear(), activeDatePivot.getMonth(), activeDatePivot.getDate());
        fromDate = new Date(toDate.getTime() - 6 * 86400000);
        labelText = `${fromDate.getDate()}-${UZ_MONTHS[fromDate.getMonth()]} — ${toDate.getDate()}-${UZ_MONTHS[toDate.getMonth()]}`;
        if (navEl) navEl.style.display = 'inline-flex';
    } else if (currentPeriod === 'all') {
        if (fromInput) fromInput.value = '';
        if (toInput) toInput.value = '';
        if (labelEl) labelEl.textContent = 'Barcha davr';
        if (navEl) navEl.style.display = 'none';
        document.querySelectorAll('.quick-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.period === 'all'));
        if (applyLoad) {
            currentOffset = 0;
            loadDemands();
        }
        return;
    }

    if (fromInput) fromInput.value = getLocalDateString(fromDate);
    if (toInput) toInput.value = getLocalDateString(toDate);
    if (labelEl) labelEl.textContent = labelText;

    document.querySelectorAll('.quick-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.period === currentPeriod));

    if (applyLoad) {
        currentOffset = 0;
        loadDemands();
    }
}

function selectPeriod(period) {
    currentPeriod = period;
    const now = new Date();
    if (period === 'today') {
        activeDatePivot = new Date();
    } else if (period === 'yesterday') {
        activeDatePivot = new Date(now.getTime() - 86400000);
    } else if (period === 'week' || period === 'month') {
        activeDatePivot = new Date();
    }
    updateDateRangeUI(true);
}

function navigatePeriod(direction) {
    if (currentPeriod === 'month') {
        activeDatePivot.setMonth(activeDatePivot.getMonth() + direction);
    } else if (currentPeriod === 'today' || currentPeriod === 'yesterday') {
        activeDatePivot.setDate(activeDatePivot.getDate() + direction);
    } else if (currentPeriod === 'week') {
        activeDatePivot.setDate(activeDatePivot.getDate() + direction * 7);
    }
    updateDateRangeUI(true);
}

// ===== SAHIFA YUKLANGANDA =====
document.addEventListener('DOMContentLoaded', async () => {
    try {
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

        try {
            const orgResp = await apiFetch('/dashboard/organization');
            if (orgResp && orgResp.success && orgResp.data) {
                currentOrgName = orgResp.data.name || 'Said_Baraka';
                const orgEl = document.getElementById('orgName');
                if (orgEl) orgEl.textContent = currentOrgName;
            }
        } catch (e) {}

        // sessionStorage orqali tashqaridan o'tish (customers.html → demands.html)
        const openDemandId = sessionStorage.getItem('openDemand');
        if (openDemandId) {
            sessionStorage.removeItem('openDemand');
            // Sana filtrini 'all' ga o'zgartiramiz — shunda boshqa kundagi sotuv ham topiladi
            currentPeriod = 'all';
            updateDateRangeUI(false);
            loadDemands();
            // Biroz kutib, keyin to'g'ridan-to'g'ri modalni ochamiz
            try {
                await showDetail(openDemandId);
            } catch (e) {
                console.warn('Auto-open demand kartochka xatosi:', e);
            }
        } else {
            // Standart davr: 'today' (Joriy to'liq kun)
            updateDateRangeUI(false);
            // 🚀 ZUDLIK BILAN sotuvlar ro'yxatini yuklash (Local DB dan darhol keladi)
            loadDemands();
        }

        // Tashkilot, hisob raqamlar, valyuta kursi va statuslarni fonda parallel yuklash
        Promise.all([
            apiFetch('/dashboard/organization').catch(() => null),
            apiFetch('/demands/meta/states').catch(() => null),
            fetchUSDRate().catch(() => null),
            loadPaymentSettings().catch(() => null),
        ]).then(async ([orgResp, statesResp]) => {
            if (orgResp && orgResp.success && orgResp.data) {
                if (orgResp.data.name) currentOrgName = orgResp.data.name;
                if (orgResp.data.id) {
                    const accountsResp = await apiFetch(`/payments/accounts/${orgResp.data.id}`).catch(() => null);
                    if (accountsResp && accountsResp.success) {
                        orgAccounts = accountsResp.data || [];
                    }
                }
            }

            if (statesResp && statesResp.success && statesResp.data) {
                demandStates = statesResp.data || [];
            }
        }).catch(e => console.warn('Boshlang\'ich metadata yuklanmadi:', e));

        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', debounce(() => {
                currentOffset = 0;
                loadDemands();
            }, 300));
        }

        // Sana qo'lda o'zgarganda
        const onCustomDateChange = () => {
            const f = document.getElementById('dateFrom').value;
            const t = document.getElementById('dateTo').value;
            if (f && t) {
                document.querySelectorAll('.quick-btn').forEach(btn => btn.classList.remove('active'));
                const labelEl = document.getElementById('periodDisplayLabel');
                if (labelEl) labelEl.textContent = `${f} — ${t}`;
            }
            currentOffset = 0;
            loadDemands();
        };

        document.getElementById('dateFrom').addEventListener('change', onCustomDateChange);
        document.getElementById('dateTo').addEventListener('change', onCustomDateChange);

    } catch (error) {
        console.error('DOMContentLoaded xatosi:', error);
        const tbody = document.getElementById('demandsTable');
        if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="loading" style="color:red;">Xato: ${error.message}</td></tr>`;
    }
});

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// ===== STATUS FILTRI =====
function selectStateFilter(status) {
    currentStateFilter = status;
    document.querySelectorAll('.status-filter-pill').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.status === status);
    });
    currentOffset = 0;
    loadDemands();
}

// ===== SOTUVLAR RO'YXATI =====
async function loadDemands() {
    const fromEl = document.getElementById('dateFrom');
    const toEl = document.getElementById('dateTo');
    const searchEl = document.getElementById('searchInput');
    const tbody = document.getElementById('demandsTable');

    const dateFrom = fromEl ? fromEl.value : '';
    const dateTo = toEl ? toEl.value : '';
    const search = searchEl ? searchEl.value.trim() : '';

    if (tbody) {
        tbody.innerHTML = '<tr><td colspan="9" class="loading"><span class="spinner-small" style="display:inline-block;width:14px;height:14px;border:2px solid #ccc;border-top-color:var(--primary);border-radius:50%;animation:spin 0.8s linear infinite;margin-right:8px;vertical-align:middle;"></span>Yuklanmoqda...</td></tr>';
    }

    try {
        const params = new URLSearchParams({ limit: pageSize, offset: currentOffset });
        if (dateFrom) params.append('date_from', dateFrom);
        if (dateTo) params.append('date_to', dateTo);
        if (search) params.append('search', search);
        if (currentStateFilter && currentStateFilter !== 'all') {
            params.append('state_filter', currentStateFilter);
        }

        const response = await apiFetch(`/demands?${params.toString()}`);
        if (response && response.success) {
            currentLoadedDemands = response.data || [];
            renderDemands(response.data);
            totalSize = (response.meta && response.meta.size !== undefined) ? response.meta.size : (response.data ? response.data.length : 0);
            updateResultsCount();
            renderPagination();
        } else {
            if (tbody) tbody.innerHTML = `<tr><td colspan="9" class="loading" style="color:red;">Xatolik: Sotuvlarni olib bo'lmadi</td></tr>`;
        }
    } catch (error) {
        console.error('loadDemands xatosi:', error);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="9" class="loading" style="color:red;">Xato: ${error.message}</td></tr>`;
        }
    }
}

function renderDemands(demands) {
    const tbody = document.getElementById('demandsTable');
    if (!demands || demands.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="loading">Sotuvlar topilmadi</td></tr>';
        return;
    }

    tbody.innerHTML = demands.map((d, index) => {
        const stateBg = d.state_color || '#64748b';
        const isPaid = (d.remaining || 0) <= 0.01;
        const debtClass = isPaid ? 'paid' : 'debt';

        return `
        <tr>
            <td>${currentOffset + index + 1}</td>
            <td>
                <a href="javascript:void(0)" onclick="showDetail('${d.id}')" style="color:var(--primary);text-decoration:none;font-weight:700;">
                    ${d.name}
                </a>
            </td>
            <td class="hide-mobile" style="white-space:nowrap;font-size:13px;color:var(--text-light);">${formatDate(d.moment)}</td>
            <td>
                <a href="/static/customers.html" onclick="sessionStorage.setItem('openCustomer','${d.agent_id || ''}')" style="color:var(--primary);text-decoration:none;font-weight:700;" title="Mijoz kartochkasini ochish">
                    ${d.agent_name}
                </a>
            </td>
            <td style="font-weight:700;white-space:nowrap;">${formatMoney(d.sum)}</td>
            <td class="hide-mobile ${debtClass}" style="font-weight:700;white-space:nowrap;">
                ${isPaid ? '<span style="color:var(--success)">0 so\'m</span>' : `<span style="color:var(--danger)">${formatMoney(d.remaining)}</span>`}
            </td>
            <td>
                <span class="state-pill" style="border-color:${stateBg}; color:${stateBg}; background: ${stateBg}15;">
                    <span class="pill-dot" style="background:${stateBg};"></span>
                    ${d.state_name || '—'}
                </span>
            </td>
            <td><span class="payment-badge payment-${d.payment_status}">${d.payment_status_name}</span></td>
            <td>
                <div style="display:flex;gap:4px;align-items:center;">
                    <button class="action-btn" onclick="showDetail('${d.id}')" title="Ko'rish">👁️</button>
                    <button class="action-btn edit-btn" onclick="showEdit('${d.id}')" title="Tahrirlash va To'lov">✏️</button>
                    <button class="action-btn action-btn-quick-status" onclick="openQuickStatus('${d.id}', '${d.name}', '${(d.state_name || '').replace(/'/g, "\\'")}')" title="Statusni tez o'zgartirish">🔄</button>
                    <button class="action-btn action-btn-print" onclick="printReceipt80mm('${d.id}')" title="80mm Kassa Cheki">🖨️</button>
                </div>
            </td>
        </tr>
    `}).join('');
}

function updateResultsCount() {
    const start = totalSize === 0 ? 0 : currentOffset + 1;
    const end = Math.min(currentOffset + pageSize, totalSize);
    document.getElementById('resultsCount').textContent = `${start}-${end} / Jami: ${totalSize} ta`;
}

function renderPagination() {
    const pagination = document.getElementById('pagination');
    const totalPages = Math.ceil(totalSize / pageSize);
    const currentPage = Math.floor(currentOffset / pageSize) + 1;
    if (totalPages <= 1) { pagination.innerHTML = ''; return; }

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

function goToPage(page) { currentOffset = (page - 1) * pageSize; loadDemands(); }

// ===== USTUNLAR BO'YICHA SARALASH (CLIENT-SIDE) =====
function sortDemandsBy(field) {
    if (demandSortField === field) {
        demandSortDir = demandSortDir === 'asc' ? 'desc' : 'asc';
    } else {
        demandSortField = field;
        demandSortDir = (field === 'sum' || field === 'remaining') ? 'desc' : 'asc';
    }

    const comparators = {
        'name': (a, b) => (a.name || '').localeCompare(b.name || '', 'uz'),
        'moment': (a, b) => (a.moment || '').localeCompare(b.moment || ''),
        'agent_name': (a, b) => (a.agent_name || '').localeCompare(b.agent_name || '', 'uz'),
        'sum': (a, b) => (a.sum || 0) - (b.sum || 0),
        'remaining': (a, b) => (a.remaining || 0) - (b.remaining || 0),
        'state_name': (a, b) => (a.state_name || '').localeCompare(b.state_name || '', 'uz'),
        'payment_status': (a, b) => (a.payment_status || '').localeCompare(b.payment_status || ''),
    };

    const cmp = comparators[field];
    if (!cmp) return;

    currentLoadedDemands.sort((a, b) => {
        const result = cmp(a, b);
        return demandSortDir === 'asc' ? result : -result;
    });

    renderDemands(currentLoadedDemands);
    updateDemandSortIndicators();
}

function updateDemandSortIndicators() {
    document.querySelectorAll('.demands-sortable').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        const arrow = th.querySelector('.sort-arrow');
        if (arrow) arrow.textContent = '↕';
    });

    if (demandSortField) {
        const activeTh = document.getElementById(`dth-${demandSortField}`);
        if (activeTh) {
            activeTh.classList.add(demandSortDir === 'asc' ? 'sorted-asc' : 'sorted-desc');
            const arrow = activeTh.querySelector('.sort-arrow');
            if (arrow) arrow.textContent = demandSortDir === 'asc' ? '▲' : '▼';
        }
    }
}

// ===== TEZKOR STATUS POPUP =====
function openQuickStatus(demandId, demandName, currentStateName) {
    const modal = document.getElementById('quickStatusModal');
    const info = document.getElementById('quickStatusDemandInfo');
    
    info.innerHTML = `Sotuv: <strong style="color:var(--primary); font-size:16px;">${demandName}</strong><br>Hozirgi status: <strong>${currentStateName || '—'}</strong>`;
    
    if (!demandStates || demandStates.length === 0) {
        apiFetch('/demands/meta/states').then(resp => {
            if (resp.success) {
                demandStates = resp.data || [];
                renderQuickStatusButtons(demandId, currentStateName);
            }
        });
    } else {
        renderQuickStatusButtons(demandId, currentStateName);
    }
    
    modal.classList.add('active');
}

function renderQuickStatusButtons(demandId, currentStateName) {
    const list = document.getElementById('quickStatusButtonsList');
    list.innerHTML = demandStates.map(s => {
        const isCurrent = s.name === currentStateName;
        return `
            <button class="quick-state-option-btn ${isCurrent ? 'current' : ''}" 
                    onclick="applyQuickStatus('${demandId}', '${s.id}', '${s.href}')">
                <span class="state-dot" style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#3b82f6;margin-right:10px;"></span>
                <span style="font-weight:600;">${s.name}</span>
                ${isCurrent ? '<span style="margin-left:auto;font-size:12px;color:var(--success);font-weight:700;">● Joriy</span>' : ''}
            </button>
        `;
    }).join('');
}

async function applyQuickStatus(demandId, stateId, stateHref) {
    try {
        const resp = await apiFetch(`/demands/${demandId}/quick-status`, {
            method: 'PUT',
            body: JSON.stringify({ state_id: stateId, state_href: stateHref }),
        });
        if (resp.success) {
            closeQuickStatusModal();
            await loadDemands();
        } else {
            alert('Status o\'zgartirishda xato: ' + (resp.message || 'Xatolik'));
        }
    } catch (e) {
        alert('Xato: ' + e.message);
    }
}

function closeQuickStatusModal() {
    const modal = document.getElementById('quickStatusModal');
    if (modal) modal.classList.remove('active');
}

document.getElementById('quickStatusModal').addEventListener('click', (e) => {
    if (e.target.id === 'quickStatusModal') closeQuickStatusModal();
});

// ===== BATAFSIL MODAL =====
async function showDetail(demandId) {
    const modal = document.getElementById('detailModal');
    const modalBody = document.getElementById('modalBody');
    modal.classList.add('active');
    modalBody.innerHTML = '<div style="text-align:center;padding:40px;"><div class="loading">⏳ Yuklanmoqda...</div></div>';
    
    try {
        const response = await apiFetch(`/demands/${demandId}`);
        if (response.success) {
            const d = response.data;
            document.getElementById('modalTitle').textContent = `Sotuv: ${d.name}`;
            
            const linkedPaymentsHtml = (d.linked_payments && d.linked_payments.length > 0) ? `
                <div style="margin-top:20px;padding:14px;background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                        <h4 style="margin:0;color:var(--primary);">🔗 Bog'langan to'lov hujjatlari (Связанные документы)</h4>
                        <span style="font-size:12px;color:var(--text-light);font-weight:600;">${d.linked_payments.length} ta to'lov</span>
                    </div>
                    <div style="display:flex;flex-direction:column;gap:6px;">
                        ${d.linked_payments.map(p => {
                            let amtStr = formatMoney(p.amount);
                            if (p.is_usd && p.usd_amount) {
                                const rateText = p.usd_rate ? `, kurs: ${formatMoney(p.usd_rate)}` : '';
                                amtStr = `$${p.usd_amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${formatMoney(p.amount)}${rateText})`;
                            }
                            return `
                            <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background: var(--card);border-radius:6px;border:1px solid #e2e8f0;">
                                <div>
                                    <span class="payment-type-badge payment-${p.type}">${p.type_name}</span>
                                    <span style="font-size:12px;color:var(--text-light);margin-left:8px;">${formatDate(p.moment)}</span>
                                    ${p.purpose ? `<div style="font-size:12px;color:#64748b;margin-top:2px;">${p.purpose}</div>` : ''}
                                </div>
                                <strong style="color:var(--success);font-size:14px;">${amtStr}</strong>
                            </div>
                            `;
                        }).join('')}
                    </div>
                    <div style="display:flex;justify-content:space-between;margin-top:12px;padding-top:10px;border-top:1px dashed #cbd5e1;font-weight:700;">
                        <span>Jami to'langan summa:</span>
                        <span style="color:var(--success);font-size:15px;">${formatMoney(d.total_paid || 0)}</span>
                    </div>
                </div>
            ` : `
                <div style="margin-top:16px;padding:12px;background:#f8fafc;border-radius:8px;border:1px dashed #cbd5e1;color:#64748b;font-size:13px;text-align:center;">
                    Ushbu sotuvga bog'langan to'lov hujjati mavjud emas
                </div>
            `;

            modalBody.innerHTML = `
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));gap:12px;margin-bottom:16px;background: var(--bg);padding:12px;border-radius:8px;">
                    <div><span style="color:var(--text-light);font-size:12px;">Sana:</span><br><strong>${formatDate(d.moment)}</strong></div>
                    <div><span style="color:var(--text-light);font-size:12px;">Mijoz:</span><br><strong>${d.agent_name}</strong></div>
                    <div><span style="color:var(--text-light);font-size:12px;">Telefon:</span><br><strong>${d.agent_phone || '—'}</strong></div>
                    <div><span style="color:var(--text-light);font-size:12px;">Status:</span><br><strong style="color:${d.state_color || 'var(--primary)'};">${d.state_name || '—'}</strong></div>
                    <div><span style="color:var(--text-light);font-size:12px;">Jami Summa:</span><br><strong style="font-size:16px;color:var(--primary);">${formatMoney(d.sum)}</strong></div>
                    <div><span style="color:var(--text-light);font-size:12px;">Qolgan Qarz:</span><br><strong style="font-size:16px;color:${d.remaining > 0 ? 'var(--danger)' : 'var(--success)'};">${formatMoney(d.remaining || 0)}</strong></div>
                </div>

                <h3 style="margin-top: 20px; color: var(--primary);">📦 Tovarlar ro'yxati:</h3>
                <table class="positions-table">
                    <thead><tr><th>Kod</th><th>Tovar</th><th>Soni</th><th>Narxi</th><th>Summa</th></tr></thead>
                    <tbody>${d.positions.map(p => `
                        <tr>
                            <td><strong style="color: var(--accent);">${p.code}</strong></td>
                            <td>${p.name}</td><td>${p.quantity}</td>
                            <td>${formatMoney(p.price)}</td><td>${formatMoney(p.sum)}</td>
                        </tr>`).join('')}
                    </tbody>
                </table>
                
                ${linkedPaymentsHtml}
                
                <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px;">
                    <button class="action-btn" style="background:#15803d;color:#fff;padding:8px 16px;font-size:14px;border-radius:6px;" onclick="closeModal();printReceipt80mm('${d.id}')">🖨️ 80mm Chek</button>
                    <button class="action-btn edit-btn" style="padding:8px 16px;font-size:14px;" onclick="closeModal();showEdit('${d.id}')">✏️ Tahrirlash / To'lov</button>
                    <button class="btn-cancel" onclick="closeModal()">Yopish</button>
                </div>
            `;
        }
    } catch (error) { modalBody.innerHTML = `<div style="color:red;padding:20px;">Xato: ${error.message}</div>`; }
}

function closeModal() { document.getElementById('detailModal').classList.remove('active'); }
document.getElementById('detailModal').addEventListener('click', (e) => { if (e.target.id === 'detailModal') closeModal(); });

// ===== TAHRIRLASH MODALI =====
async function showEdit(demandId) {
    const modal = document.getElementById('editModal');
    const modalBody = document.getElementById('editModalBody');
    modal.classList.add('active');
    modalBody.innerHTML = '<div style="text-align:center;padding:30px;"><div class="loading">⏳ Yuklanmoqda...</div></div>';

    try {
        // Yagona tezkor so'rov — barcha ma'lumotlar (sotuv, tovarlar, bog'langan to'lovlar, statuslar, qarz) bir vaqtda keladi
        const demandResponse = await apiFetch(`/demands/${demandId}`);
        if (!demandResponse || !demandResponse.success || !demandResponse.data) {
            throw new Error('Sotuv ma\'lumotlari topilmadi');
        }
        
        currentEditDemand = demandResponse.data;
        if (currentEditDemand.states && currentEditDemand.states.length > 0) {
            demandStates = currentEditDemand.states;
        }
        oplataAttribute = currentEditDemand.oplata_attribute || oplataAttribute;
        
        const payments = {
            payments: currentEditDemand.linked_payments || [],
            total_paid: currentEditDemand.total_paid || 0
        };
        const currentBalance = currentEditDemand.agent_balance || 0;

        // Sozlamalar hali yuklanmagan bo'lsa 1 marta yuklash
        if (!appPaymentMethods || appPaymentMethods.length === 0) {
            await loadPaymentSettings();
        }

        renderEditForm(currentEditDemand, payments, currentBalance);
    } catch (error) {
        console.error('Tahrirlash xato:', error);
        modalBody.innerHTML = `<p style="color: red; text-align: center; padding: 20px;">Xato: ${error.message}</p>`;
    }
}

function renderEditForm(demand, paymentsData, currentBalance) {
    const modalBody = document.getElementById('editModalBody');
    document.getElementById('editModalTitle').textContent =
        `✏️ Sotuv № ${demand.name} • ${formatDate(demand.moment)}${demand.owner_name ? ` • 👤 ${demand.owner_name}` : ''}`;

    const demandSum = demand.sum;
    const totalPaid = paymentsData.total_paid || 0;
    const demandRemaining = Math.max(0, demandSum - totalPaid);

    // MoySklad demand.sum = skidka qo'llangan summa
    const rawTotalFromPositions = (demand.positions || []).reduce((acc, pos) => {
        return acc + (pos.price || 0) * (pos.quantity || 0);
    }, 0);

    let existingDiscountPercent = demand.discount || 0;
    let originalSumWithoutDiscount, existingDiscountAmount;

    if (rawTotalFromPositions > demandSum) {
        originalSumWithoutDiscount = Math.round(rawTotalFromPositions);
        existingDiscountAmount = Math.round(rawTotalFromPositions - demandSum);
        if (existingDiscountPercent === 0 && originalSumWithoutDiscount > 0) {
            existingDiscountPercent = (existingDiscountAmount / originalSumWithoutDiscount) * 100.0;
        }
    } else if (existingDiscountPercent > 0 && existingDiscountPercent < 100) {
        originalSumWithoutDiscount = Math.round(demandSum / (1 - existingDiscountPercent / 100.0));
        existingDiscountAmount = Math.round(originalSumWithoutDiscount - demandSum);
    } else {
        originalSumWithoutDiscount = Math.round(demandSum);
        existingDiscountAmount = 0;
    }

    window.deletedPositionIds = [];
    window.originalDemandSum = originalSumWithoutDiscount;
    window.existingDiscountPercent = existingDiscountPercent;
    window.existingDiscountAmount = existingDiscountAmount;
    window.initialDiscountAmount = existingDiscountAmount;
    window.initialDemandSum = demandSum;
    window.currentDiscountType = existingDiscountPercent > 0 ? 'percent' : 'sum';
    window.currentDiscountPercent = existingDiscountPercent;
    window.currentDiscountAmount = existingDiscountAmount;
    window.currentBalance = currentBalance;
    window.demandPaid = totalPaid;
    window.demandRemaining = demandRemaining;

    const stateOptions = demandStates.map(s =>
        `<option value="${s.href}" ${s.name === demand.state_name ? 'selected' : ''}>${s.name}</option>`
    ).join('');

    // To'lov usullari va hisoblarini tayyorlash
    const uzsAccounts = (appAccountsList && appAccountsList.length > 0)
        ? appAccountsList.filter(a => !a.is_dollar && a.currency !== 'USD')
        : orgAccounts;
    const dollarAccounts = (appAccountsList && appAccountsList.length > 0)
        ? appAccountsList.filter(a => a.is_dollar || a.currency === 'USD')
        : [];

    const cashMethod = appPaymentMethods.find(m => m.id === 'cash');
    const cardMethod = appPaymentMethods.find(m => m.id === 'card');
    const usdMethod = appPaymentMethods.find(m => m.id === 'usd');

    const isCashActive = cashMethod ? cashMethod.is_active : true;
    const isCardActive = cardMethod ? cardMethod.is_active : true;
    const isUsdActive = usdMethod ? usdMethod.is_active : true;

    // Card accounts filter — faqat 1 tadan ko'p bo'lsagina dropdown ko'rinadi
    const cardLinkedIds = cardMethod?.linked_account_ids || (cardMethod?.linked_account_id ? [cardMethod.linked_account_id] : []);
    const activeCardAccounts = cardLinkedIds.length > 0
        ? uzsAccounts.filter(a => cardLinkedIds.includes(a.id))
        : uzsAccounts;
    const showCardDropdown = activeCardAccounts.length > 1;
    const defaultCardAccId = activeCardAccounts[0]?.id || '';

    // Dollar accounts filter — faqat 1 tadan ko'p bo'lsagina dropdown ko'rinadi
    const usdLinkedIds = usdMethod?.linked_account_ids || (usdMethod?.linked_account_id ? [usdMethod.linked_account_id] : []);
    const activeDollarAccounts = usdLinkedIds.length > 0
        ? dollarAccounts.filter(a => usdLinkedIds.includes(a.id))
        : dollarAccounts;
    const showUsdDropdown = activeDollarAccounts.length > 1;
    const defaultUsdAccId = activeDollarAccounts[0]?.id || '';

    const cardAccountAndFullPayHtml = `
        <div class="card-account-fullpay-row" style="display:flex; justify-content:space-between; align-items:flex-end; gap:6px; margin-top:4px;">
            ${showCardDropdown ? `
            <div class="pay-input-field" style="flex:1; min-width:0;">
                <label>🏦 Bank hisobi:</label>
                <select id="paymentAccount" class="select-modern-account" style="width:100%; padding:5px 8px; border-radius:6px; font-weight:600; font-size:11.5px; border:1px solid var(--border); height:32px; box-sizing:border-box;">
                    ${activeCardAccounts.map(a => `<option value="${a.id}">${a.name || a.bankName}</option>`).join('')}
                </select>
            </div>
            ` : `<input type="hidden" id="paymentAccount" value="${defaultCardAccId}">`}
            <div style="${showCardDropdown ? '' : 'width:100%; display:flex; justify-content:flex-end;'}">
                <button type="button" class="btn-full-payment" onclick="setEditAmount('full')" title="Qolgan barcha sotuv qarzini to'lovga kiritish">
                    💯 To'liq to'lash
                </button>
            </div>
        </div>
    `;

    const usdAccountSelectHtml = showUsdDropdown
        ? `<div class="compact-pay-field" style="min-width:140px;">
               <label style="color:#166534;">🏦 Dollar hisobi</label>
               <select id="usdAccountSelect">
                   ${activeDollarAccounts.map(a => `<option value="${a.id}">💵 ${a.name}</option>`).join('')}
               </select>
           </div>`
        : `<input type="hidden" id="usdAccountSelect" value="${defaultUsdAccId}">`;

    const paymentHistory = paymentsData.payments.map(p => {
        let amtStr = formatMoney(p.amount);
        if (p.is_usd && p.usd_amount) {
            const rateText = p.usd_rate ? `, kurs: ${formatMoney(p.usd_rate)}` : '';
            amtStr = `$${p.usd_amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${formatMoney(p.amount)}${rateText})`;
        }
        return `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 10px;background: var(--card);border-radius:6px;margin-bottom:4px;border:1px solid #e2e8f0;font-size:12px;">
            <div>
                <span class="payment-type-badge payment-${p.type}">${p.type_name}</span>
                ${p.name ? `<strong style="color:var(--primary);margin-left:4px;">№${p.name}</strong>` : ''}
                <span style="font-size:11px;color:var(--text-light);margin-left:6px;">${formatDate(p.moment)}</span>
                ${p.purpose ? `<span style="font-size:11px;color:#64748b;margin-left:6px;">— ${p.purpose}</span>` : ''}
            </div>
            <strong style="color:var(--success);font-size:13px;">${amtStr}</strong>
        </div>
        `;
    }).join('');

    const isFullyPaid = demandRemaining <= 0;

    window.openCustomerProfile = function(event, customerId) {
        if (!customerId) return;
        try {
            sessionStorage.setItem('openCustomer', customerId);
        } catch (e) {}
    };

    modalBody.innerHTML = `
        <!-- YUQORI BIRLASHGAN BOSHQARUV TASMASI (Mijoz + Balans + Status + Saqlash) -->
        <div class="demand-edit-topbar">
            <div class="topbar-left">
                <!-- Mijoz nomi va yangi tabda ochish silkasi -->
                <div class="agent-info-badge">
                    <span style="font-size:11px; color:var(--text-light); text-transform:uppercase; font-weight:700;">Mijoz:</span>
                    <a href="/customers?id=${encodeURIComponent(demand.agent_id || '')}" target="_blank" class="agent-name-link" onclick="openCustomerProfile(event, '${demand.agent_id || ''}')" title="Mijoz kartochkasini ochish (yangi oyna)">
                        <span>👤</span> <strong>${demand.agent_name}</strong>
                        <span style="font-size:11px; opacity:0.75;">↗️</span>
                    </a>
                </div>
                
                <!-- Mijozning joriy umumiy balansi / qarzi -->
                <div class="customer-balance-badge ${currentBalance > 0 ? 'debt' : (currentBalance < 0 ? 'credit' : 'zero')}" title="Mijozning barcha operatsiyalar bo'yicha jami balansi">
                    <span class="badge-label">${currentBalance > 0 ? 'Qarzi:' : (currentBalance < 0 ? 'Haqi:' : 'Balans:')}</span>
                    <strong class="badge-value">${formatMoney(Math.abs(currentBalance))}</strong>
                </div>
            </div>

            <div class="topbar-right">
                <!-- Status tanlash -->
                <div class="topbar-status-box">
                    <label for="editState">📌 Status:</label>
                    <select id="editState" class="status-select-modern">
                        <option value="">— O'zgartirmaslik —</option>
                        ${stateOptions}
                    </select>
                </div>

                <!-- Saqlash tugmasi -->
                <button class="btn-save-demand" id="saveBtn" onclick="saveEdit()" title="Barcha o'zgarishlarni saqlash">
                    💾 Saqlash
                </button>
            </div>
        </div>

        <!-- ASOSIY 2 USTUNLI GRID (Main 2-Column Grid) -->
        <div class="demand-edit-grid">
            
            <!-- CHAP USTUN (~58%): 📦 TOVARLAR RO'YXATI -->
            <div class="demand-edit-left">
                <div class="positions-card">
                    <div class="positions-card-header">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span style="font-size:16px;">📦</span>
                            <strong style="font-size:14px; color:var(--primary);">Tovarlar</strong>
                            <span class="positions-count-badge"><span id="positionsCount">${demand.positions.length}</span> ta</span>
                        </div>
                        <button class="btn-add-pos" type="button" onclick="toggleAddPosition()" style="padding:4px 10px; font-size:12px;">
                            ➕ Tovar qo'shish
                        </button>
                    </div>

                    <!-- Tovar qo'shish / Qidiruv paneli -->
                    <div id="addPositionPanel" class="add-position-panel" style="display:none;">
                        <input type="text" id="assortmentSearch" placeholder="🔍 Tovar nomi, kodi yoki shtrixkodi bo'yicha yozing..." class="assortment-search-input">
                        <div id="searchResults" class="assortment-search-results"></div>
                    </div>

                    <!-- Tovarlar jadvali konteyneri (ichki mustaqil skroll bilan) -->
                    <div class="positions-table-wrapper">
                        <table class="edit-positions-table">
                            <thead>
                                <tr>
                                    <th>Tovar</th>
                                    <th style="width:75px; text-align:right;">Soni</th>
                                    <th style="width:105px; text-align:right;">Narx</th>
                                    <th style="width:110px; text-align:right;">Summa</th>
                                    <th style="width:65px; text-align:center;">Skidka</th>
                                    <th style="width:36px; text-align:center;"></th>
                                </tr>
                            </thead>
                            <tbody id="positionsBody"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- O'NG USTUN (~42%): 💰 MOLIYA VA TO'LOVLAR -->
            <div class="demand-edit-right">
                
                <!-- 1. Sotuv summasi va Skidka xulosasi -->
                <div class="demand-summary-box">
                    <div class="summary-stat-row">
                        <div class="stat-col">
                            <span class="stat-title">💰 Sotuv summasi:</span>
                            <div class="stat-val" id="saleSumDisplay">${formatMoney(demandSum)}</div>
                            ${totalPaid > 0 ? `<span class="stat-sub-paid">✅ To'langan: ${formatMoney(totalPaid)}</span>` : ''}
                        </div>
                        <div class="stat-col align-right">
                            <span class="stat-title">📋 Qolgan qarz:</span>
                            <div class="stat-val ${demandRemaining > 0 ? 'debt-color' : 'paid-color'}" id="finalSumDisplay">
                                ${isFullyPaid ? '✅ To\'langan' : formatMoney(demandRemaining)}
                            </div>
                        </div>
                    </div>

                    <!-- Skidka sozlash qatori -->
                    <div class="discount-widget">
                        <div class="discount-header">
                            <span style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-light);">🏷️ Skidka / Chegirma:</span>
                            <span id="discountSummaryText" class="discount-calc-badge" style="font-size:12px; font-weight:700; color:var(--accent);">
                                ${existingDiscountPercent > 0 ? `${existingDiscountPercent.toFixed(1)}% (${formatMoney(existingDiscountAmount)})` : '0 so\'m'}
                            </span>
                        </div>
                        <div class="discount-controls-spacious">
                            <div class="discount-toggle-group">
                                <button type="button" class="discount-toggle-btn ${window.currentDiscountType === 'percent' ? 'active' : ''}" id="btnPercent" onclick="setDiscountType('percent')">% Foiz</button>
                                <button type="button" class="discount-toggle-btn ${window.currentDiscountType === 'sum' ? 'active' : ''}" id="btnSum" onclick="setDiscountType('sum')">So'm</button>
                            </div>
                            <input type="number" id="editDiscount"
                                   value="${window.currentDiscountType === 'percent' ? existingDiscountPercent.toFixed(2) : existingDiscountAmount}"
                                   min="0" step="${window.currentDiscountType === 'percent' ? '0.5' : '1000'}"
                                   class="discount-input-spacious" placeholder="0">
                        </div>
                    </div>
                </div>

                <!-- 2. Yangi to'lov qabul qilish -->
                <div class="payment-widget-box">
                    <div class="payment-widget-header">
                        <span class="payment-widget-title">💳 Yangi to'lov qabul qilish (ixtiyoriy)</span>
                        <a href="/settings" target="_blank" class="settings-mini-link">⚙️ Sozlamalar</a>
                    </div>

                    <!-- UZS qatori: Naqd & Karta -->
                    <div class="pay-inputs-row">
                        ${isCashActive ? `
                        <div class="pay-input-field">
                            <label>💵 Naqd (so'm):</label>
                            <input type="text" inputmode="numeric" id="cashAmount" class="ghost-zero format-number" value="0" placeholder="0" oninput="updateEditPayment()">
                        </div>
                        ` : ''}
                        ${isCardActive ? `
                        <div class="pay-input-field">
                            <label>💳 Karta / Bank:</label>
                            <input type="text" inputmode="numeric" id="cardAmount" class="ghost-zero format-number" value="0" placeholder="0" oninput="updateEditPayment()">
                        </div>
                        ` : ''}
                    </div>
                    ${cardAccountAndFullPayHtml}

                    <!-- Dollar (USD) qatori -->
                    ${isUsdActive ? `
                    <div class="usd-pay-box">
                        <div class="usd-pay-header">💲 Dollar to'lov</div>
                        <div class="usd-inputs-grid">
                            <div class="pay-input-field">
                                <label>Miqdor ($):</label>
                                <input type="text" inputmode="decimal" id="usdAmount" class="ghost-zero format-number" style="height:32px; padding:5px 8px; font-size:13px;" value="0" placeholder="0" oninput="updateEditPayment()">
                            </div>
                            <div class="pay-input-field">
                                <label>📊 Kurs:</label>
                                <input type="text" inputmode="numeric" id="usdRate" class="ghost-zero format-number" style="text-align:center; padding:5px 4px; font-size:12px; height:32px;" value="${formatNumber(appReferenceRate)}" oninput="updateEditPayment()">
                            </div>
                            <div class="pay-input-field" style="min-width:0;">
                                <label>🧮 Qiymati:</label>
                                <div class="compact-usd-badge" id="usdEquivBadge">~ 0 so'm</div>
                            </div>
                        </div>
                        ${usdAccountSelectHtml}
                    </div>
                    ` : ''}

                    <!-- Hisob-kitob xulosasi -->
                    <div class="pay-calculation-bar">
                        <div class="calc-item">
                            <span>💰 Yangi to'lov:</span>
                            <strong id="editTotalPayment">0 so'm</strong>
                        </div>
                        <div class="calc-item">
                            <span>📋 Yangi sotuv qarzi:</span>
                            <strong id="editNewRemaining" class="debt">${formatMoney(demandRemaining)}</strong>
                        </div>
                        <div class="calc-item">
                            <span>👤 Yangi umumiy qarz:</span>
                            <strong id="editNewBalance" class="debt">${formatMoney(Math.max(0, currentBalance))}</strong>
                        </div>
                    </div>
                </div>

                <!-- 3. Bog'langan avvalgi to'lovlar (mavjud bo'lsa) -->
                ${paymentsData.payments.length > 0 ? `
                <div class="linked-payments-card">
                    <div class="linked-payments-header">
                        <span class="linked-payments-title">🔗 Bog'langan to'lovlar (${paymentsData.payments.length} ta)</span>
                        <strong class="linked-payments-total">Jami: ${formatMoney(totalPaid)}</strong>
                    </div>
                    <div class="linked-payments-list">
                        ${paymentHistory}
                    </div>
                </div>
                ` : ''}

            </div>
        </div>
    `;

    renderPositionsTable();

    document.getElementById('editDiscount').addEventListener('input', () => recalculateTotals(false));
    recalculateTotals(true);

    if (window.initGhostZeros) window.initGhostZeros(document.getElementById('editModal'));

    const searchInput = document.getElementById('assortmentSearch');
    if (searchInput) searchInput.addEventListener('input', debounce(searchAssortment, 350));
}

function renderPositionsTable() {
    const tbody = document.getElementById('positionsBody');
    if (!tbody || !currentEditDemand) return;

    const countEl = document.getElementById('positionsCount');
    if (countEl) countEl.textContent = currentEditDemand.positions.length;

    if (currentEditDemand.positions.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:20px;color:var(--text-light);">Hujjatda tovarlar qolmadi. "➕ Tovar qo'shish" tugmasi orqali qo'shishingiz mumkin.</td></tr>`;
        return;
    }

    const discountDisplay = (window.currentDiscountPercent && window.currentDiscountPercent > 0)
        ? `${window.currentDiscountPercent.toFixed(2)}%`
        : '—';

    tbody.innerHTML = currentEditDemand.positions.map((p, i) => `
        <tr id="posRow_${i}" class="${p.is_new ? 'new-pos-row' : ''}">
            <td>
                <strong style="color: var(--accent);">${p.code || '—'}</strong>
                ${p.is_new ? '<span class="badge-new" style="background:#e8f5e9;color:#2e7d32;font-size:10px;padding:2px 6px;border-radius:4px;margin-left:4px;">Yangi</span>' : ''}
                <br><small style="color:var(--text);">${p.name}</small>
            </td>
            <td>
                <input type="number" class="pos-qty" data-index="${i}" value="${p.quantity}" min="0.01" step="any" oninput="recalculatePosition(${i})">
            </td>
            <td>
                <input type="number" class="pos-price" data-index="${i}" value="${p.price}" min="0" step="100" oninput="recalculatePosition(${i})">
            </td>
            <td class="pos-sum" id="pos_sum_${i}">${formatNumber(p.quantity * p.price)}</td>
            <td style="text-align:center;">
                <span class="pos-discount-display" id="pos_discount_${i}">${p.discount ? p.discount.toFixed(2) + '%' : discountDisplay}</span>
            </td>
            <td style="text-align:center;">
                <button type="button" class="delete-pos-btn" onclick="deletePosition(${i})" title="O'chirish">🗑️</button>
            </td>
        </tr>
    `).join('');
}

function setDiscountType(type) {
    window.currentDiscountType = type;
    const btnSum = document.getElementById('btnSum');
    const btnPercent = document.getElementById('btnPercent');
    if (btnSum) btnSum.classList.toggle('active', type === 'sum');
    if (btnPercent) btnPercent.classList.toggle('active', type === 'percent');

    const input = document.getElementById('editDiscount');
    if (input) {
        input.step = type === 'sum' ? '1000' : '0.5';
        if (type === 'percent') {
            input.value = (window.currentDiscountPercent || 0).toFixed(2);
        } else {
            input.value = formatNumber(Math.round(window.currentDiscountAmount || 0));
        }
    }
    recalculateTotals();
}

function recalculatePosition(i) {
    if (!currentEditDemand || !currentEditDemand.positions[i]) return;
    const qtyInputs = document.querySelectorAll('.pos-qty');
    const priceInputs = document.querySelectorAll('.pos-price');

    const qty = qtyInputs[i] ? parseAmount(qtyInputs[i].value) : 0;
    const price = priceInputs[i] ? parseAmount(priceInputs[i].value) : 0;

    currentEditDemand.positions[i].quantity = qty;
    currentEditDemand.positions[i].price = price;
    currentEditDemand.positions[i].sum = qty * price;

    const sumEl = document.getElementById(`pos_sum_${i}`);
    if (sumEl) sumEl.textContent = formatMoney(qty * price);

    recalculateTotals();
}

function recalculateTotals(isInitial = false) {
    if (!currentEditDemand) return;

    const qtyInputs = document.querySelectorAll('.pos-qty');
    const priceInputs = document.querySelectorAll('.pos-price');

    let rawTotal = 0;
    for (let i = 0; i < currentEditDemand.positions.length; i++) {
        const qty = qtyInputs[i] ? parseAmount(qtyInputs[i].value) : (currentEditDemand.positions[i].quantity || 0);
        const price = priceInputs[i] ? parseAmount(priceInputs[i].value) : (currentEditDemand.positions[i].price || 0);
        rawTotal += qty * price;
    }

    const discountVal = parseAmount(document.getElementById('editDiscount')?.value);
    const discountType = window.currentDiscountType || 'sum';

    let discountAmount = 0;
    let discountPercent = 0;

    if (isInitial && window.initialDiscountAmount !== undefined) {
        discountAmount = window.initialDiscountAmount;
        discountPercent = rawTotal > 0 ? (discountAmount / rawTotal) * 100.0 : 0;
    } else if (discountType === 'percent') {
        discountPercent = Math.min(Math.max(discountVal, 0), 99.99);
        discountAmount = (rawTotal * discountPercent) / 100.0;
    } else {
        discountAmount = Math.min(Math.max(discountVal, 0), rawTotal);
        discountPercent = rawTotal > 0 ? (discountAmount / rawTotal) * 100.0 : 0;
    }

    const finalSum = (isInitial && window.initialDemandSum !== undefined)
        ? window.initialDemandSum
        : Math.max(0, Math.round(rawTotal - discountAmount));
    const paid = window.demandPaid || 0;
    const remaining = Math.max(0, finalSum - paid);

    window.currentDiscountPercent = discountPercent;
    window.currentDiscountAmount = discountAmount;
    window.currentDemandSum = finalSum;
    window.demandRemaining = remaining;

    // Sotuv summasi ko'rinishi
    const saleEl = document.getElementById('saleSumDisplay');
    if (saleEl) {
        if (discountAmount > 0) {
            saleEl.innerHTML = `
                <div style="text-decoration:line-through; color:#94a3b8; font-size:12px; font-weight:600; line-height:1.2;">${formatMoney(rawTotal)}</div>
                <div style="font-size:17px; font-weight:800; color:var(--text); line-height:1.2;">${formatMoney(finalSum)}</div>
            `;
        } else {
            saleEl.textContent = formatMoney(rawTotal);
        }
    }

    // Skidka info
    const percentEl = document.getElementById('discountSummaryPercent');
    const amountEl = document.getElementById('discountSummaryAmount');
    const textEl = document.getElementById('discountSummaryText');
    if (percentEl) percentEl.textContent = discountPercent.toFixed(2) + '%';
    if (amountEl) amountEl.textContent = formatMoney(Math.round(discountAmount)) + ' so\'m';
    if (textEl) {
        if (discountAmount > 0) {
            textEl.textContent = `${discountPercent.toFixed(1)}% (${formatMoney(Math.round(discountAmount))})`;
        } else {
            textEl.textContent = '0 so\'m';
        }
    }

    // Qolgan qarz ko'rinishi
    const finalEl = document.getElementById('finalSumDisplay');
    if (finalEl) {
        if (remaining <= 0) {
            finalEl.textContent = '✅ To\'langan';
            finalEl.className = 'sum-col-value paid-color';
        } else {
            finalEl.textContent = formatMoney(remaining);
            finalEl.className = 'sum-col-value debt-color';
        }
    }

    // Jadvaldagi har bir pozitsiya skidkasini yangilash
    document.querySelectorAll('[id^="pos_discount_"]').forEach(el => {
        el.textContent = discountPercent > 0 ? `${discountPercent.toFixed(2)}%` : '—';
    });

    updateEditPayment();
}

function updateEditPayment() {
    const cashEl = document.getElementById('cashAmount');
    const cardEl = document.getElementById('cardAmount');
    const usdAmountEl = document.getElementById('usdAmount');
    const usdRateEl = document.getElementById('usdRate');
    const usdBadgeEl = document.getElementById('usdEquivBadge');

    const cash = cashEl ? parseAmount(cashEl.value) : 0;
    const card = cardEl ? parseAmount(cardEl.value) : 0;
    const usdAmount = usdAmountEl ? parseAmount(usdAmountEl.value) : 0;
    const usdRate = usdRateEl ? (parseAmount(usdRateEl.value) || appReferenceRate) : appReferenceRate;

    const usdEquivalentUZS = Math.round(usdAmount * usdRate);
    if (usdBadgeEl) {
        usdBadgeEl.textContent = `~ ${formatMoney(usdEquivalentUZS)}`;
    }

    const totalPaymentUZS = cash + card + usdEquivalentUZS;

    const remaining = window.demandRemaining || 0;
    const currentBalance = window.currentBalance || 0;
    const initialDiscount = window.initialDiscountAmount || 0;
    const currentDiscount = window.currentDiscountAmount || 0;
    const extraDiscount = Math.max(0, currentDiscount - initialDiscount);

    const newDemandRemaining = Math.max(0, remaining - totalPaymentUZS);
    const newBalance = Math.max(0, currentBalance - totalPaymentUZS - extraDiscount);

    const totalEl = document.getElementById('editTotalPayment');
    const remainEl = document.getElementById('editNewRemaining');
    const balanceEl = document.getElementById('editNewBalance');

    if (totalEl) {
        if (usdAmount > 0) {
            totalEl.innerHTML = `${formatMoney(totalPaymentUZS)} <span style="color:#15803d;font-size:12px;font-weight:600;">($${usdAmount} @ ${formatMoney(usdRate)})</span>`;
        } else {
            totalEl.textContent = formatMoney(totalPaymentUZS);
        }
    }
    if (remainEl) remainEl.textContent = formatMoney(newDemandRemaining);
    if (balanceEl) balanceEl.textContent = formatMoney(newBalance);
}

function setEditAmount(type) {
    const remaining = window.demandRemaining || 0;
    if (type === 'full') {
        const cashEl = document.getElementById('cashAmount');
        const cardEl = document.getElementById('cardAmount');
        const usdEl = document.getElementById('usdAmount');
        if (cashEl) {
            cashEl.value = formatNumber(Math.round(remaining));
            if (cardEl) cardEl.value = '';
        } else if (cardEl) {
            cardEl.value = formatNumber(Math.round(remaining));
        }
        if (usdEl) usdEl.value = '';
    }
    updateEditPayment();
}

function toggleAddPosition() {
    const panel = document.getElementById('addPositionPanel');
    if (!panel) return;
    const isHidden = panel.style.display === 'none';
    panel.style.display = isHidden ? 'block' : 'none';
    if (isHidden) {
        const input = document.getElementById('assortmentSearch');
        if (input) {
            input.value = '';
            input.focus();
        }
        document.getElementById('searchResults').innerHTML = '';
    }
}

async function searchAssortment() {
    const query = document.getElementById('assortmentSearch').value.trim();
    const resultsDiv = document.getElementById('searchResults');
    if (!resultsDiv) return;

    if (query.length < 2) {
        resultsDiv.innerHTML = '<div style="padding:8px;color:var(--text-light);">Kamida 2 ta belgi kiriting...</div>';
        return;
    }

    try {
        resultsDiv.innerHTML = '<div style="padding:8px;color:var(--text-light);">🔍 Qidirilmoqda...</div>';
        const response = await apiFetch(`/demands/search/assortment?query=${encodeURIComponent(query)}`);

        if (response.success && response.data && response.data.length > 0) {
            resultsDiv.innerHTML = response.data.map(item => `
                <div class="search-result-item" onclick="onSelectProduct('${item.id}', '${(item.name || '').replace(/'/g, "\\'")}', '${item.code || ''}', ${item.price || 0})" style="padding:8px 12px;border-bottom:1px solid #eee;cursor:pointer;display:flex;justify-content:space-between;align-items:center;transition:background 0.2s;">
                    <div>
                        <strong style="color:var(--accent);">${item.code || '—'}</strong>
                        <div style="font-size:13px;font-weight:600;">${item.name}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-weight:700;color:var(--primary);">${formatMoney(item.price)}</div>
                        <small style="color:var(--success);">Omborda: ${item.quantity || 0} ta</small>
                    </div>
                </div>
            `).join('');
        } else {
            resultsDiv.innerHTML = '<div style="padding:8px;color:var(--text-light);">❌ Tovar topilmadi</div>';
        }
    } catch (error) {
        console.error('Assortment qidiruv xatosi:', error);
        resultsDiv.innerHTML = '<div style="padding:8px;color:red;">Qidiruvda xato yuz berdi</div>';
    }
}

function onSelectProduct(assortmentId, name, code, price) {
    if (!currentEditDemand) return;

    const newPosition = {
        position_id: null,
        assortment_id: assortmentId,
        code: code || '—',
        name: name,
        quantity: 1,
        price: price || 0,
        sum: price || 0,
        discount: window.currentDiscountPercent || 0,
        original_price: price || 0,
        is_new: true,
    };

    currentEditDemand.positions.push(newPosition);
    renderPositionsTable();
    recalculateTotals();

    const resultsDiv = document.getElementById('searchResults');
    if (resultsDiv) {
        resultsDiv.innerHTML = `<div style="padding:8px;color:var(--success);font-weight:600;">✅ "${name}" jadvalga qo'shildi!</div>`;
    }
}

function deletePosition(index) {
    if (!currentEditDemand || !currentEditDemand.positions[index]) return;

    const pos = currentEditDemand.positions[index];
    if (!confirm(`"${pos.name}" tovarini ro'yxatdan o'chirishni tasdiqlaysizmi?`)) return;

    if (pos.position_id) {
        if (!window.deletedPositionIds) window.deletedPositionIds = [];
        window.deletedPositionIds.push(pos.position_id);
    }

    currentEditDemand.positions.splice(index, 1);
    renderPositionsTable();
    recalculateTotals();
}

async function saveEdit() {
    if (!currentEditDemand) return;

    const saveBtn = document.getElementById('saveBtn');
    saveBtn.disabled = true;
    saveBtn.textContent = '⏳ Saqlanmoqda...';

    try {
        const demandId = currentEditDemand.id;
        const discountType = window.currentDiscountType || 'sum';
        const rawDiscountInput = parseAmount(document.getElementById('editDiscount')?.value);
        let discountValue = rawDiscountInput;
        if (discountType === 'percent') {
            discountValue = Math.floor(rawDiscountInput * 1000000) / 1000000;
        } else {
            discountValue = Math.round(rawDiscountInput);
        }
        const stateHref = document.getElementById('editState')?.value || null;

        const cashEl = document.getElementById('cashAmount');
        const cardEl = document.getElementById('cardAmount');
        const cashAmount = cashEl ? parseAmount(cashEl.value) : 0;
        const cardAmount = cardEl ? parseAmount(cardEl.value) : 0;
        const accountEl = document.getElementById('paymentAccount');
        const accountId = accountEl ? accountEl.value : null;

        const usdAmountEl = document.getElementById('usdAmount');
        const usdRateEl = document.getElementById('usdRate');
        const usdAccountEl = document.getElementById('usdAccountSelect');
        const usdAmount = usdAmountEl ? parseAmount(usdAmountEl.value) : 0;
        const usdRate = usdRateEl ? parseAmount(usdRateEl.value) : 0;
        const usdAccountId = usdAccountEl ? usdAccountEl.value : null;

        // Jadvaldagi joriy qiymatlar
        const qtyInputs = document.querySelectorAll('.pos-qty');
        const priceInputs = document.querySelectorAll('.pos-price');

        const positionsToUpdate = [];
        const addedPositions = [];

        currentEditDemand.positions.forEach((pos, i) => {
            const q = qtyInputs[i] ? parseAmount(qtyInputs[i].value) : pos.quantity;
            const p = priceInputs[i] ? parseAmount(priceInputs[i].value) : pos.price;

            if (pos.is_new) {
                addedPositions.push({
                    assortment_id: pos.assortment_id,
                    quantity: q,
                    price: p,
                });
            } else {
                positionsToUpdate.push({
                    position_id: pos.position_id,
                    quantity: q,
                    price: p,
                });
            }
        });

        const payload = {
            discount_type: discountType,
            discount_value: discountValue,
            state_href: stateHref,
            positions: positionsToUpdate,
            added_positions: addedPositions.length > 0 ? addedPositions : null,
            deleted_positions: (window.deletedPositionIds && window.deletedPositionIds.length > 0) ? window.deletedPositionIds : null,
            cash_amount: cashAmount,
            card_amount: cardAmount,
            account_id: accountId || null,
            usd_amount: usdAmount,
            usd_rate: usdRate,
            usd_account_id: usdAccountId || null,
            update_payment_attribute: !!(oplataAttribute && oplataAttribute.id),
        };

        const response = await apiFetch(`/demands/${demandId}`, {
            method: 'PUT',
            body: JSON.stringify(payload),
        });

        if (response && response.success) {
            alert('✅ Sotuv muvaffaqiyatli saqlandi!');
            closeEditModal();
            await loadDemands();
        } else {
            throw new Error((response && (response.detail || response.message)) || 'Saqlashda xatolik yuz berdi');
        }
    } catch (error) {
        console.error('Saqlash xatosi:', error);
        alert('❌ Xato: ' + error.message);
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = '💾 Saqlash';
    }
}

function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
    currentEditDemand = null;
    window.deletedPositionIds = [];
}

document.getElementById('editModal').addEventListener('click', (e) => {
    if (e.target.id === 'editModal') closeEditModal();
});

// Enter tugmasi bosilganda keyingi inputga o'tish (tovar narxi, soni, va to'lovlar uchun)
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.tagName === 'INPUT') {
        const target = e.target;
        
        // Sotuvni tahrirlash: narx yoki soni
        if (target.classList.contains('pos-price') || target.classList.contains('pos-qty')) {
            e.preventDefault();
            const isPrice = target.classList.contains('pos-price');
            const currentIndex = parseInt(target.getAttribute('data-index') || '0', 10);
            const nextInput = document.querySelector(`input.${isPrice ? 'pos-price' : 'pos-qty'}[data-index="${currentIndex + 1}"]`);
            if (nextInput) {
                nextInput.focus();
                nextInput.select();
            }
        }
        // To'lovlar oynasida navbatma-navbat o'tish (ghost-zero classli to'lov summalari)
        else if (target.classList.contains('ghost-zero')) {
            e.preventDefault();
            const paymentInputs = Array.from(document.querySelectorAll('.modal.active .ghost-zero')).filter(el => el.offsetParent !== null);
            const idx = paymentInputs.indexOf(target);
            if (idx !== -1 && idx < paymentInputs.length - 1) {
                paymentInputs[idx + 1].focus();
                paymentInputs[idx + 1].select();
            }
        }
        // Shtrixkod skaneri uchun (Tovar qo'shish)
        else if (target.id === 'assortmentSearch') {
            e.preventDefault();
            const query = target.value.trim();
            if (query.length < 2) return;
            
            const resultsDiv = document.getElementById('searchResults');
            if (resultsDiv) resultsDiv.innerHTML = '<div style="padding:8px;color:var(--text-light);">🔍 Skaner qilinmoqda...</div>';
            
            apiFetch(`/demands/search/assortment?query=${encodeURIComponent(query)}`).then(response => {
                if (response.success && response.data && response.data.length > 0) {
                    const item = response.data[0];
                    onSelectProduct(item.id, (item.name || '').replace(/'/g, "\\'"), item.code || '', item.price || 0);
                    
                    target.value = '';
                    if (resultsDiv) {
                        resultsDiv.innerHTML = `<div style="padding:8px;color:var(--success);font-weight:600;">✅ "${item.name}" qatorga qo'shildi!</div>`;
                    }
                    
                    setTimeout(() => {
                        const qtyInputs = document.querySelectorAll('.pos-qty');
                        if (qtyInputs.length > 0) {
                            const lastQty = qtyInputs[qtyInputs.length - 1];
                            lastQty.focus();
                            lastQty.select();
                        }
                    }, 50);
                } else {
                    if (resultsDiv) resultsDiv.innerHTML = '<div style="padding:8px;color:red;">❌ Tovar topilmadi</div>';
                }
            }).catch(err => {
                console.error(err);
                if (resultsDiv) resultsDiv.innerHTML = '<div style="padding:8px;color:red;">Xato yuz berdi</div>';
            });
        }
    }
});

// ===== SOTUVLAR RO'YXATINI CHOP ETISH (PRINT) =====
function togglePrintDropdown(btnEl) {
    const dropdown = btnEl?.nextElementSibling || document.getElementById('demandsPrintDropdown');
    if (dropdown) dropdown.classList.toggle('show');
}

// Dropdown tashqarisiga bosilganda yopish
document.addEventListener('click', (e) => {
    if (!e.target.closest('.print-dropdown-wrapper')) {
        document.querySelectorAll('.print-dropdown-menu.show').forEach(d => d.classList.remove('show'));
    }
});

async function printDemandsList(format = 'a4') {
    // Dropdownni yopish
    document.querySelectorAll('.print-dropdown-menu.show').forEach(d => d.classList.remove('show'));

    const printArea = document.getElementById('genericPrintArea');
    if (!printArea) return;

    // Print format classini body ga qo'shish
    document.body.classList.remove('print-a4', 'print-a5');
    document.body.classList.add(`print-${format}`);

    const dateFrom = document.getElementById('dateFrom')?.value;
    const dateTo = document.getElementById('dateTo')?.value;
    const searchVal = document.getElementById('searchInput')?.value;
    const nowStr = new Date().toLocaleString('uz-UZ', { year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit' });

    let periodTitle = 'Barcha davr sotuvlari';
    if (dateFrom && dateTo) {
        if (dateFrom === dateTo) periodTitle = `${dateFrom} sanasidagi sotuvlar reyestri`;
        else periodTitle = `${dateFrom} — ${dateTo} davridagi sotuvlar reyestri`;
    }
    if (searchVal) periodTitle += ` (Qidiruv: "${searchVal}")`;

    const listToPrint = currentLoadedDemands || [];

    const totalSalesCount = listToPrint.length;
    const totalSalesSum = listToPrint.reduce((acc, d) => acc + (d.sum || 0), 0);
    const totalPaidSum = listToPrint.reduce((acc, d) => acc + (d.payedSum || 0), 0);
    const totalRemainingDebt = totalSalesSum - totalPaidSum;

    const isA5 = format === 'a5';
    const fontSize = isA5 ? 'font-size:10px;' : '';
    const thPad = isA5 ? 'padding:4px 6px;' : '';
    const tdPad = isA5 ? 'padding:3px 6px;' : '';

    let rowsHtml = '';
    listToPrint.forEach((d, idx) => {
        const remaining = (d.sum || 0) - (d.payedSum || 0);
        let paymentStatus = 'To\'lanmagan';
        let statusColor = '#b91c1c';
        if (d.payedSum >= d.sum && d.sum > 0) {
            paymentStatus = 'To\'liq to\'langan';
            statusColor = '#15803d';
        } else if (d.payedSum > 0) {
            paymentStatus = `Qisman: ${formatMoney(d.payedSum)}`;
            statusColor = '#d97706';
        }

        const momentFormatted = d.moment ? d.moment.substring(0, 16) : '—';

        rowsHtml += `
            <tr>
                <td style="text-align:center;width:30px;${tdPad}">${idx + 1}</td>
                <td style="font-weight:700;${tdPad}">${d.name || '—'}</td>
                <td style="${tdPad}">${momentFormatted}</td>
                <td style="font-weight:600;${tdPad}">${d.customer || d.agent_name || '—'}</td>
                <td style="text-align:right;font-weight:700;${tdPad}">${formatMoney(d.sum)}</td>
                <td style="text-align:center;font-weight:600;color:${statusColor};${isA5 ? 'font-size:9px;' : 'font-size:11px;'}${tdPad}">
                    ${paymentStatus}
                </td>
                <td style="text-align:right;font-weight:700;color:${remaining > 0 ? '#b91c1c' : '#15803d'};${tdPad}">
                    ${remaining > 0 ? formatMoney(remaining) : '0 so\'m'}
                </td>
            </tr>
        `;
    });

    printArea.innerHTML = `
        <div class="print-report-header" style="${isA5 ? 'padding:8px 12px;' : ''}">
            <div>
                <div class="print-report-title" style="${isA5 ? 'font-size:14px;' : ''}">📦 ${periodTitle}</div>
                <div class="print-report-subtitle" style="${isA5 ? 'font-size:10px;' : ''}">Tashkilot: <strong>${currentOrgName}</strong> | Chop etilgan vaqt: ${nowStr}</div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:${isA5 ? '10px' : '12px'};font-weight:700;color:#64748b;">Azer tizimi${isA5 ? ' (A5)' : ''}</div>
            </div>
        </div>

        <div class="print-summary-box" style="${isA5 ? 'padding:6px 10px;gap:10px;' : ''}">
            <div class="print-summary-item">
                <div class="print-summary-label">Sotuvlar Soni</div>
                <div class="print-summary-value" style="${isA5 ? 'font-size:14px;' : ''}">${totalSalesCount} ta</div>
            </div>
            <div class="print-summary-item">
                <div class="print-summary-label">Jami Sotuv Summasi</div>
                <div class="print-summary-value" style="color:#1e3a8a;${isA5 ? 'font-size:14px;' : ''}">${formatMoney(totalSalesSum)}</div>
            </div>
            <div class="print-summary-item">
                <div class="print-summary-label">Jami To'langan</div>
                <div class="print-summary-value" style="color:#15803d;${isA5 ? 'font-size:14px;' : ''}">${formatMoney(totalPaidSum)}</div>
            </div>
            <div class="print-summary-item">
                <div class="print-summary-label">Qolgan Qarz</div>
                <div class="print-summary-value" style="color:#b91c1c;${isA5 ? 'font-size:14px;' : ''}">${formatMoney(totalRemainingDebt)}</div>
            </div>
        </div>

        <table class="print-table" style="${fontSize}">
            <thead>
                <tr>
                    <th style="text-align:center;width:30px;${thPad}">№</th>
                    <th style="${thPad}">Sotuv №</th>
                    <th style="${thPad}">Sana</th>
                    <th style="${thPad}">Mijoz (Kontragent)</th>
                    <th style="text-align:right;${thPad}">Summa</th>
                    <th style="text-align:center;${thPad}">To'lov holati</th>
                    <th style="text-align:right;${thPad}">Qolgan Qarz</th>
                </tr>
            </thead>
            <tbody>
                ${rowsHtml || '<tr><td colspan="7" style="text-align:center;">Sotuvlar topilmadi</td></tr>'}
            </tbody>
        </table>

        <div class="print-signatures" style="${isA5 ? 'margin-top:12px;gap:20px;font-size:11px;' : ''}">
            <div>
                <div>Hisobotni tuzdi: ____________________</div>
                <div style="font-size:10px;color:#64748b;margin-top:4px;">(imzo va F.I.SH)</div>
            </div>
            <div>
                <div>Tasdiqladi (Rahbar): ____________________</div>
                <div style="font-size:10px;color:#64748b;margin-top:4px;">(imzo va muhr)</div>
            </div>
        </div>
    `;

    window.print();
}

// ===== 80MM XPRINTER CHEK CHOP ETISH & SOZLAMALARI =====
const DEFAULT_RECEIPT_SETTINGS = {
    storeName: "MODERN MEN'S WEAR",
    slogan: "Erkaklar kiyimlarining ulgurji savdosi",
    phones: "+998 90 123-45-67",
    address: "Toshkent sh., Abu Saxiy bozori",
    footerNote: "Xaridingiz uchun rahmat! Sotilgan tovarlar 3 kun ichida chek bilan almashtiriladi.",
    fontSize: "large"
};

function getReceiptSettings() {
    try {
        const saved = localStorage.getItem('moysklad_receipt_settings');
        if (saved) return JSON.parse(saved);
    } catch (e) {}
    return { ...DEFAULT_RECEIPT_SETTINGS };
}

function openReceiptSettingsModal() {
    const s = getReceiptSettings();
    document.getElementById('rcpt_store_name').value = s.storeName || '';
    document.getElementById('rcpt_slogan').value = s.slogan || '';
    document.getElementById('rcpt_phones').value = s.phones || '';
    document.getElementById('rcpt_address').value = s.address || '';
    document.getElementById('rcpt_footer_note').value = s.footerNote || '';
    document.getElementById('rcpt_font_size').value = s.fontSize || 'large';
    document.getElementById('receiptSettingsModal').classList.add('active');
}

function closeReceiptSettingsModal() {
    document.getElementById('receiptSettingsModal').classList.remove('active');
}

function saveReceiptSettings() {
    const s = {
        storeName: document.getElementById('rcpt_store_name').value.trim() || DEFAULT_RECEIPT_SETTINGS.storeName,
        slogan: document.getElementById('rcpt_slogan').value.trim(),
        phones: document.getElementById('rcpt_phones').value.trim(),
        address: document.getElementById('rcpt_address').value.trim(),
        footerNote: document.getElementById('rcpt_footer_note').value.trim(),
        fontSize: document.getElementById('rcpt_font_size').value || 'large',
    };
    localStorage.setItem('moysklad_receipt_settings', JSON.stringify(s));
    alert('✅ Chek sozlamalari muvaffaqiyatli saqlandi!');
    closeReceiptSettingsModal();
}

async function printReceipt80mm(demandId) {
    const previewModal = document.getElementById('receiptPreviewModal');
    const previewCard = document.getElementById('receiptPreviewCard');
    previewModal.classList.add('active');
    previewCard.innerHTML = '<div style="text-align:center;padding:30px;"><div class="loading">⏳ Chek tayyorlanmoqda...</div></div>';

    try {
        const resp = await apiFetch(`/demands/${demandId}`);
        if (!resp.success || !resp.data) throw new Error('Sotuv ma\'lumotlarini olib bo\'lmadi');
        const d = resp.data;

        let customerBalance = 0;
        if (d.agent_id) {
            try {
                const balResp = await apiFetch(`/payments/balance/${d.agent_id}`);
                if (balResp.success && balResp.data) {
                    customerBalance = parseFloat(balResp.data.balance) || 0;
                }
            } catch (e) {}
        }

        const settings = getReceiptSettings();
        const receiptHtml = buildReceiptHtml(d, customerBalance, settings);

        previewCard.innerHTML = receiptHtml;
        document.getElementById('receiptPrintArea').innerHTML = receiptHtml;
    } catch (e) {
        previewCard.innerHTML = `<div style="color:red;padding:20px;text-align:center;">Xatolik: ${e.message}</div>`;
    }
}

function buildReceiptHtml(demand, currentCustomerDebt, settings) {
    const totalSum = demand.sum || 0;
    const paidSum = demand.total_paid || 0;
    const remainingSum = Math.max(0, totalSum - paidSum);
    const discountPercent = demand.discount || 0;

    let totalQuantity = 0;
    let totalOriginalSum = 0;
    let totalPositionsDiscountSum = 0;

    const positionsRows = (demand.positions || []).map((p, idx) => {
        const qty = parseFloat(p.quantity) || 0;
        totalQuantity += qty;

        // Baza narx (original katalog narxi)
        let origUnitPrice = parseFloat(p.original_price) || parseFloat(p.price) || 0;
        const currentSum = parseFloat(p.sum) || (qty * origUnitPrice);
        let itemDiscountPct = parseFloat(p.discount) || 0;
        let itemDiscountAmt = parseFloat(p.discount_amount) || 0;

        // Agar butun hujjatda umumiy chegirma bo'lsa va tovarda 0 bo'lsa
        if (itemDiscountPct === 0 && discountPercent > 0) {
            itemDiscountPct = discountPercent;
        }

        // Chegirmali birlik narxi
        let finalUnitPrice = parseFloat(p.discounted_price) || 0;
        if (finalUnitPrice <= 0 || finalUnitPrice === origUnitPrice) {
            if (itemDiscountPct > 0 && itemDiscountPct < 100) {
                finalUnitPrice = origUnitPrice * (1 - itemDiscountPct / 100.0);
            } else if (qty > 0 && currentSum < (origUnitPrice * qty)) {
                finalUnitPrice = currentSum / qty;
            } else {
                finalUnitPrice = origUnitPrice;
            }
        }

        const origTotalSum = origUnitPrice * qty;
        // Faqat haqiqatdan ham narx pasaytirilgan bo'lsa skidka hisoblanadi
        const hasItemDiscount = (origUnitPrice - finalUnitPrice) > 0.5;

        const finalItemSum = hasItemDiscount ? Math.round(finalUnitPrice * qty) : currentSum;

        if (hasItemDiscount) {
            if (itemDiscountAmt <= 0) itemDiscountAmt = Math.max(0, origTotalSum - finalItemSum);
            if (itemDiscountPct <= 0 && origTotalSum > 0) itemDiscountPct = ((origUnitPrice - finalUnitPrice) / origUnitPrice) * 100.0;
            totalPositionsDiscountSum += itemDiscountAmt;
            totalOriginalSum += origTotalSum;
        } else {
            totalOriginalSum += currentSum;
        }

        const pctFormatted = (itemDiscountPct % 1 === 0 ? itemDiscountPct : itemDiscountPct.toFixed(1)) + '%';

        return `
        <tr class="receipt-item-row">
            <td colspan="2" class="receipt-item-cell">
                <div class="receipt-item-title">
                    <span class="receipt-item-idx">${idx + 1}.</span> ${p.code && p.code !== '—' ? `<span class="receipt-item-code">[${p.code}]</span> ` : ''}${p.name}
                </div>
                <div class="receipt-item-calc-row">
                    <div class="receipt-item-math">
                        ${hasItemDiscount ? `
                            <strong class="calc-qty">${formatNumber(qty)}</strong> * <strike class="calc-old-price">${formatNumber(origUnitPrice)}</strike> ➔ <strong class="calc-new-price">${formatNumber(finalUnitPrice)}</strong> <strong class="calc-disc-percent">(-${pctFormatted})</strong>
                        ` : `
                            <strong class="calc-qty">${formatNumber(qty)}</strong> * <strong class="calc-new-price">${formatNumber(origUnitPrice)}</strong>
                        `}
                    </div>
                    <div class="receipt-item-total">
                        <strong class="receipt-item-sum-value">${formatMoney(finalItemSum)}</strong>
                    </div>
                </div>
            </td>
        </tr>
        `;
    }).join('');

    const totalPositionsCount = (demand.positions || []).length;

    // Asl tovarlar summasi (skidkasiz)
    let sumWithoutDiscount = totalSum;
    let discountAmount = 0;
    if (discountPercent > 0 && discountPercent < 100) {
        sumWithoutDiscount = totalSum / (1 - discountPercent / 100.0);
        discountAmount = sumWithoutDiscount - totalSum;
    } else if (totalPositionsDiscountSum > 0) {
        discountAmount = totalPositionsDiscountSum;
        sumWithoutDiscount = totalSum + totalPositionsDiscountSum;
    }

    // Oldingi qarzni hisoblash:
    const previousDebt = Math.max(0, currentCustomerDebt + paidSum - totalSum);
    const newTotalDebt = Math.max(0, previousDebt + totalSum - paidSum);

    return `
        <div class="receipt-80mm font-${settings.fontSize || 'large'}">
            <div class="receipt-header">
                <div class="receipt-store-title">${settings.storeName || "MODERN MEN'S WEAR"}</div>
                ${settings.slogan ? `<div class="receipt-store-slogan">${settings.slogan}</div>` : ''}
                ${settings.phones ? `<div class="receipt-store-contact">📞 ${settings.phones}</div>` : ''}
                ${settings.address ? `<div class="receipt-store-contact">📍 ${settings.address}</div>` : ''}
            </div>

            <div class="receipt-meta-box">
                <div class="receipt-meta-row">
                    <span class="meta-label">Sotuv (Chek) №:</span>
                    <span class="meta-value doc-num">${demand.name}</span>
                </div>
                <div class="receipt-meta-row">
                    <span class="meta-label">Sana / Vaqt:</span>
                    <span class="meta-value">${formatDate(demand.moment)}</span>
                </div>
                <div class="receipt-meta-row">
                    <span class="meta-label">Xaridor:</span>
                    <span class="meta-value customer-name">${demand.agent_name || "—"}</span>
                </div>
                ${demand.owner_name ? `
                <div class="receipt-meta-row">
                    <span class="meta-label">Sotuvchi:</span>
                    <span class="meta-value">${demand.owner_name}</span>
                </div>` : ''}
                ${demand.agent_phone ? `
                <div class="receipt-meta-row">
                    <span class="meta-label">Mijoz tel:</span>
                    <span class="meta-value">${demand.agent_phone}</span>
                </div>` : ''}
            </div>

            <table class="receipt-table">
                <thead>
                    <tr>
                        <th style="text-align:left;">№ Tovar va Hisobi</th>
                        <th class="col-r" style="text-align:right; width:110px;">Summa</th>
                    </tr>
                </thead>
                <tbody>
                    ${positionsRows || '<tr><td colspan="2" style="text-align:center;padding:10px;">Tovarlar mavjud emas</td></tr>'}
                </tbody>
            </table>

            <div class="receipt-divider"></div>

            <!-- Chek oxirida umumiy tovar soni -->
            <div class="receipt-summary-qty-box">
                <div class="receipt-total-row" style="justify-content: center; font-size: 13px; gap: 10px; margin: 0;">
                    <span>Jami tovar: <strong>${formatNumber(totalQuantity)} ta</strong>,</span>
                    <span>Pozitsiya: <strong>${totalPositionsCount} ta</strong></span>
                </div>
            </div>

            <div class="receipt-divider"></div>

            <div class="receipt-totals">
                ${(discountAmount > 0 || discountPercent > 0) ? `
                <div class="receipt-total-row">
                    <span>Jami summasi:</span>
                    <span>${formatMoney(sumWithoutDiscount)}</span>
                </div>
                <div class="receipt-total-row discount-row">
                    <span>Chegirma (${discountPercent > 0 ? discountPercent.toFixed(1) + '%' : 'tovarlar bo\'yicha'}):</span>
                    <span>- ${formatMoney(discountAmount)}</span>
                </div>` : ''}

                <div class="receipt-total-row grand-total">
                    <span>TO'LOV:</span>
                    <span>${formatMoney(totalSum)}</span>
                </div>

                <div class="receipt-total-row paid-row">
                    <span>To'landi:</span>
                    <strong>${formatMoney(paidSum)}</strong>
                </div>

                ${remainingSum > 0 ? `
                <div class="receipt-total-row debt-row">
                    <span>Ushbu sotuvdan qarz:</span>
                    <strong>${formatMoney(remainingSum)}</strong>
                </div>` : ''}
            </div>

            <!-- Qarz hisob-kitob kartochkasi -->
            <div class="receipt-debt-card">
                <div class="debt-title">⚖️ O'ZARO HISOB-KITOB BALANSI</div>
                <div class="receipt-total-row">
                    <span>Oldingi qarzdorlik:</span>
                    <span>${formatMoney(previousDebt)}</span>
                </div>
                <div class="receipt-total-row">
                    <span>+ Ushbu xarid summasi:</span>
                    <span>${formatMoney(totalSum)}</span>
                </div>
                <div class="receipt-total-row">
                    <span>- Qabul qilingan to'lov:</span>
                    <span>${formatMoney(paidSum)}</span>
                </div>
                <div class="receipt-debt-divider"></div>
                <div class="receipt-total-row debt-final-row">
                    <span>YANGI QARZ:</span>
                    <span>${formatMoney(newTotalDebt)}</span>
                </div>
            </div>

            <div class="receipt-footer">
                ${settings.footerNote ? `<div class="footer-note">${settings.footerNote}</div>` : '<div class="footer-note">Xaridingiz uchun rahmat!</div>'}
            </div>
        </div>
    `;
}

function executeReceiptPrint() {
    // 80mm chek uzayib ketsa o'rtasidan kesilmasligi uchun @page size'ni auto qilib beramiz
    const style = document.createElement('style');
    style.id = 'print-80mm-style';
    style.innerHTML = `@media print { 
        @page { size: 76mm auto; margin: 0; } 
        body { margin: 0; padding: 0; }
        .receipt-80mm { page-break-inside: avoid; }
    }`;
    document.head.appendChild(style);
    
    window.onafterprint = function() {
        const s = document.getElementById('print-80mm-style');
        if (s) s.remove();
        window.onafterprint = null;
    };
    
    window.print();
}

function closeReceiptPreviewModal() {
    document.getElementById('receiptPreviewModal').classList.remove('active');
}

document.getElementById('receiptPreviewModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'receiptPreviewModal') closeReceiptPreviewModal();
});
document.getElementById('receiptSettingsModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'receiptSettingsModal') closeReceiptSettingsModal();
});