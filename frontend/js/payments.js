// frontend/js/payments.js - Said Baraka Kassa & Valyuta Moduli

// ===== GLOBAL O'ZGARUVCHILAR =====
let currentPeriod = 'today'; // Standart davr: 'today' (Bugun - tezkor ochiladi)
let currentTypeFilter = 'all';
let currentAccountId = 'all';
let currentExpenseItemId = '';
let currentCashflowData = null;
let expenseItems = [];
let orgAccounts = [];
let customersList = [];
let selectedExpenseType = 'cash'; // 'cash' yoki 'card'
let currentOrgName = 'Said Baraka';
let currentOrgId = '';

// Oylar nomlari (O'zbekcha)
const UZ_MONTHS = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
];

let activeDatePivot = new Date(); // Hozirgi ko'rilayotgan sana/oy

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
        toDate = new Date(year, month + 1, 0);
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
        document.querySelectorAll('.quick-dates .quick-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.period === 'all'));
        if (applyLoad) loadCashflow();
        return;
    }

    if (fromInput) fromInput.value = getLocalDateString(fromDate);
    if (toInput) toInput.value = getLocalDateString(toDate);
    if (labelEl) labelEl.textContent = labelText;

    document.querySelectorAll('.quick-dates .quick-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.period === currentPeriod));

    if (applyLoad) loadCashflow();
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
        // Standart davr: 'month' (Joriy to'liq oy)
        updateDateRangeUI(false);

        // 1. Valyuta kurslarini yuklash
        await loadCurrencyData();

        // 2. Tashkilot va hisob raqamlarini yuklash
        await loadOrgAndAccounts();

        // 3. Xarajat moddalarini yuklash
        await loadExpenseItems();

        // 4. Mijozlar ro'yxatini yuklash (kirim kiritish uchun)
        loadCustomersForModal();

        // 5. Hodisalarni ulash (Search & Date)
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', debounce(() => {
                loadCashflow();
            }, 300));
        }

        const onCustomDateChange = () => {
            const f = document.getElementById('dateFrom').value;
            const t = document.getElementById('dateTo').value;
            if (f && t) {
                document.querySelectorAll('.quick-dates .quick-btn').forEach(btn => btn.classList.remove('active'));
                const labelEl = document.getElementById('periodDisplayLabel');
                if (labelEl) labelEl.textContent = `${f} — ${t}`;
            }
            loadCashflow();
        };

        const dateFromInput = document.getElementById('dateFrom');
        const dateToInput = document.getElementById('dateTo');
        if (dateFromInput && dateToInput) {
            dateFromInput.addEventListener('change', onCustomDateChange);
            dateToInput.addEventListener('change', onCustomDateChange);
        }

        // 6. Kassa ma'lumotlarini yuklash
        await loadCashflow();
    } catch (error) {
        console.error('Kassa sahifasi boshlang\'ich xatosi:', error);
    }
});

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

function clearActivePeriodButtons() {
    document.querySelectorAll('.quick-dates .quick-btn').forEach(btn => btn.classList.remove('active'));
}

// ===== VALYUTA VA KURS BOSHQARUVI =====
async function loadCurrencyData() {
    try {
        const currData = await fetchUSDRate();
        if (currData) {
            const rate = currData.usd_rate || 12800;
            const rateDisp = document.getElementById('currentUsdRateDisplay');
            if (rateDisp) {
                rateDisp.textContent = `1 USD = ${formatMoney(rate)}`;
            }

            const cbu = currData.cbu;
            const cbuDisp = document.getElementById('cbuRateDisplay');
            const cbuDiff = document.getElementById('cbuDiffDisplay');
            if (cbu && cbuDisp) {
                cbuDisp.textContent = `${formatMoney(cbu.rate)}`;
                if (cbuDiff && cbu.diff) {
                    const isPositive = !cbu.diff.startsWith('-');
                    cbuDiff.textContent = `(${cbu.diff})`;
                    cbuDiff.style.color = isPositive ? '#16a34a' : '#ef4444';
                }
            }
        }
    } catch (e) {
        console.warn('Valyuta ma\'lumotlari olinmadi:', e);
    }
}

function openCurrencyModal() {
    const modal = document.getElementById('currencyModal');
    if (!modal) return;

    document.getElementById('modalCurrentRate').textContent = `1 USD = ${formatMoney(window.currentUSDRate || 12800)}`;
    
    if (window.cbuRateInfo) {
        document.getElementById('modalCbuRate').textContent = `${formatMoney(window.cbuRateInfo.rate)} (${window.cbuRateInfo.date || ''})`;
    } else {
        document.getElementById('modalCbuRate').textContent = "Yuklanmoqda...";
    }

    document.getElementById('newUsdRateInput').value = formatNumber(window.currentUSDRate || '', true);
    modal.classList.add('active');
}

function closeCurrencyModal() {
    const modal = document.getElementById('currencyModal');
    if (modal) modal.classList.remove('active');
}

