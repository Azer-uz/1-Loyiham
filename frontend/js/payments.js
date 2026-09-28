
async function loadEditAccountsSelect(selectedAccountId) {
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

        // Hodisalarni ulash (Search & Date)
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

        // 🚀 Barcha ma'lumotlarni parallel yuklash (Tezkor 0.05 soniyada to'liq yuklanadi)
        await Promise.all([
            loadCashflow(),
            loadCurrencyData().catch(() => null),
            loadOrgAndAccounts().catch(() => null),
            loadExpenseItems().catch(() => null),
            loadCustomersForModal().catch(() => null),
        ]);
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
let appPaymentMethods = [];
let appAvailableAccounts = [];

async function loadOrgAndAccounts() {
    try {
        const [orgResp, methodsResp] = await Promise.all([
            apiFetch('/dashboard/organization'),
            apiFetch('/settings/payment-methods').catch(() => null)
        ]);

        if (methodsResp && methodsResp.success && methodsResp.data) {
            appPaymentMethods = methodsResp.data.methods || [];
            appAvailableAccounts = methodsResp.data.available_accounts || [];
        }

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

function getCardAccountsList() {
    const cardMethod = appPaymentMethods.find(m => m.id === 'card');
    if (cardMethod && Array.isArray(cardMethod.linked_accounts_detail) && cardMethod.linked_accounts_detail.length > 0) {
        return cardMethod.linked_accounts_detail;
    }
    if (cardMethod && Array.isArray(cardMethod.linked_account_ids) && cardMethod.linked_account_ids.length > 0) {
        return orgAccounts.filter(a => cardMethod.linked_account_ids.includes(a.id));
    }
    return orgAccounts.filter(a => a.type !== 'cash' && a.type !== 'dollar' && !a.isDollar && !a.is_dollar && a.currency !== 'USD');
}

function getDollarAccountsList() {
    const usdMethod = appPaymentMethods.find(m => m.id === 'usd');
    if (usdMethod && Array.isArray(usdMethod.linked_accounts_detail) && usdMethod.linked_accounts_detail.length > 0) {
        return usdMethod.linked_accounts_detail;
    }
    if (usdMethod && Array.isArray(usdMethod.linked_account_ids) && usdMethod.linked_account_ids.length > 0) {
        return orgAccounts.filter(a => usdMethod.linked_account_ids.includes(a.id));
    }
    return orgAccounts.filter(a => a.type === 'dollar' || a.isDollar || a.is_dollar || a.currency === 'USD');
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
        expAcc.innerHTML = '<option value="cash_default">💵 Asosiy Naqd Kassa (UZS)</option>';
    } else if (selectedExpenseType === 'card') {
        const uzsBankOnly = orgAccounts.filter(a => a.type !== 'cash' && !a.is_dollar && a.currency !== 'USD');
        expAcc.innerHTML = uzsBankOnly.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    } else if (selectedExpenseType === 'usd') {
        const usdAccounts = orgAccounts.filter(a => a.is_dollar || a.currency === 'USD');
        expAcc.innerHTML = usdAccounts.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
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

    const resetPageBtn = document.getElementById('resetAccountFilterPageBtn');
    if (resetPageBtn) {
        resetPageBtn.style.display = accId !== 'all' ? 'inline-block' : 'none';
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
    const gridModal = document.getElementById('accountsGrid');
    const gridPage = document.getElementById('pageAccountsGrid');

    if (!accountBalances || accountBalances.length === 0) {
        const emptyHtml = '<div style="color:var(--text-light); padding:10px;">Hisoblar ma\'lumoti yo\'q</div>';
        if (gridModal) gridModal.innerHTML = emptyHtml;
        if (gridPage) gridPage.innerHTML = emptyHtml;
        return;
    }

    const htmlContent = accountBalances.map(acc => {
        const isCash = acc.type === 'cash';
        const isDollar = acc.type === 'dollar' || acc.is_dollar || acc.currency === 'USD';
        const badgeTypeClass = isCash ? 'account-type-cash' : (isDollar ? 'account-type-dollar' : 'account-type-bank');
        const badgeLabel = isCash ? 'Naqd Kassa' : (isDollar ? 'Valyuta (USD)' : 'Bank Hisob');
        const isActive = currentAccountId === acc.id;

        const balanceFormatted = isDollar
            ? `$${formatNumber(acc.balance || 0)}`
            : `${formatNumber(acc.balance || 0)} so'm`;

        return `
            <div class="account-card ${isActive ? 'active-filter' : ''}" data-account-id="${acc.id}" onclick="filterByAccount('${acc.id}', false)" title="${isActive ? 'Tanlangan filtr' : 'Filtrlash uchun bosing'}">
                <div class="account-card-top">
                    <span class="account-card-name" title="${acc.name}">${acc.name}</span>
                    <span class="account-card-type-badge ${badgeTypeClass}">${badgeLabel}</span>
                </div>
                <div class="account-card-balance" style="${isDollar ? 'color:#15803d;' : ''}">${balanceFormatted}</div>
                ${acc.is_adjusted ? `<div class="adjusted-tag" title="Sabab: ${acc.reason || 'Korrektirovka'}">✏️ To'g'rilangan</div>` : ''}
            </div>
        `;
    }).join('');

    if (gridModal) gridModal.innerHTML = htmlContent;
    if (gridPage) gridPage.innerHTML = htmlContent;
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
        const isDollar = t.account_type === 'dollar' || t.is_usd === true;
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

        let amountFormatted = '';
        if (t.is_usd || t.account_type === 'dollar' || (t.usd_amount && t.usd_amount > 0)) {
            const usdAmt = t.usd_amount || (t.amount ? t.amount / (t.usd_rate || 12800) : 0);
            const usdStr = (Number(usdAmt) || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            const uzsStr = formatMoney(t.amount);
            const rateStr = t.usd_rate ? `kurs: ${formatNumber(t.usd_rate)}` : '';
            amountFormatted = `
                <div style="display:inline-flex; flex-direction:column; align-items:flex-end; vertical-align:middle;">
                    <span style="font-size:14px; font-weight:800;">${sign} $${usdStr}</span>
                    <span style="font-size:11px; font-weight:500; opacity:0.8; color:var(--text-light);">${uzsStr}${rateStr ? ' (' + rateStr + ')' : ''}</span>
                </div>
            `;
        } else {
            amountFormatted = `<span>${sign} ${formatMoney(t.amount)}</span>`;
        }

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
                    ${amountFormatted}
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
    const usdBtn = document.getElementById('expTypeUsd');
    if (usdBtn) usdBtn.classList.toggle('active', type === 'usd');
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
        const resp = await apiFetch('/customers?limit=2000');
        if (resp && resp.success && resp.data) {
            customersList = Array.isArray(resp.data) ? resp.data : (resp.data.customers || []);
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
    document.getElementById('payUsdAmount').value = '';
    document.getElementById('payDescription').value = '';
    
    // Populate Kirim Selects
    const cardSelect = document.getElementById('payCardAccountSelect');
    const usdSelect = document.getElementById('payUsdAccountSelect');
    
    if (cardSelect) {
        const uzsBankOnly = orgAccounts.filter(a => a.type !== 'cash' && !a.is_dollar && a.currency !== 'USD');
        cardSelect.innerHTML = uzsBankOnly.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    }
    
    if (usdSelect) {
        const usdAccounts = orgAccounts.filter(a => a.is_dollar || a.currency === 'USD');
        usdSelect.innerHTML = usdAccounts.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    }

    updatePaymentUSDPreview();
    document.getElementById('customerPaymentModal').classList.add('active');
}

function closeCustomerPaymentModal() {
    document.getElementById('customerPaymentModal').classList.remove('active');
}

function updatePaymentUSDPreview() {
    const cash = parseAmount(document.getElementById('payCashAmount').value);
    const card = parseAmount(document.getElementById('payCardAmount').value);
    const usd = parseAmount(document.getElementById('payUsdAmount').value);
    
    const usdRate = window.currentUSDRate || 12800;
    const usdToUzs = usd * usdRate;
    const totalUzs = cash + card + usdToUzs;

    document.getElementById('payTotalPreview').textContent = formatMoney(totalUzs);
    document.getElementById('payTotalUSDPreview').textContent = `${formatUSD(totalUzs / usdRate)} USD`;
}

async function handleCustomerPaymentSubmit(event) {
    event.preventDefault();
    const customer_id = document.getElementById('payCustomerSelect').value;
    const cash_amount = parseAmount(document.getElementById('payCashAmount').value);
    const card_amount = parseAmount(document.getElementById('payCardAmount').value);
    const usd_amount = parseAmount(document.getElementById('payUsdAmount').value);
    const card_account_id = document.getElementById('payCardAccountSelect')?.value;
    const usd_account_id = document.getElementById('payUsdAccountSelect')?.value;
    const description = document.getElementById('payDescription').value;

    if (!customer_id) {
        alert("Iltimos, mijozni tanlang!");
        return;
    }

    if (cash_amount <= 0 && card_amount <= 0 && usd_amount <= 0) {
        alert("Naqd, bank yoki dollar summasidan kamida bittasini kiriting!");
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
            usd_amount: usd_amount,
            usd_rate: window.currentUSDRate || 12800.0,
            account_id: card_account_id || null,
            usd_account_id: usd_account_id || null,
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

    let tx = null;
    if (currentCashflowData && currentCashflowData.transactions) {
        tx = currentCashflowData.transactions.find(t => t.id === paymentId);
    }

    currentEditingTx = tx || { id: paymentId, doc_type: docType };

    const modal = document.getElementById('editPaymentModal');
    if (!modal) return;

    document.getElementById('editPayId').value = paymentId;
    document.getElementById('editPayDocType').value = docType || (tx && tx.doc_type) || 'cashin';

    // Sarlavha
    const typeLabel = tx ? (tx.type_name || 'To\'lov') : 'To\'lov';
    document.getElementById('editPayTitle').textContent = `✏️ ${typeLabel}ni Tahrirlash`;
    document.getElementById('editPayDocSubtitle').textContent = tx 
        ? `Hujjat: ${tx.doc_number || '—'} | Kontragent: ${tx.target_name || '—'}`
        : `ID: ${paymentId}`;

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

    await loadEditAccountsSelect((tx && (tx.account_id || (tx.account && tx.account.id))) || null);

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
        if (amtInput) amtInput.value = tx ? formatNumber(tx.amount) : '0';
    } else {
        if (usdGroup) usdGroup.style.display = 'none';
        if (accGroup) accGroup.style.display = 'none';
        if (amtInput) amtInput.value = tx ? formatNumber(tx.amount) : '0';
        if (usdInput) usdInput.value = '';
        if (rateInput) rateInput.value = formatNumber(window.currentUSDRate || 12800);
    }

    // Sana va vaqt
    const momentInput = document.getElementById('editPayMoment');
    if (tx && tx.moment) {
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

    let linkedDemandId = (tx && (tx.linked_demand_id || tx.demand_id)) || null;
    let targetCustomerName = tx ? tx.target_name : '';

    // MoySklad hujjatining o'zidan operatsiyalarni tekshirib olish (bog'lanishni 100% aniq topish)
    try {
        const fullDocResp = await apiFetch(`/payments/${docType || (tx && tx.doc_type) || 'cashin'}/${paymentId}`);
        if (fullDocResp && fullDocResp.success && fullDocResp.data) {
            const docData = fullDocResp.data;
            if (docData.agent && docData.agent.name) {
                targetCustomerName = docData.agent.name;
            }
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
        console.warn('Payment full doc fetch warning:', err);
    }

    if (targetCustomerName && targetCustomerName !== 'Xarajat' && targetCustomerName !== 'Bank xarajati') {
        try {
            const demandsResp = await apiFetch(`/demands?limit=50&offset=0&search=${encodeURIComponent(targetCustomerName)}`);
            if (demandsResp && demandsResp.data && demandsResp.data.length > 0) {
                demandsResp.data.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.id;
                    const rem = d.remaining ? ` | Qarz: ${formatMoney(d.remaining)}` : '';
                    opt.textContent = `№ ${d.name} (${d.moment ? d.moment.substring(0, 10) : ''}) — ${formatMoney(d.sum)}${rem}`;
                    if (linkedDemandId && (linkedDemandId === d.id)) {
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
        loadEditAccountsSelect(currentEditingTx?.account_id || currentEditingTx?.account?.id);
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
    const paymentId = document.getElementById('editPayId').value;
    const docType = document.getElementById('editPayDocType').value;
    const amount = parseAmount(document.getElementById('editPayAmount').value);
    const methodSelect = document.getElementById('editPayMethod') || document.getElementById('editPayCurrency');
    const method = methodSelect ? methodSelect.value : 'cash';
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

    if (method === 'usd' || method === 'USD') {
        const usdAmount = parseAmount(document.getElementById('editPayUsdAmount').value);
        const usdRate = parseAmount(document.getElementById('editPayUsdRate').value) || (window.currentUSDRate || 12800);
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



// ================= BIRLASHGAN TEZKOR TO'LOV PANELI (DRAWER) =================
let currentDrawerTab = 'income'; // 'income' | 'expense'
let currentDrawerExpenseType = 'cash'; // 'cash' | 'card' | 'usd'

function openQuickPayDrawer(tab = 'income', customerId = null, customerName = null, currentBalance = null) {
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

    // Default rates
    const rateInput = document.getElementById('drawerPayUsdRate');
    if (rateInput) rateInput.value = formatNumber(window.currentUSDRate || 12800);

    switchDrawerTab(tab);
    backdrop.classList.add('active');
    drawer.classList.add('active');

    if (customerId) {
        selectDrawerCust(customerId, customerName || '');
        setTimeout(() => {
            document.getElementById('drawerPayCash')?.focus();
        }, 220);
    } else {
        setTimeout(() => {
            if (tab === 'income') {
                document.getElementById('drawerIncomeCustomerSearch')?.focus();
            } else {
                document.getElementById('drawerExpAmount')?.focus();
            }
        }, 200);
    }
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
    const usdHidden = document.getElementById('drawerPayUsdAccount');
    const expItemSel = document.getElementById('drawerExpItemSelect');

    const uzsCards = getCardAccountsList();
    const usdAccounts = getDollarAccountsList();

    if (cardSelect) {
        cardSelect.innerHTML = uzsCards.map(a => `<option value="${a.id}">💳 ${a.name.replace(/^[🏦💳💵💲]\s*/, '')}</option>`).join('');
        if (uzsCards.length > 0) cardSelect.value = uzsCards[0].id;
    }
    if (usdHidden) {
        usdHidden.value = usdAccounts[0]?.id || 'usd_default';
    }

    // Populate expense items dropdown
    if (expItemSel && expenseItems && expenseItems.length > 0) {
        expItemSel.innerHTML = '<option value="">Toifani tanlang...</option>' +
            expenseItems.map(item => `<option value="${item.id}">🏷️ ${item.name}</option>`).join('');
    }

    // Render quick expense chips matching real DB items
    renderDrawerExpenseChips();
}

const EXPENSE_ICONS = {
    'аренда': '🏢',
    'зарплата': '👥',
    'питание': '🍲',
    'маркетинг и реклама': '📢',
    'маркетинг': '📢',
    'реклама': '📢',
    'логистика': '📦',
    'коммуналка': '💡',
    'закупка товаров': '🛒',
    'закупка': '🛒',
    'дивидент': '💰',
    'налоги и сборы': '🏛️',
    'налоги': '🏛️',
    'перемещение': '🔄',
    'списания': '🗑️',
    'возврат': '↩️'
};

function renderDrawerExpenseChips() {
    const container = document.getElementById('drawerExpenseChipsContainer');
    if (!container || !expenseItems || expenseItems.length === 0) return;

    container.innerHTML = expenseItems.map(item => {
        const lower = (item.name || '').toLowerCase().trim();
        const icon = EXPENSE_ICONS[lower] || '🏷️';
        const cleanName = (item.name || '').replace(/'/g, "\\'");
        return `
            <button type="button" class="drawer-chip-btn" id="chip_exp_${item.id}" onclick="selectDrawerExpenseItemQuick('${item.id}', '${cleanName}')">
                ${icon} ${item.name}
            </button>
        `;
    }).join('');
}

function selectDrawerExpenseItemQuick(itemId, categoryName) {
    const select = document.getElementById('drawerExpItemSelect');
    if (select) {
        select.value = itemId;
    }
    highlightActiveExpenseChip(itemId);
}

function highlightActiveExpenseChip(itemId) {
    const chips = document.querySelectorAll('#drawerExpenseChipsContainer .drawer-chip-btn');
    chips.forEach(btn => {
        if (btn.id === `chip_exp_${itemId}`) {
            btn.classList.add('active');
            btn.style.background = '#0284c7';
            btn.style.color = '#ffffff';
            btn.style.borderColor = '#0284c7';
            btn.style.fontWeight = '700';
        } else {
            btn.classList.remove('active');
            btn.style.background = '';
            btn.style.color = '';
            btn.style.borderColor = '';
            btn.style.fontWeight = '';
        }
    });
}

function setDrawerExpenseType(type) {
    currentDrawerExpenseType = type;
    const btnCash = document.getElementById('drawerExpTypeCash');
    const btnCard = document.getElementById('drawerExpTypeCard');
    const btnUsd = document.getElementById('drawerExpTypeUsd');
    if (btnCash) btnCash.classList.toggle('active', type === 'cash');
    if (btnCard) btnCard.classList.toggle('active', type === 'card');
    if (btnUsd) btnUsd.classList.toggle('active', type === 'usd');

    const accGroup = document.getElementById('drawerExpAccountGroup');
    const accSelect = document.getElementById('drawerExpAccountSelect');
    if (!accSelect) return;

    if (type === 'cash') {
        if (accGroup) accGroup.style.display = 'none';
        const cashAccs = orgAccounts.filter(a => a.type === 'cash' || (!a.is_dollar && a.currency === 'UZS' && (a.name || '').toLowerCase().includes('naqd')));
        const displayAccs = cashAccs.length > 0 ? cashAccs : [{ id: 'cash_default', name: '💵 Asosiy Naqd Kassa (UZS)' }];
        accSelect.innerHTML = displayAccs.map(a => `<option value="${a.id}">💵 ${a.name}</option>`).join('');
        accSelect.value = displayAccs[0].id;
    } else if (type === 'card') {
        if (accGroup) accGroup.style.display = 'block';
        const cardAccs = getCardAccountsList();
        const displayAccs = cardAccs.length > 0 ? cardAccs : orgAccounts.filter(a => a.type !== 'cash' && !a.is_dollar);
        accSelect.innerHTML = displayAccs.map(a => `<option value="${a.id}">💳 ${a.name}</option>`).join('');
        if (displayAccs.length > 0) accSelect.value = displayAccs[0].id;
    } else if (type === 'usd') {
        if (accGroup) accGroup.style.display = 'block';
        const usdAccs = getDollarAccountsList();
        const displayAccs = usdAccs.length > 0 ? usdAccs : orgAccounts.filter(a => a.is_dollar || a.currency === 'USD');
        accSelect.innerHTML = displayAccs.map(a => `<option value="${a.id}">💲 ${a.name}</option>`).join('');
        if (displayAccs.length > 0) accSelect.value = displayAccs[0].id;
    }
    updateDrawerExpUsdPreview();
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
                <div onclick="selectDrawerCust('${c.id}', '${(c.name || '').replace(/'/g, "\\'")}')" style="padding:7px 12px; cursor:pointer; font-size:12.5px; border-bottom:1px solid #f1f5f9; display:flex; justify-content:space-between; align-items:center; transition:background 0.15s;" onmouseover="this.style.background='#f0f9ff'" onmouseout="this.style.background='transparent'">
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

// ================= UNIVERSAL QUICK-PAY DRAWER FIFO STATE & LOGIC =================
let drawerUnpaidDemandsData = [];
let drawerDemandAllocations = {};
let drawerManualPinnedDemands = {};
let drawerIsFifoAuto = true;
let drawerCurrentCustomerDebt = 0;

function getDrawerPaymentTotalUzs() {
    const cash = parseAmount(document.getElementById('drawerPayCash')?.value);
    const card = parseAmount(document.getElementById('drawerPayCard')?.value);
    const usd = parseAmount(document.getElementById('drawerPayUsd')?.value);
    const rate = parseAmount(document.getElementById('drawerPayUsdRate')?.value) || (window.currentUSDRate || 12800);
    return Math.round(cash + card + (usd * rate));
}

function updateDrawerTotals() {
    const cash = parseAmount(document.getElementById('drawerPayCash')?.value);
    const card = parseAmount(document.getElementById('drawerPayCard')?.value);
    const usd = parseAmount(document.getElementById('drawerPayUsd')?.value);
    const rate = parseAmount(document.getElementById('drawerPayUsdRate')?.value) || (window.currentUSDRate || 12800);

    const usdEquiv = Math.round(usd * rate);
    const totalUzs = Math.round(cash + card + usdEquiv);

    const equivEl = document.getElementById('drawerPayUsdEquiv');
    if (equivEl) equivEl.textContent = `~ ${formatMoney(usdEquiv)}`;

    const totalEl = document.getElementById('drawerIncomeTotalUzs');
    const totalUsdEl = document.getElementById('drawerIncomeTotalUsd');
    if (totalEl) totalEl.textContent = formatMoney(totalUzs);
    if (totalUsdEl) totalUsdEl.textContent = `$${(totalUzs / rate).toFixed(2)} USD`;

    const cardGroup = document.getElementById('drawerPayCardAccGroup');
    if (cardGroup) cardGroup.style.display = card > 0 ? 'block' : 'none';

    drawerRecalculateFifo(false);
}

function drawerRecalculateFifo(shouldRenderDom = false, activeInputDemandId = null) {
    const totalPayment = getDrawerPaymentTotalUzs();
    const isLinkEnabled = document.getElementById('drawerLinkDemandsToggle')?.checked !== false;

    if (!isLinkEnabled || !drawerUnpaidDemandsData || drawerUnpaidDemandsData.length === 0) {
        drawerDemandAllocations = {};
        if (shouldRenderDom) drawerRenderFifoDemandsList();
        else drawerUpdateFifoDom(activeInputDemandId);
        return;
    }

    if (drawerIsFifoAuto) {
        drawerDemandAllocations = {};
        let budget = totalPayment;
        for (const d of drawerUnpaidDemandsData) {
            const rem = Math.max(0, d.remaining || 0);
            if (budget <= 0.01) {
                drawerDemandAllocations[d.id] = 0;
            } else {
                const alloc = Math.min(budget, rem);
                drawerDemandAllocations[d.id] = alloc;
                budget -= alloc;
            }
        }
    } else {
        // Qo'lda kiritilgan rejim
        let pinnedSum = 0;
        for (const [did, val] of Object.entries(drawerManualPinnedDemands)) {
            pinnedSum += val;
            drawerDemandAllocations[did] = val;
        }

        let remainingBudget = Math.max(0, totalPayment - pinnedSum);
        for (const d of drawerUnpaidDemandsData) {
            if (drawerManualPinnedDemands[d.id] === undefined) {
                const rem = Math.max(0, d.remaining || 0);
                if (remainingBudget <= 0.01) {
                    drawerDemandAllocations[d.id] = 0;
                } else {
                    const alloc = Math.min(remainingBudget, rem);
                    drawerDemandAllocations[d.id] = alloc;
                    remainingBudget -= alloc;
                }
            }
        }
    }

    if (shouldRenderDom) {
        drawerRenderFifoDemandsList();
    } else {
        drawerUpdateFifoDom(activeInputDemandId);
    }
}

function drawerRenderFifoDemandsList() {
    const container = document.getElementById('drawerUnpaidDemandsList');
    if (!container) return;

    if (!drawerUnpaidDemandsData || drawerUnpaidDemandsData.length === 0) {
        container.innerHTML = '<div style="color:#64748b; padding:20px 10px; text-align:center;">Mijozning qarzdor sotuvlari mavjud emas (barcha sotuvlar to\'langan)</div>';
        drawerUpdateFifoSummaryBar();
        return;
    }

    let html = '';
    drawerUnpaidDemandsData.forEach((d, idx) => {
        const alloc = drawerDemandAllocations[d.id] || 0;
        const isFullyPaid = alloc >= (d.remaining - 0.01);
        const isPartial = alloc > 0.01 && !isFullyPaid;
        const cardClass = isFullyPaid ? 'demand-card fully-paid' : (isPartial ? 'demand-card partial-paid' : 'demand-card unpaid');

        let badgeHtml = `<span class="demand-badge unpaid">Bog'lanmaydi ⭕</span>`;
        if (isFullyPaid) {
            badgeHtml = `<span class="demand-badge fully-paid">To'liq yopiladi ✅</span>`;
        } else if (isPartial) {
            badgeHtml = `<span class="demand-badge partial-paid">Qisman: ${formatMoney(alloc)} ⏳</span>`;
        }

        const formattedAlloc = alloc > 0 ? formatNumber(Math.round(alloc)) : '0';

        html += `
            <div class="${cardClass}" id="drawer_demand_card_${d.id}">
                <!-- Qator 1: Hujjat raqami, sana va solo tugma -->
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <input type="checkbox" id="drawer_demand_chk_${d.id}" ${alloc > 0.01 ? 'checked' : ''} onchange="drawerToggleDemandLink('${d.id}')" style="cursor:pointer; width:16px; height:16px;">
                        <strong style="color:var(--primary); font-size:13px;">Sotuv № ${d.name}</strong>
                        <span style="color:#64748b; font-size:11.5px; font-weight:500;">📅 ${d.moment ? d.moment.substring(0, 10) : ''}</span>
                    </div>
                    <button type="button" class="btn-solo-demand" onclick="drawerQuickSetDemandAllocation('${d.id}', 'solo')" title="Faqat ushbu sotuv qarzini yopish">
                        ⚡ Faqat shuni yopish
                    </button>
                </div>

                <!-- Qator 2: Jami sotuv va Qoldiq qarz summalari -->
                <div style="display:flex; justify-content:space-between; font-size:12px; color:#475569; background:rgba(0,0,0,0.02); padding:4px 8px; border-radius:6px;">
                    <span>Jami sotuv: <strong>${formatMoney(d.sum)}</strong></span>
                    <span>Qoldiq qarz: <strong style="color:#dc2626; font-size:12.5px;">${formatMoney(d.remaining)}</strong></span>
                </div>

                <!-- Qator 3: Taqsimlash holati va Bog'lanadigan summa kiritish -->
                <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; margin-top:2px;">
                    <div id="drawer_demand_badge_${d.id}">${badgeHtml}</div>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span style="font-size:11.5px; font-weight:600; color:#475569;">Bog'lanadi:</span>
                        <input type="text" inputmode="numeric" id="drawer_demand_alloc_${d.id}" value="${formattedAlloc}" class="form-control" style="width:130px; padding:5px 8px; font-size:13px; font-weight:800; text-align:right; border-color:#0284c7;" oninput="drawerHandleManualDemandInput('${d.id}', this.value)">
                        <span style="font-size:11.5px; color:#64748b;">so'm</span>
                        <button type="button" onclick="drawerQuickSetDemandAllocation('${d.id}', 'zero')" title="Bog'lamaslik" style="border:none; background:transparent; cursor:pointer; font-size:13px; color:#dc2626; padding:0 2px;">⭕</button>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
    drawerUpdateFifoSummaryBar();
}

function drawerUpdateFifoDom(activeInputDemandId = null) {
    const list = document.getElementById('drawerUnpaidDemandsList');
    if (!list || !list.children.length || list.innerText.includes('yuklanmoqda') || list.innerText.includes('chiqadi')) {
        drawerRenderFifoDemandsList();
        return;
    }

    for (const d of drawerUnpaidDemandsData) {
        const alloc = drawerDemandAllocations[d.id] || 0;
        const isFullyPaid = alloc >= (d.remaining - 0.01);
        const isPartial = alloc > 0.01 && !isFullyPaid;

        if (d.id !== activeInputDemandId) {
            const inputEl = document.getElementById(`drawer_demand_alloc_${d.id}`);
            if (inputEl) {
                const formatted = alloc > 0 ? formatNumber(Math.round(alloc)) : '0';
                if (inputEl.value !== formatted) {
                    inputEl.value = formatted;
                }
            }
        }

        const chkEl = document.getElementById(`drawer_demand_chk_${d.id}`);
        if (chkEl) chkEl.checked = alloc > 0.01;

        const badgeEl = document.getElementById(`drawer_demand_badge_${d.id}`);
        const cardEl = document.getElementById(`drawer_demand_card_${d.id}`);
        if (badgeEl && cardEl) {
            if (isFullyPaid) {
                badgeEl.innerHTML = `<span class="demand-badge fully-paid">To'liq yopiladi ✅</span>`;
                cardEl.className = 'demand-card fully-paid';
            } else if (isPartial) {
                badgeEl.innerHTML = `<span class="demand-badge partial-paid">Qisman: ${formatMoney(alloc)} ⏳</span>`;
                cardEl.className = 'demand-card partial-paid';
            } else {
                badgeEl.innerHTML = `<span class="demand-badge unpaid">Bog'lanmaydi ⭕</span>`;
                cardEl.className = 'demand-card unpaid';
            }
        }
    }

    drawerUpdateFifoSummaryBar();
}

function drawerUpdateFifoSummaryBar() {
    const bar = document.getElementById('drawerFifoSummaryBar');
    if (!bar) return;

    let totalAllocated = 0;
    let totalDemandsDebt = 0;
    const totalPayment = getDrawerPaymentTotalUzs();

    for (const d of drawerUnpaidDemandsData) {
        totalAllocated += (drawerDemandAllocations[d.id] || 0);
        totalDemandsDebt += (d.remaining || 0);
    }

    bar.style.display = 'flex';
    const allocEl = document.getElementById('drawerFifoTotalAllocatedText');
    if (allocEl) allocEl.textContent = formatMoney(totalAllocated);

    const remDebt = Math.max(0, totalDemandsDebt - totalAllocated);
    const remEl = document.getElementById('drawerFifoRemainingDebtText');
    if (remEl) remEl.textContent = formatMoney(remDebt);

    const excessEl = document.getElementById('drawerFifoExcessText');
    if (excessEl) {
        if (totalPayment > totalAllocated) {
            excessEl.style.display = 'block';
            excessEl.innerHTML = `Ortiqcha (avans): <strong>${formatMoney(totalPayment - totalAllocated)}</strong>`;
        } else {
            excessEl.style.display = 'none';
        }
    }
}

function drawerHandleManualDemandInput(demandId, rawValue) {
    drawerIsFifoAuto = false;
    const badge = document.getElementById('drawerFifoModeBadge');
    if (badge) {
        badge.textContent = '✍️ Qo\'lda taqsimlash';
        badge.className = 'fifo-mode-badge manual';
    }

    const val = parseAmount(rawValue);
    const demand = drawerUnpaidDemandsData.find(d => d.id === demandId);
    const maxAlloc = demand ? demand.remaining : val;
    const cleanVal = Math.min(val, maxAlloc);

    drawerManualPinnedDemands[demandId] = cleanVal;
    drawerRecalculateFifo(false, demandId);
}

function drawerQuickSetDemandAllocation(demandId, type) {
    const demand = drawerUnpaidDemandsData.find(d => d.id === demandId);
    if (!demand) return;

    if (type === 'solo') {
        drawerIsFifoAuto = false;
        drawerManualPinnedDemands = {};
        drawerManualPinnedDemands[demandId] = demand.remaining;

        const cashInput = document.getElementById('drawerPayCash');
        const cardInput = document.getElementById('drawerPayCard');
        const usdInput = document.getElementById('drawerPayUsd');
        if (cashInput) cashInput.value = formatNumber(Math.round(demand.remaining));
        if (cardInput) cardInput.value = '0';
        if (usdInput) usdInput.value = '0.00';

        const badge = document.getElementById('drawerFifoModeBadge');
        if (badge) {
            badge.textContent = `🎯 №${demand.name} yopiladi`;
            badge.className = 'fifo-mode-badge solo';
        }

        updateDrawerTotals();
    } else if (type === 'zero') {
        drawerIsFifoAuto = false;
        drawerManualPinnedDemands[demandId] = 0;
        const badge = document.getElementById('drawerFifoModeBadge');
        if (badge) {
            badge.textContent = '✍️ Qo\'lda taqsimlash';
            badge.className = 'fifo-mode-badge manual';
        }
        drawerRecalculateFifo(false);
    }
}

function drawerToggleDemandLink(demandId) {
    const chk = document.getElementById(`drawer_demand_chk_${demandId}`);
    const demand = drawerUnpaidDemandsData.find(d => d.id === demandId);
    if (!demand) return;

    drawerIsFifoAuto = false;
    const badge = document.getElementById('drawerFifoModeBadge');
    if (badge) {
        badge.textContent = '✍️ Qo\'lda taqsimlash';
        badge.className = 'fifo-mode-badge manual';
    }

    if (chk && !chk.checked) {
        drawerManualPinnedDemands[demandId] = 0;
    } else {
        const totalPayment = getDrawerPaymentTotalUzs();
        let alreadyAlloc = 0;
        for (const [did, amt] of Object.entries(drawerManualPinnedDemands)) {
            if (did !== demandId) alreadyAlloc += amt;
        }
        const avail = Math.max(0, totalPayment - alreadyAlloc);
        drawerManualPinnedDemands[demandId] = Math.min(avail, demand.remaining);
    }

    drawerRecalculateFifo(false);
}

function drawerResetToAutoFifo() {
    drawerIsFifoAuto = true;
    drawerManualPinnedDemands = {};
    const badge = document.getElementById('drawerFifoModeBadge');
    if (badge) {
        badge.textContent = '⚡ Avto-taqsimlash';
        badge.className = 'fifo-mode-badge auto';
    }
    drawerRecalculateFifo(true);
}

function drawerHandleLinkDemandsToggle() {
    drawerRecalculateFifo(true);
}

function drawerFillTotalDebtAmount() {
    if (drawerCurrentCustomerDebt <= 0) return;
    const cashInput = document.getElementById('drawerPayCash');
    if (cashInput) {
        cashInput.value = formatNumber(Math.round(drawerCurrentCustomerDebt));
        updateDrawerTotals();
    }
}

async function loadCustomerUnpaidDemandsForDrawer(customerId, customerName) {
    const loading = document.getElementById('drawerUnpaidDemandsLoading');
    const container = document.getElementById('drawerUnpaidDemandsList');
    if (loading) loading.style.display = 'block';
    if (container) container.innerHTML = '<div style="color:#64748b; padding:20px; text-align:center;">⏳ Ochiq sotuvlar qidirilmoqda...</div>';

    drawerIsFifoAuto = true;
    drawerDemandAllocations = {};
    drawerManualPinnedDemands = {};
    drawerUnpaidDemandsData = [];

    const badge = document.getElementById('drawerFifoModeBadge');
    if (badge) {
        badge.textContent = '⚡ Avto-taqsimlash';
        badge.className = 'fifo-mode-badge auto';
    }

    try {
        const resp = await apiFetch(`/customers/${customerId}/unpaid-demands`);
        if (loading) loading.style.display = 'none';
        if (resp && resp.success && Array.isArray(resp.data)) {
            drawerUnpaidDemandsData = resp.data;
        } else {
            drawerUnpaidDemandsData = [];
        }
    } catch (e) {
        if (loading) loading.style.display = 'none';
        console.warn('Unpaid demands load error:', e);
        drawerUnpaidDemandsData = [];
    }

    drawerRecalculateFifo(true);
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
                <div onclick="selectDrawerCust('${c.id}', '${(c.name || '').replace(/'/g, "\\'")}')" style="padding:8px 12px; cursor:pointer; font-size:12.5px; border-bottom:1px solid #f1f5f9; display:flex; justify-content:space-between; align-items:center; transition:background 0.15s;" onmouseover="this.style.background='#f0f9ff'" onmouseout="this.style.background='transparent'">
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

    // Fetch customer balance
    let bal = 0;
    try {
        const bResp = await apiFetch(`/payments/balance/${id}`);
        if (bResp && bResp.success && bResp.data) {
            bal = bResp.data.balance || 0;
        }
    } catch (e) {}

    drawerCurrentCustomerDebt = bal > 0.01 ? bal : 0;

    const banner = document.getElementById('drawerCustDebtBanner');
    const debtVal = document.getElementById('drawerCustDebtValue');
    const fillBtn = document.getElementById('drawerBtnFillAllDebt');
    if (banner && debtVal) {
        banner.style.display = 'flex';
        const isDebt = bal > 0;
        debtVal.textContent = isDebt ? `Qarzi: ${formatMoney(bal)}` : (bal < 0 ? `Haqi: ${formatMoney(Math.abs(bal))}` : "0 so'm (Hisobi teng)");
        debtVal.style.color = isDebt ? '#ef4444' : (bal < 0 ? '#16a34a' : '#64748b');
        if (fillBtn) fillBtn.style.display = isDebt ? 'inline-block' : 'none';
    }

    // Load unpaid demands for FIFO allocation in Drawer
    await loadCustomerUnpaidDemandsForDrawer(id, name);
}

// --- Submit Handlers ---
async function handleDrawerIncomeSubmit(e) {
    e.preventDefault();
    const custId = document.getElementById('drawerIncomeCustomerId')?.value;
    const cash = parseAmount(document.getElementById('drawerPayCash')?.value);
    const card = parseAmount(document.getElementById('drawerPayCard')?.value);
    const usd = parseAmount(document.getElementById('drawerPayUsd')?.value);
    const usdRate = parseAmount(document.getElementById('drawerPayUsdRate')?.value) || (window.currentUSDRate || 12800.0);
    const cardAcc = document.getElementById('drawerPayCardAccount')?.value;
    const usdAcc = document.getElementById('drawerPayUsdAccount')?.value;
    const moment = document.getElementById('drawerIncomeMoment')?.value;
    const desc = document.getElementById('drawerIncomeDesc')?.value?.trim() || "Mijozdan to'lov";

    const totalUzs = getDrawerPaymentTotalUzs();

    if (!custId) {
        alert("Iltimos, avval mijozni tanlang!");
        return;
    }
    if (totalUzs <= 0) {
        alert("Naqd, karta yoki dollar summasidan kamida bittasini kiriting!");
        return;
    }

    // Bog'lanuvchi sotuvlar (FIFO yoki qo'lda belgilangan)
    const isLinkingChecked = document.getElementById('drawerLinkDemandsToggle')?.checked !== false;
    const linkedDemands = [];
    const selectedDemandIds = [];

    if (isLinkingChecked) {
        for (const [did, amt] of Object.entries(drawerDemandAllocations)) {
            if (amt > 0.01) {
                linkedDemands.push({ demand_id: did, amount: amt });
                selectedDemandIds.push(did);
            }
        }
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
            usd_rate: usdRate,
            account_id: cardAcc || null,
            usd_account_id: usdAcc || null,
            linked_demands: linkedDemands.length > 0 ? linkedDemands : null,
            demand_ids: selectedDemandIds.length > 0 ? selectedDemandIds : null,
            auto_fifo: drawerIsFifoAuto,
            description: desc,
            moment: moment ? (moment.replace('T', ' ') + ':00') : undefined
        };

        const resp = await apiFetch('/payments/customer-payment', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        if (resp && resp.success) {
            const linkedCount = linkedDemands.length;
            const linkMsg = linkedCount > 0 ? ` (${linkedCount} ta sotuvga bog'landi)` : '';
            alert(`✅ Kirim to'lov muvaffaqiyatli qabul qilindi! Jami: ${formatMoney(totalUzs)}${linkMsg}`);
            closeQuickPayDrawer();
            if (typeof loadCashflow === 'function') await loadCashflow();
            if (typeof loadCustomers === 'function') await loadCustomers();
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

document.addEventListener('DOMContentLoaded', () => {
    const expSelect = document.getElementById('drawerExpItemSelect');
    if (expSelect) {
        expSelect.addEventListener('change', (e) => {
            highlightActiveExpenseChip(e.target.value);
        });
    }
});