async function handleRateSubmit(event) {
    event.preventDefault();
    const rateInput = document.getElementById('newUsdRateInput');
    const rateVal = parseAmount(rateInput.value);

    if (!rateVal || rateVal <= 0) {
        alert("Iltimos, to'g'ri kurs qiymatini kiriting");
        return;
    }

    const btn = document.getElementById('saveRateBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Saqlanmoqda...';

    try {
        const resp = await apiFetch('/currency/usd-rate', {
            method: 'POST',
            body: JSON.stringify({ rate: rateVal })
        });

        if (resp.success) {
            window.currentUSDRate = rateVal;
            alert(`✅ ${resp.message}`);
            closeCurrencyModal();
            await loadCurrencyData();
            await loadCashflow();
        } else {
            throw new Error(resp.detail || 'Kursni saqlashda xatolik');
        }
    } catch (e) {
        alert(`❌ Xatolik: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 Kursni Saqlash';
    }
}

async function syncCbuRate() {
    if (!confirm("Rostdan ham MoySklad USD kursini O'zbekiston Markaziy Banki rasmiy kursi bilan tenglashtirmoqchimisiz?")) {
        return;
    }

    try {
        const resp = await apiFetch('/currency/sync-cbu', { method: 'POST' });
        if (resp.success && resp.data) {
            window.currentUSDRate = resp.data.new_rate;
            alert(`✅ ${resp.message}`);
            closeCurrencyModal();
            await loadCurrencyData();
            await loadCashflow();
        } else {
            throw new Error(resp.detail || 'Sinxronlashda xatolik');
        }
    } catch (e) {
        alert(`❌ Xatolik: ${e.message}`);
    }
}

// ===== TASHKILOT VA HISOBLARNI YUKLASH =====
async function loadOrgAndAccounts() {
    try {
        const orgResp = await apiFetch('/dashboard/organization');
        if (orgResp.success && orgResp.data) {
            currentOrgName = orgResp.data.name || 'Said Baraka';
            currentOrgId = orgResp.data.id || '';
            const orgEl = document.getElementById('orgName');
            if (orgEl) orgEl.textContent = currentOrgName;

            if (currentOrgId) {
                const accountsResp = await apiFetch(`/payments/accounts/${currentOrgId}`);
                if (accountsResp.success) {
                    orgAccounts = accountsResp.data || [];
                    populateAccountSelects();
                }
            }
        }
    } catch (e) {
        console.warn('Tashkilot hisoblari yuklanmadi:', e);
    }
}

function populateAccountSelects() {
    // 1. Filtr paneli selecti
    const accFilter = document.getElementById('accountFilter');
    if (accFilter) {
        accFilter.innerHTML = '<option value="all">🏦 Barcha hisoblar & kassalar</option>' +
            orgAccounts.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    }

    // 2. Yangi xarajat modali selecti
    updateExpenseAccountOptions();

    // 3. Kirim modali selecti
    const payAcc = document.getElementById('payAccountSelect');
    if (payAcc) {
        // Faqat bank va valyuta hisoblari
        const bankOnly = orgAccounts.filter(a => a.type !== 'cash');
        payAcc.innerHTML = '<option value="">Asosiy hisob (Avtomatik)</option>' +
            bankOnly.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    }
}

function updateExpenseAccountOptions() {
    const expAcc = document.getElementById('expenseAccountSelect');
    if (!expAcc) return;

    if (selectedExpenseType === 'cash') {
        // Faqat naqd kassa
        expAcc.innerHTML = '<option value="cash_default">💵 Asosiy Naqd Kassa (UZS)</option>';
    } else {
        // Bank va dollar hisoblari
        const bankOnly = orgAccounts.filter(a => a.type !== 'cash');
        expAcc.innerHTML = bankOnly.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    }
}

// ===== HISOBLAR BO'YICHA FILTRLASH =====
function filterByAccount(accId, closeOnSelect = false) {
    currentAccountId = accId;
    const select = document.getElementById('accountFilter');
    if (select) select.value = accId;

    const resetBtn = document.getElementById('resetAccountFilterBtn');
    if (resetBtn) {
        resetBtn.style.display = accId !== 'all' ? 'inline-block' : 'none';
    }

    // Kartalardagi active klassini yangilash
    document.querySelectorAll('.account-card').forEach(card => {
        card.classList.toggle('active-filter', card.dataset.accountId === accId);
    });

    if (closeOnSelect) {
        closeAccountsModal();
    }

    loadCashflow();
}

function handleAccountFilterChange() {
    const val = document.getElementById('accountFilter').value;
    filterByAccount(val);
}

// ===== HISOBLAR BALANSI MODALI BO'YICHA BOSHQARUV =====
function openAccountsModal() {
    const modal = document.getElementById('accountsModal');
    if (modal) modal.classList.add('active');
}

function closeAccountsModal() {
    const modal = document.getElementById('accountsModal');
    if (modal) modal.classList.remove('active');
}

// ===== HISOBLAR BALANSI VIDJETINI CHIZISH =====
function renderAccountsGrid(accountBalances) {
    const grid = document.getElementById('accountsGrid');
    if (!grid) return;

    if (!accountBalances || accountBalances.length === 0) {
        grid.innerHTML = '<div style="color:var(--text-light); padding:10px;">Hisoblar ma\'lumoti yo\'q</div>';
        return;
    }

    grid.innerHTML = accountBalances.map(acc => {
        const isCash = acc.type === 'cash';
        const isDollar = acc.type === 'dollar' || acc.is_dollar || acc.currency === 'USD';
        const badgeTypeClass = isCash ? 'account-type-cash' : (isDollar ? 'account-type-dollar' : 'account-type-bank');
        const badgeLabel = isCash ? 'Naqd Kassa' : (isDollar ? 'Valyuta (USD)' : 'Bank Hisob');
        const isActive = currentAccountId === acc.id;

        const balanceFormatted = isDollar
            ? `$${formatMoney(acc.balance || 0)}`
            : `${formatMoney(acc.balance || 0)} so'm`;

        return `
            <div class="account-card ${isActive ? 'active-filter' : ''}" data-account-id="${acc.id}" onclick="filterByAccount('${acc.id}', true)">
                <div class="account-card-top">
                    <span class="account-card-name" title="${acc.name}">${acc.name}</span>
                    <span class="account-card-type-badge ${badgeTypeClass}">${badgeLabel}</span>
                </div>
                <div class="account-card-balance" style="${isDollar ? 'color:#15803d;' : ''}">${balanceFormatted}</div>
                ${acc.is_adjusted ? `<div class="adjusted-tag" title="Sabab: ${acc.reason || 'Korrektirovka'}">✏️ To'g'rilangan</div>` : ''}
                <div style="margin-top:6px; display:flex; justify-content:space-between; align-items:center;">
                    <button type="button" class="btn-quick-adjust" onclick="event.stopPropagation(); closeAccountsModal(); openAdjustmentModal('${acc.id}', '${(acc.name || '').replace(/'/g, "\\'")}', ${acc.balance || 0}, '${acc.currency || (isDollar ? 'USD' : 'UZS')}')">
                        ✏️ Korrektirovka
                    </button>
                    <span style="font-size:11px; color:var(--text-light); font-weight:600;">Filtrlash ↗️</span>
                </div>
            </div>
        `;
    }).join('');
}

// ===== TUR FILTRI (KIRIM / CHIQIM) =====
function selectTypeFilter(type) {
    currentTypeFilter = type;
    document.querySelectorAll('[data-type]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.type === type);
    });
    loadCashflow();
}

// ===== XARAJAT MODDALARINI YUKLASH =====
async function loadExpenseItems() {
    try {
        const resp = await apiFetch('/payments/expense-items');
        if (resp.success && Array.isArray(resp.data)) {
            expenseItems = resp.data;

            const filterSelect = document.getElementById('expenseItemFilter');
            filterSelect.innerHTML = '<option value="">Barcha xarajat moddalari</option>' +
                expenseItems.map(it => `<option value="${it.id}">${it.name}</option>`).join('');

            const modalSelect = document.getElementById('expenseItemSelect');
            modalSelect.innerHTML = '<option value="">Tanlang...</option>' +
                expenseItems.map(it => `<option value="${it.id}">${it.name}</option>`).join('');
        }
    } catch (e) {
        console.warn('Xarajat moddalari yuklanmadi:', e);
    }
}

// ===== KASSA MA'LUMOTLARINI YUKLASH =====
async function loadCashflow() {
    const tbody = document.getElementById('cashflowTable');
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="loading">⏳ Kassa va hisob ma\'lumotlari yuklanmoqda...</td></tr>';

    const fromEl = document.getElementById('dateFrom');
    const toEl = document.getElementById('dateTo');
    const expEl = document.getElementById('expenseItemFilter');
    const searchEl = document.getElementById('searchInput');

    const dateFrom = fromEl ? fromEl.value : '';
    const dateTo = toEl ? toEl.value : '';
    const expenseItemId = expEl ? expEl.value : '';
    const searchVal = (searchEl && searchEl.value ? searchEl.value : '').toLowerCase().trim();

    try {
        const params = new URLSearchParams();
        if (dateFrom) params.append('date_from', dateFrom);
        if (dateTo) params.append('date_to', dateTo);
        if (currentTypeFilter !== 'all') params.append('type_filter', currentTypeFilter);
        if (expenseItemId) params.append('expense_item_id', expenseItemId);
        if (currentAccountId && currentAccountId !== 'all') params.append('account_id', currentAccountId);

        const resp = await apiFetch(`/payments/cashflow?${params.toString()}`);
        if (resp.success && resp.data) {
            currentCashflowData = resp.data;
            if (resp.data.summary && resp.data.summary.usd_rate) {
                window.currentUSDRate = resp.data.summary.usd_rate;
            }

            let txList = resp.data.transactions || [];
            if (searchVal) {
                txList = txList.filter(t => 
                    (t.target_name || '').toLowerCase().includes(searchVal) ||
                    (t.purpose || '').toLowerCase().includes(searchVal) ||
                    (t.doc_number || '').toLowerCase().includes(searchVal) ||
                    (t.account_name || '').toLowerCase().includes(searchVal) ||
                    (t.expense_item || '').toLowerCase().includes(searchVal)
                );
            }

            renderStats(resp.data.summary);
            renderTransactions(txList);
            const countEl = document.getElementById('resultsCount');
            if (countEl) countEl.textContent = `Jami: ${txList.length} ta operatsiya`;
        } else {
            throw new Error(resp.detail || 'Ma\'lumot yuklanmadi');
        }
    } catch (e) {
        console.error('Cashflow yuklash xatosi:', e);
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="loading" style="color:red;">Xato: ${e.message}</td></tr>`;
    }
}

// ===== STATISTIKANI CHIZISH =====
function renderStats(summary) {
    if (!summary) return;

    // 0. Top Dual-Currency Banner (UZS va USD alohida)
    const topUzsEl = document.getElementById('topTotalUzsDisplay');
    const topUsdEl = document.getElementById('topTotalUsdDisplay');
    const topConsEl = document.getElementById('topConsolidatedDisplay');
    const topRefSub = document.getElementById('topRefRateSub');

    if (topUzsEl) topUzsEl.textContent = formatMoney(summary.total_uzs_balance || 0) + " so'm";
    if (topUsdEl) topUsdEl.textContent = "$" + formatMoney(summary.total_usd_balance || 0);
    if (topConsEl) topConsEl.textContent = "~ " + formatMoney(summary.consolidated_uzs_equivalent || 0) + " so'm";
    if (topRefSub && summary.usd_rate) topRefSub.textContent = `(@ ${formatMoney(summary.usd_rate)})`;

    // 1. Asosiy summalar (So'm va Dollar aniq taqsimoti bilan)
    const inflowTotal = summary.total_inflow || 0;
    const inflowUzs = summary.inflow_uzs !== undefined ? summary.inflow_uzs : inflowTotal;
    const inflowUsd = summary.inflow_usd || 0;

    const outflowTotal = summary.total_outflow || 0;
    const outflowUzs = summary.outflow_uzs !== undefined ? summary.outflow_uzs : outflowTotal;
    const outflowUsd = summary.outflow_usd || 0;

    const netTotal = summary.net_balance !== undefined ? summary.net_balance : (inflowTotal - outflowTotal);
    const netUzs = summary.net_uzs !== undefined ? summary.net_uzs : (inflowUzs - outflowUzs);
    const netUsd = summary.net_usd !== undefined ? summary.net_usd : (inflowUsd - outflowUsd);

    // Kirim kartasi
    document.getElementById('statInflow').textContent = formatMoney(inflowTotal);
    const inUzsEl = document.getElementById('statInflowUzs');
    if (inUzsEl) inUzsEl.textContent = formatMoney(inflowUzs);
    const inUsdEl = document.getElementById('statInflowUSD');
    if (inUsdEl) inUsdEl.textContent = `$${formatNumber(inflowUsd)}`;

    // Chiqim kartasi
    document.getElementById('statOutflow').textContent = formatMoney(outflowTotal);
    const outUzsEl = document.getElementById('statOutflowUzs');
    if (outUzsEl) outUzsEl.textContent = formatMoney(outflowUzs);
    const outUsdEl = document.getElementById('statOutflowUSD');
    if (outUsdEl) outUsdEl.textContent = `$${formatNumber(outflowUsd)}`;

    // Sof qoldiq kartasi
    const netEl = document.getElementById('statNetBalance');
    netEl.textContent = (netTotal > 0 ? '+' : '') + formatMoney(netTotal);
    netEl.style.color = netTotal >= 0 ? 'var(--primary)' : 'var(--danger)';

    const netUzsEl = document.getElementById('statNetUzs');
    if (netUzsEl) netUzsEl.textContent = (netUzs > 0 ? '+' : '') + formatMoney(netUzs);

    const netUsdEl = document.getElementById('statNetBalanceUSD');
    if (netUsdEl) {
        netUsdEl.textContent = (netUsd > 0 ? '+$' : '$') + formatNumber(netUsd);
        netUsdEl.style.color = netUsd >= 0 ? 'var(--success)' : 'var(--danger)';
    }

    // Naqd va Bank qoldiqlari
    document.getElementById('statCashIn').textContent = formatMoney(summary.cash_balance >= 0 ? summary.cash_balance : 0);
    document.getElementById('statCardIn').textContent = formatMoney(summary.card_balance >= 0 ? summary.card_balance : 0);
    document.getElementById('statCashBalance').textContent = formatMoney(summary.cash_balance || 0);
    document.getElementById('statCardBalance').textContent = formatMoney(summary.card_balance || 0);

    // 2. Hisoblar balansi kartalarini chizish
    renderAccountsGrid(summary.account_balances || []);
}

// ===== TRANZAKSIYALAR JADVALINI CHIZISH =====
function renderTransactions(transactions) {
    const tbody = document.getElementById('cashflowTable');
    if (!transactions || transactions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="loading">Bu filtr bo\'yicha operatsiyalar topilmadi</td></tr>';
        return;
    }

    // Saralash uchun transaksiyalarni saqlab qo'yish
    if (typeof lastRenderedTransactions !== 'undefined') {
        lastRenderedTransactions = transactions;
    }

    tbody.innerHTML = transactions.map((t, idx) => {
        const isIn = t.direction === 'in';
        const isCash = t.doc_type === 'cashin' || t.doc_type === 'cashout' || t.account_id === 'cash_default';
        const isDollar = t.account_type === 'dollar' || (t.account_name && t.account_name.toLowerCase().includes('dollar')) || (t.usd_amount && t.usd_amount > 0);
        const badgeClass = isIn ? 'badge-inflow' : 'badge-outflow';
        const sign = isIn ? '+' : '-';
        const amountColor = isIn ? 'var(--success)' : 'var(--danger)';
        const dateStr = t.moment ? t.moment.substring(0, 16) : '—';

        let accBadgeClass = 'badge-acc-bank';
        if (isCash) accBadgeClass = 'badge-acc-cash';
        else if (isDollar) accBadgeClass = 'badge-acc-dollar';

        const accDisplay = t.account_name || (isCash ? '💵 Naqd Kassa' : '🏦 Bank hisobi');

        let typeNameDisplay = `<span class="${badgeClass}">${isIn ? '📥' : '📤'} ${t.type_name}</span>`;
        if (t.linked_demand_id || t.demand_id) {
            const did = t.linked_demand_id || t.demand_id;
            typeNameDisplay = `<a href="/static/demands.html" onclick="event.stopPropagation(); sessionStorage.setItem('openDemand','${did}')" style="text-decoration:none;" title="Sotuvni ko'rish"><span class="${badgeClass}" style="cursor:pointer;box-shadow:0 0 0 1px var(--accent);">${isIn ? '📥' : '📤'} ${t.type_name} 🔗</span></a>`;
        } else if (t.doc_number) {
            typeNameDisplay = `<span class="${badgeClass}">${isIn ? '📥' : '📤'} ${t.type_name} №${t.doc_number}</span>`;
        }

        const safeId = t.id || '';
        const safeDocType = t.doc_type || (isIn ? 'cashin' : 'cashout');

        return `
            <tr onclick="openPaymentEditModal('${safeId}', '${safeDocType}')" style="cursor:pointer;" title="Tahrirlash yoki sotuvga bog'lash uchun bosing">
                <td style="text-align:center;font-size:12px;color:var(--text-light);">${idx + 1}</td>
                <td style="font-weight:600;white-space:nowrap;">${dateStr}</td>
                <td>${typeNameDisplay}</td>
                <td>
                    <span class="badge-account ${accBadgeClass}">
                        ${accDisplay}
                    </span>
                </td>
                <td style="font-weight:700;color:var(--primary);">
                    ${t.target_name}
                </td>
                <td style="font-size:13px;color:var(--text-light);max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${t.purpose || ''}">
                    ${t.purpose || '—'}
                </td>
                <td style="text-align:right;font-weight:800;color:${amountColor};white-space:nowrap;">
                    <span>${sign} ${formatMoney(t.amount)}</span>
                    <button class="btn-icon" onclick="event.stopPropagation(); openPaymentEditModal('${safeId}', '${safeDocType}')" title="Tahrirlash" style="background:transparent;border:none;cursor:pointer;font-size:13px;margin-left:8px;padding:2px 4px;border-radius:4px;">✏️</button>
                </td>
            </tr>
        `;
    }).join('');
}

// ===== XARAJAT KIRITISH MODALI BOSHQARUVI =====
function openExpenseModal() {
    const modal = document.getElementById('expenseModal');
    if (!modal) return;
    setExpenseType('cash');
    document.getElementById('expenseAmount').value = '';
    document.getElementById('expenseUsdPreview').textContent = '~ $0.00 USD';
    document.getElementById('expenseDescription').value = '';
    modal.classList.add('active');
}

function closeExpenseModal() {
    const modal = document.getElementById('expenseModal');
    if (modal) modal.classList.remove('active');
}

function setExpenseType(type) {
    selectedExpenseType = type;
    document.getElementById('expTypeCash').classList.toggle('active', type === 'cash');
    document.getElementById('expTypeCard').classList.toggle('active', type === 'card');
    updateExpenseAccountOptions();
}

function updateExpenseUSDPreview() {
    const amt = parseAmount(document.getElementById('expenseAmount').value);
    document.getElementById('expenseUsdPreview').textContent = `~ ${formatUSD(amt)} USD`;
}

async function handleExpenseSubmit(event) {
    event.preventDefault();
    const amount = parseAmount(document.getElementById('expenseAmount').value);
    const expense_item_id = document.getElementById('expenseItemSelect').value;
    const account_id = document.getElementById('expenseAccountSelect').value;
    const description = document.getElementById('expenseDescription').value;

    if (!amount || amount <= 0) {
        alert("Xarajat summasini kiriting!");
        return;
    }
    if (!expense_item_id) {
        alert("Xarajat toifasini tanlang!");
        return;
    }

    const btn = document.getElementById('saveExpenseBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Saqlanmoqda...';

    try {
        const payload = {
            amount: amount,
            payment_type: selectedExpenseType,
            expense_item_id: expense_item_id,
            description: description,
            account_id: account_id !== 'cash_default' ? account_id : null,
        };

        const resp = await apiFetch('/payments/expense', {
            method: 'POST',
            body: JSON.stringify(payload),
        });

        if (resp.success) {
            alert("✅ Xarajat muvaffaqiyatli saqlandi!");
            closeExpenseModal();
            loadCashflow();
        } else {
            throw new Error(resp.detail || 'Xarajatni saqlashda xatolik');
        }
    } catch (e) {
        alert(`❌ Xatolik: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 Xarajatni Saqlash';
    }
}

// ===== YANGI XARAJAT MODDASI MODALI =====
function openNewExpenseItemModal() {
    document.getElementById('newItemName').value = '';
    document.getElementById('newItemDescription').value = '';
    document.getElementById('newExpenseItemModal').classList.add('active');
}

function closeNewExpenseItemModal() {
    document.getElementById('newExpenseItemModal').classList.remove('active');
}

async function handleNewExpenseItemSubmit(event) {
    event.preventDefault();
    const name = document.getElementById('newItemName').value.trim();
    const desc = document.getElementById('newItemDescription').value.trim();

    if (!name) {
        alert("Toifa nomini kiriting!");
        return;
    }

    const btn = document.getElementById('saveNewItemBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Yaratilmoqda...';

    try {
        const resp = await apiFetch('/payments/expense-items', {
            method: 'POST',
            body: JSON.stringify({ name: name, description: desc }),
        });

        if (resp.success) {
            alert("✅ Yangi xarajat toifasi yaratildi!");
            closeNewExpenseItemModal();
            await loadExpenseItems();
            if (resp.data && resp.data.id) {
                document.getElementById('expenseItemSelect').value = resp.data.id;
            }
        } else {
            throw new Error(resp.detail || 'Toifa yaratishda xatolik');
        }
    } catch (e) {
        alert(`❌ Xatolik: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '➕ Yaratish';
    }
}

// ===== KIRIM KIRITISH MODALI =====
async function loadCustomersForModal() {
    try {
        const resp = await apiFetch('/customers');
        if (resp.success && resp.data) {
            customersList = resp.data.customers || [];
            const select = document.getElementById('payCustomerSelect');
            if (select) {
                select.innerHTML = '<option value="">Mijozni tanlang...</option>' +
                    customersList.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
            }
        }
    } catch (e) {
        console.warn('Mijozlar yuklanmadi:', e);
    }
}

function openCustomerPaymentModal() {
    document.getElementById('payCashAmount').value = '';
    document.getElementById('payCardAmount').value = '';
    document.getElementById('payDescription').value = '';
    updatePaymentUSDPreview();
    document.getElementById('customerPaymentModal').classList.add('active');
}

function closeCustomerPaymentModal() {
    document.getElementById('customerPaymentModal').classList.remove('active');
}

function updatePaymentUSDPreview() {
    const cash = parseAmount(document.getElementById('payCashAmount').value);
    const card = parseAmount(document.getElementById('payCardAmount').value);
    const total = cash + card;

    document.getElementById('payTotalPreview').textContent = formatMoney(total);
    document.getElementById('payTotalUSDPreview').textContent = `${formatUSD(total)} USD`;
}

async function handleCustomerPaymentSubmit(event) {
    event.preventDefault();
    const customer_id = document.getElementById('payCustomerSelect').value;
    const cash_amount = parseAmount(document.getElementById('payCashAmount').value);
    const card_amount = parseAmount(document.getElementById('payCardAmount').value);
    const account_id = document.getElementById('payAccountSelect').value;
    const description = document.getElementById('payDescription').value;

    if (!customer_id) {
        alert("Iltimos, mijozni tanlang!");
        return;
    }

    if (cash_amount <= 0 && card_amount <= 0) {
        alert("Naqd yoki bank summasidan kamida bittasini kiriting!");
        return;
    }

    const btn = document.getElementById('saveCustomerPaymentBtn');
    btn.disabled = true;
    btn.textContent = '⏳ Saqlanmoqda...';

    try {
        const payload = {
            counterparty_id: customer_id,
            cash_amount: cash_amount,
            card_amount: card_amount,
            account_id: account_id || null,
            description: description || "Mijozdan to'lov",
        };

        const resp = await apiFetch('/payments/customer-payment', {
            method: 'POST',
            body: JSON.stringify(payload),
        });

        if (resp.success) {
            alert("✅ Kirim to'lov muvaffaqiyatli saqlandi!");
            closeCustomerPaymentModal();
            loadCashflow();
        } else {
            throw new Error(resp.detail || 'To\'lovni saqlashda xatolik');
        }
    } catch (e) {
        alert(`❌ Xatolik: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 Kirimni Saqlash';
    }
}

// ===== CHOP ETISH =====
function togglePaymentsPrintDropdown(btnEl) {
    const dropdown = btnEl?.nextElementSibling;
    if (dropdown) dropdown.classList.toggle('show');
}

// Dropdown tashqarisiga bosilganda yopish
document.addEventListener('click', (e) => {
    if (!e.target.closest('.print-dropdown-wrapper')) {
        document.querySelectorAll('.print-dropdown-menu.show').forEach(d => d.classList.remove('show'));
    }
});

async function printCashflowReport(format = 'a4') {
    // Dropdownni yopish
    document.querySelectorAll('.print-dropdown-menu.show').forEach(d => d.classList.remove('show'));

    document.body.classList.remove('print-a4', 'print-a5');
    document.body.classList.add(`print-${format}`);

    window.print();
}

// ===== KASSA JADVALINI SARALASH (CLIENT-SIDE) =====
let paymentSortField = null;
let paymentSortDir = 'asc';
let lastRenderedTransactions = [];

function sortPaymentsBy(field) {
    if (paymentSortField === field) {
        paymentSortDir = paymentSortDir === 'asc' ? 'desc' : 'asc';
    } else {
        paymentSortField = field;
        paymentSortDir = field === 'amount' ? 'desc' : 'asc';
    }

    const comparators = {
        'moment': (a, b) => (a.moment || '').localeCompare(b.moment || ''),
        'type_name': (a, b) => (a.type_name || '').localeCompare(b.type_name || '', 'uz'),
        'target_name': (a, b) => (a.target_name || '').localeCompare(b.target_name || '', 'uz'),
        'amount': (a, b) => (a.amount || 0) - (b.amount || 0),
    };

    const cmp = comparators[field];
    if (!cmp || !lastRenderedTransactions || lastRenderedTransactions.length === 0) return;

    lastRenderedTransactions.sort((a, b) => {
        const result = cmp(a, b);
        return paymentSortDir === 'asc' ? result : -result;
    });

    renderTransactions(lastRenderedTransactions);
    updatePaymentSortIndicators();
}

function updatePaymentSortIndicators() {
    document.querySelectorAll('.payments-sortable').forEach(th => {
        th.classList.remove('sorted-asc', 'sorted-desc');
        const arrow = th.querySelector('.sort-arrow');
        if (arrow) arrow.textContent = '↕';
    });

    if (paymentSortField) {
        const activeTh = document.getElementById(`pth-${paymentSortField}`);
        if (activeTh) {
            activeTh.classList.add(paymentSortDir === 'asc' ? 'sorted-asc' : 'sorted-desc');
            const arrow = activeTh.querySelector('.sort-arrow');
            if (arrow) arrow.textContent = paymentSortDir === 'asc' ? '▲' : '▼';
        }
    }
}

// ===== HISOB QOLDIG'INI KORREKTIROVKA QILISH =====
let activeAdjCurrency = 'UZS';

function openAdjustmentModal(accId, name, balance, currency) {
    document.getElementById('adjAccountId').value = accId;
    document.getElementById('adjAccountName').textContent = name;
    activeAdjCurrency = currency || 'UZS';
    
    const isDollar = activeAdjCurrency === 'USD';
    const balanceText = isDollar ? `$${formatMoney(balance)} USD` : `${formatMoney(balance)} so'm`;
    document.getElementById('adjCurrentBalance').textContent = balanceText;
    document.getElementById('adjCurrencyHint').textContent = isDollar
        ? "Ushbu hisob Dollarda (USD). Haqiqiy qoldiqni AQSH dollarida kiriting."
        : "Ushbu hisob O'zbekiston so'mida (UZS). Haqiqiy qoldiqni so'mda kiriting.";

    document.getElementById('adjNewBalance').value = formatNumber(balance || 0, true);
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
        alert("Iltimos, yangi qoldiqni kiriting!");
        return;
    }
    if (!reason) {
        alert("Iltimos, korrektirovka sababini kiriting!");
        return;
    }

    const saveBtn = document.getElementById('saveAdjBtn');
    saveBtn.disabled = true;
    saveBtn.textContent = '⏳ Saqlanmoqda...';

    try {
        const resp = await apiFetch('/settings/accounts/adjust-balance', {
            method: 'POST',
            body: JSON.stringify({
                account_id: accId,
                corrected_balance: newBal,
                reason: reason
            })
        });

        if (resp && resp.success) {
            alert("✅ Hisob qoldig'i muvaffaqiyatli korrektirovka qilindi!");
            closeAdjustmentModal();
            await loadCashflow();
        } else {
            throw new Error(resp?.detail || 'Korrektirovkani saqlashda xatolik');
        }
    } catch (e) {
        alert(`❌ Xatolik: ${e.message}`);
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = '💾 Korrektirovkani Saqlash';
    }
}

// ================= TO'LOVNI TAHRIRLASH, SOTUVGA BOG'LASH VA O'CHIRISH =================
let currentEditingTx = null;

async function openPaymentEditModal(paymentId, docType) {
    if (!paymentId) return;

    // Tranzaksiyani keshdan yoki joriy ro'yxatdan topish
    let tx = null;
    if (currentCashflowData && currentCashflowData.transactions) {
        tx = currentCashflowData.transactions.find(t => t.id === paymentId);
    }

    currentEditingTx = tx || { id: paymentId, doc_type: docType };

    const modal = document.getElementById('editPaymentModal');
    if (!modal) return;

    document.getElementById('editPayId').value = paymentId;
    document.getElementById('editPayDocType').value = docType || 'cashin';

    // Sarlavha
    const typeLabel = tx ? (tx.type_name || 'To\'lov') : 'To\'lov';
    document.getElementById('editPayTitle').textContent = `✏️ ${typeLabel}ni Tahrirlash`;
    document.getElementById('editPayDocSubtitle').textContent = tx 
        ? `Hujjat: ${tx.doc_number || '—'} | Kontragent: ${tx.target_name || '—'}`
        : `ID: ${paymentId}`;

    // Summa va valyuta
    const isDollar = tx && (tx.account_type === 'dollar' || (tx.usd_amount && tx.usd_amount > 0));
    const currSelect = document.getElementById('editPayCurrency');
    currSelect.value = isDollar ? 'USD' : 'UZS';

    const amtInput = document.getElementById('editPayAmount');
    amtInput.value = tx ? formatNumber(tx.amount) : '0';

    const usdGroup = document.getElementById('editPayUsdGroup');
    const usdInput = document.getElementById('editPayUsdAmount');
    const rateInput = document.getElementById('editPayUsdRate');

    if (isDollar) {
        usdGroup.style.display = 'block';
        usdInput.value = tx ? formatNumber(tx.usd_amount || Math.round(tx.amount / (window.currentUSDRate || 12800)), true) : '0';
        rateInput.value = formatNumber(window.currentUSDRate || 12800);
    } else {
        usdGroup.style.display = 'none';
        usdInput.value = '';
        rateInput.value = formatNumber(window.currentUSDRate || 12800);
    }

    // Sana va vaqt
    const momentInput = document.getElementById('editPayMoment');
    if (tx && tx.moment) {
        // "2026-09-20 18:30:00" -> "2026-09-20T18:30"
        const cleanMoment = tx.moment.substring(0, 16).replace(' ', 'T');
        momentInput.value = cleanMoment;
    } else {
        const now = new Date();
        momentInput.value = now.toISOString().substring(0, 16);
    }

    // Maqsad / Izoh
    document.getElementById('editPayPurpose').value = tx ? (tx.purpose || '') : '';

    // Sotuvga bog'lash selectini to'ldirish
    const linkSelect = document.getElementById('editPayLinkDemand');
    linkSelect.innerHTML = '<option value="">(Bog\'lanmagan / Alohida to\'lov)</option>';

    if (tx && tx.target_name && tx.target_name !== 'Xarajat' && tx.target_name !== 'Bank xarajati') {
        try {
            const demandsResp = await apiFetch(`/demands?limit=15&offset=0&search=${encodeURIComponent(tx.target_name)}`);
            if (demandsResp && demandsResp.data && demandsResp.data.length > 0) {
                demandsResp.data.forEach(d => {
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
        } catch (e) {
            console.warn("Mijoz sotuvlarini yuklab bo'lmadi:", e);
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
    const curr = document.getElementById('editPayCurrency').value;
    const usdGroup = document.getElementById('editPayUsdGroup');
    if (curr === 'USD') {
        usdGroup.style.display = 'block';
        const amt = parseAmount(document.getElementById('editPayAmount').value);
        const rate = parseAmount(document.getElementById('editPayUsdRate').value) || (window.currentUSDRate || 12800);
        if (amt > 0) {
            document.getElementById('editPayUsdAmount').value = (amt / rate).toFixed(2);
        }
    } else {
        usdGroup.style.display = 'none';
    }
}

function recalcEditUzsFromUsd() {
    const usdVal = parseAmount(document.getElementById('editPayUsdAmount').value);
    const rate = parseAmount(document.getElementById('editPayUsdRate').value) || (window.currentUSDRate || 12800);
    if (usdVal > 0) {
        document.getElementById('editPayAmount').value = formatNumber(Math.round(usdVal * rate));
    }
}

async function handleEditPaymentSubmit(event) {
    event.preventDefault();
    const paymentId = document.getElementById('editPayId').value;
    const docType = document.getElementById('editPayDocType').value;
    const amount = parseAmount(document.getElementById('editPayAmount').value);
    const curr = document.getElementById('editPayCurrency').value;
    const momentVal = document.getElementById('editPayMoment').value;
    const purpose = document.getElementById('editPayPurpose').value.trim();
    const linkedDemandId = document.getElementById('editPayLinkDemand').value;

    if (isNaN(amount) || amount <= 0) {
        alert("Iltimos, to'g'ri to'lov summasini kiriting!");
        return;
    }

    const saveBtn = document.getElementById('saveEditPaymentBtn');
    saveBtn.disabled = true;
    saveBtn.textContent = '⏳ Saqlanmoqda...';

    const payload = {
        amount: amount,
        purpose: purpose,
        moment: momentVal.replace('T', ' ') + ':00',
    };

    if (curr === 'USD') {
        const usdAmount = parseAmount(document.getElementById('editPayUsdAmount').value);
        const usdRate = parseAmount(document.getElementById('editPayUsdRate').value) || (window.currentUSDRate || 12800);
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
            showToast("To'lov muvaffaqiyatli tahrirlandi!", "success");
            closeEditPaymentModal();
            await loadCashflow();
        } else {
            throw new Error(resp?.detail || 'To\'lovni yangilashda xatolik');
        }
    } catch (e) {
        alert(`❌ Xatolik: ${e.message}`);
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = '💾 Saqlash';
    }
}

async function deleteCurrentPayment() {
    const paymentId = document.getElementById('editPayId').value;
    const docType = document.getElementById('editPayDocType').value;

    if (!paymentId || !docType) return;

    if (!confirm("Haqiqatan ham ushbu to'lov hujjatini o'chirmoqchimisiz?\n\nBu to'lov MoySklad va mahalliy bazadan butunlay o'chiriladi.")) {
        return;
    }

    try {
        const resp = await apiFetch(`/payments/${docType}/${paymentId}`, {
            method: 'DELETE'
        });

        if (resp && resp.success) {
            showToast("To'lov muvaffaqiyatli o'chirildi!", "success");
            closeEditPaymentModal();
            await loadCashflow();
        } else {
            throw new Error(resp?.detail || 'To\'lovni o\'chirishda xatolik');
        }
    } catch (e) {
        alert(`❌ O'chirishda xatolik: ${e.message}`);
    }
}

window.addEventListener('click', (e) => {
    const accModal = document.getElementById('accountsModal');
    if (accModal && e.target === accModal) {
        closeAccountsModal();
    }
});

