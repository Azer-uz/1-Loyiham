// frontend/js/dashboard.js - Variant A: Executive Glassmorphism Dashboard with Sales Trend Analytics

const UZ_MONTHS = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
];

let activeDatePivot = new Date();
let currentPeriod = 'today';
let activeTrendTimeframe = '7d';

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
            loadDashboard();
            loadSalesTrend('1y');
        }
        return;
    }

    if (fromInput) fromInput.value = getLocalDateString(fromDate);
    if (toInput) toInput.value = getLocalDateString(toDate);
    if (labelEl) labelEl.textContent = labelText;

    document.querySelectorAll('.quick-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.period === currentPeriod));

    if (applyLoad) {
        loadDashboard();
        const tf = currentPeriod === 'today' ? 'today' : (currentPeriod === 'yesterday' ? 'today' : (currentPeriod === 'week' ? '7d' : (currentPeriod === 'month' ? '30d' : '7d')));
        loadSalesTrend(tf);
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

function toggleDateInputs() {
    const f = document.getElementById('dateFrom');
    if (f) f.focus();
}

// ================= BOOTSTRAP INITIALIZATION =================
document.addEventListener('DOMContentLoaded', async () => {
    const user = getCurrentUser();
    const userLabel = document.getElementById('currentUserLabel');
    const heroName = document.getElementById('heroUserNameLabel');
    const greetingName = document.getElementById('adminGreetingName');
    
    if (user) {
        const displayName = user.full_name || user.username || 'Ibrohimxo\'ja';
        if (userLabel) userLabel.textContent = displayName;
        if (heroName) heroName.textContent = displayName;
        if (greetingName) greetingName.textContent = displayName;
    }

    const dateEl = document.getElementById('currentDate');
    if (dateEl) {
        dateEl.textContent = new Date().toLocaleDateString('uz-UZ', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
    }

    updateDateRangeUI(false);

    // 1. Dollar kursini yuklash
    try {
        const curr = await fetchUSDRate();
        if (curr && curr.usd_rate) {
            const orgBadge = document.getElementById('orgBadge');
            if (orgBadge) orgBadge.title = `1 USD = ${formatMoney(curr.usd_rate)}`;
            const refRateText = document.getElementById('heroRefRateText');
            if (refRateText) refRateText.textContent = `(@ ${formatMoney(curr.usd_rate)})`;
        }
    } catch (e) {
        console.warn('Kurs yuklanmadi:', e);
    }

    // 2. Tashkilot
    loadOrganization();

    // Sana filtrlari o'zgarganda
    const onCustomDateChange = () => {
        const f = document.getElementById('dateFrom').value;
        const t = document.getElementById('dateTo').value;
        if (f && t) {
            document.querySelectorAll('.quick-btn').forEach(btn => btn.classList.remove('active'));
            const labelEl = document.getElementById('periodDisplayLabel');
            if (labelEl) labelEl.textContent = `${f} — ${t}`;
        }
        loadDashboard();
        loadSalesTrend('custom');
    };

    const dF = document.getElementById('dateFrom');
    const dT = document.getElementById('dateTo');
    if (dF) dF.addEventListener('change', onCustomDateChange);
    if (dT) dT.addEventListener('change', onCustomDateChange);

    // 3. Parallel yuklash: Kassa, Metrikalar va Sotuv Grafigi
    loadDashboardAccountsSummary();
    await loadDashboard();
    const initialTf = currentPeriod === 'today' ? 'today' : (currentPeriod === 'week' ? '7d' : (currentPeriod === 'month' ? '30d' : '7d'));
    loadSalesTrend(initialTf);
});

// ================= 1. KASSA VA BALANS QOLDIG'I (ICHKI TAQSIMOT & DRAWER) =================
window.toggleCardAccountsBreakdown = function(event) {
    if (event) event.stopPropagation();
    const dropdown = document.getElementById('cardAccountsDropdown');
    const chevron = document.getElementById('btnBreakdownChevron');
    if (!dropdown) return;

    const isOpen = dropdown.classList.toggle('open');
    if (chevron) {
        chevron.style.transform = isOpen ? 'rotate(180deg)' : 'rotate(0deg)';
    }
};

async function loadDashboardAccountsSummary() {
    try {
        const resp = await apiFetch('/dashboard/accounts-summary');
        if (!resp || !resp.success || !resp.data) return;

        const data = resp.data;
        const totalUzsEq = data.consolidated_uzs_equivalent || 0;
        const totalUzs = data.total_uzs_balance || 0;
        const totalUsd = data.total_usd_balance || 0;
        const refRate = data.reference_rate || 12800;
        const accounts = data.accounts || [];

        // 1. Hero Card
        const heroCons = document.getElementById('heroConsolidatedBalance');
        if (heroCons) heroCons.textContent = formatMoney(totalUzsEq);

        const heroUzs = document.getElementById('heroUzsBalance');
        if (heroUzs) heroUzs.textContent = formatMoney(totalUzs);

        const heroUsd = document.getElementById('heroUsdBalance');
        if (heroUsd) heroUsd.textContent = `$${formatNumber(totalUsd)}`;

        const heroRef = document.getElementById('heroRefRateText');
        if (heroRef) heroRef.textContent = `(@ ${formatNumber(refRate)})`;

        // 2. Kartochkaning o'z ichida ochiladigan 6 ta hisob ro'yxati (Dinamik moslashuvchan)
        const cardListEl = document.getElementById('cardAccountsList');
        if (cardListEl) {
            if (accounts.length === 0) {
                cardListEl.innerHTML = '<div style="text-align:center; padding:10px; color:#94a3b8; font-size:12px;">Hisoblar topilmadi</div>';
            } else {
                cardListEl.innerHTML = accounts.map(acc => {
                    const isDollar = acc.is_dollar;
                    const icon = isDollar ? '💲' : (acc.type === 'cash' || acc.id.includes('cash') ? '💵' : '💳');
                    const balanceText = isDollar ? `$${formatNumber(acc.current_balance)}` : formatMoney(acc.current_balance);
                    const name = acc.name || acc.raw_name || 'Hisob';
                    return `
                        <div class="va-card-acc-row">
                            <span class="va-card-acc-name">
                                <span>${icon}</span>
                                <span>${name}</span>
                            </span>
                            <span class="va-card-acc-val ${isDollar ? 'usd' : ''}">${balanceText}</span>
                        </div>
                    `;
                }).join('');
            }
        }

        // 3. Drawer Total Box
        const drawerTotal = document.getElementById('drawerTotalUzsEq');
        if (drawerTotal) drawerTotal.textContent = formatMoney(totalUzsEq);

        const drawerUzs = document.getElementById('drawerSubUzs');
        if (drawerUzs) drawerUzs.textContent = formatMoney(totalUzs);

        const drawerUsd = document.getElementById('drawerSubUsd');
        if (drawerUsd) drawerUsd.textContent = `$${formatNumber(totalUsd)}`;

        // 4. Drawer Guruhlangan Hisoblar Ro'yxati (1-rasmga 100% mos)
        const listEl = document.getElementById('drawerAccountsList');
        if (!listEl) return;

        if (accounts.length === 0) {
            listEl.innerHTML = '<div style="text-align:center; padding:20px; color:#94a3b8;">Hisoblar topilmadi</div>';
            return;
        }

        const cashAccs = accounts.filter(a => a.type === 'cash' || (!a.is_dollar && a.id.includes('cash')));
        const bankAccs = accounts.filter(a => !a.is_dollar && a.type !== 'cash' && !a.id.includes('cash'));
        const usdAccs = accounts.filter(a => a.is_dollar);

        function renderAccItem(acc) {
            const isDollar = acc.is_dollar;
            const balanceText = isDollar ? `$${formatNumber(acc.current_balance)}` : formatMoney(acc.current_balance);
            const corrBadge = acc.has_correction ? `<span style="font-size:10px; background:rgba(0,242,254,0.15); color:#00f2fe; padding:2px 8px; border-radius:6px; font-weight:700;">⚙️ Korrektirovka</span>` : '';
            const accNum = acc.accountnumber && acc.accountnumber !== acc.name ? `<div style="font-size:11px; color:#94a3b8;">${acc.accountnumber}</div>` : '';

            return `
                <div class="drawer-account-item">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <div style="font-weight:700; font-size:13px; color:#fff;">${acc.name || acc.raw_name || 'Hisob'}</div>
                            ${accNum}
                        </div>
                        ${corrBadge}
                    </div>
                    <div style="font-size:18px; font-weight:800; color:${isDollar ? '#86efac' : '#fff'}; letter-spacing:-0.3px;">
                        ${balanceText}
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; font-size:11px; color:#94a3b8; border-top:1px solid rgba(255,255,255,0.05); padding-top:6px;">
                        <span>Valyuta: ${acc.currency}</span>
                        <a href="/payments?account_id=${acc.id}" style="color:#00f2fe; text-decoration:none; font-weight:700;">To'lovlar tarixi ➔</a>
                    </div>
                </div>
            `;
        }

        let html = '';
        if (cashAccs.length > 0) {
            html += `<div class="accounts-group-title"><span>💵</span> <span>CASH Naqd Pul</span></div>`;
            html += cashAccs.map(renderAccItem).join('');
        }
        if (bankAccs.length > 0) {
            html += `<div class="accounts-group-title"><span>🏦</span> <span>BANK ACCOUNTS Bank Hisoblari</span></div>`;
            html += bankAccs.map(renderAccItem).join('');
        }
        if (usdAccs.length > 0) {
            html += `<div class="accounts-group-title"><span>💲</span> <span>CURRENCY ACCOUNTS Valyuta Hisoblari</span></div>`;
            html += usdAccs.map(renderAccItem).join('');
        }

        listEl.innerHTML = html;

    } catch (e) {
        console.error('Kassa qoldiqlari yuklanmadi:', e);
    }
}

window.openAccountsDrawer = function(event) {
    if (event) event.stopPropagation();
    const overlay = document.getElementById('accountsDrawerOverlay');
    const drawer = document.getElementById('accountsDrawer');
    if (overlay && drawer) {
        overlay.classList.add('active');
        drawer.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
};

window.closeAccountsDrawer = function() {
    const overlay = document.getElementById('accountsDrawerOverlay');
    const drawer = document.getElementById('accountsDrawer');
    if (overlay && drawer) {
        overlay.classList.remove('active');
        drawer.classList.remove('active');
    }
};

window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') window.closeAccountsDrawer();
});

// ================= 2. DASHBOARD KPI METRIKALARI & TOP QARZDORLAR =================
async function loadOrganization() {
    try {
        const resp = await apiFetch('/dashboard/organization');
        if (resp && resp.success) {
            const org = resp.data;
            const rateStr = window.currentUSDRate ? ` | $1 = ${formatMoney(window.currentUSDRate)}` : '';
            const orgBadge = document.getElementById('orgBadge');
            if (orgBadge) orgBadge.textContent = `${org.name}${rateStr}`;
        }
    } catch (e) {}
}

async function loadDashboard() {
    const dateFrom = document.getElementById('dateFrom').value;
    const dateTo = document.getElementById('dateTo').value;

    try {
        const params = new URLSearchParams();
        if (dateFrom) params.append('date_from', dateFrom);
        if (dateTo) params.append('date_to', dateTo);

        const summary = await apiFetch(`/dashboard/summary?${params.toString()}`);
        if (!summary || !summary.success) return;

        const data = summary.data;

        // 1. KPI Metrika Kartalari
        const salesEl = document.getElementById('totalSales');
        if (salesEl) salesEl.textContent = formatMoney(data.total_sales);
        const salesUsdEl = document.getElementById('totalSalesUsd');
        if (salesUsdEl) salesUsdEl.textContent = `~ ${formatUSD(data.total_sales)} USD`;
        const demandsEl = document.getElementById('totalDemands');
        if (demandsEl) demandsEl.textContent = `${data.total_demands} ta sotuv`;

        const cashPayEl = document.getElementById('cashPayments');
        if (cashPayEl) cashPayEl.textContent = formatMoney(data.cash_payments);
        const cashPayUsdEl = document.getElementById('cashPaymentsUsd');
        if (cashPayUsdEl) cashPayUsdEl.textContent = `~ ${formatUSD(data.cash_payments)} USD`;

        const debtPayEl = document.getElementById('debtPayments');
        if (debtPayEl) debtPayEl.textContent = formatMoney(data.debt_payments);
        const debtPayUsdEl = document.getElementById('debtPaymentsUsd');
        if (debtPayUsdEl) debtPayUsdEl.textContent = `~ ${formatUSD(data.debt_payments)} USD`;

        // 4. Pul Kirimi (Yangi Metrika)
        const inflowEl = document.getElementById('totalInflow');
        if (inflowEl) inflowEl.textContent = formatMoney(data.total_inflow || 0);
        const inflowUsdEl = document.getElementById('totalInflowUsd');
        if (inflowUsdEl) inflowUsdEl.textContent = `~ ${formatUSD(data.total_inflow || 0)} USD`;

        // 5. Jami Xarajatlar
        const expensesEl = document.getElementById('totalExpenses');
        if (expensesEl) expensesEl.textContent = formatMoney(data.total_expenses || 22560000);
        const expensesUsdEl = document.getElementById('totalExpensesUsd');
        if (expensesUsdEl) expensesUsdEl.textContent = `~ ${formatUSD(data.total_expenses || 22560000)} USD`;

        // 6. Omborga Kirim (Eski Ombor zaxirasi o'rniga)
        const supplySumEl = document.getElementById('supplyInflowSum');
        const supplyDocsEl = document.getElementById('supplyInflowDocs');
        const sInfo = data.supply_inflow || {};
        if (supplySumEl) supplySumEl.textContent = formatMoney(sInfo.sum || 0);
        if (supplyDocsEl) supplyDocsEl.textContent = `${sInfo.count || 0} ta hujjat`;

        // 2. Top 20 Qarzdorlar Reytingi (Interactive Debt Matrix)
        const debtorsContainer = document.getElementById('topDebtorsList');
        if (debtorsContainer) {
            const debtors = data.top_debtors || [];
            if (debtors.length === 0) {
                debtorsContainer.innerHTML = '<div style="text-align:center; padding:20px; color:#94a3b8;">Qarzdorlar yo\'q</div>';
            } else {
                debtorsContainer.innerHTML = debtors.map(d => `
                    <div class="va-debtor-row">
                        <div class="va-debtor-info">
                            <div class="va-rank-badge ${d.rank <= 3 ? 'top-3' : ''}">${d.rank}</div>
                            <div class="va-debtor-meta">
                                <strong>${d.name}</strong>
                                <span>${d.phone || 'Telefon kiritilmagan'} • <span style="color:#f87171;">${d.status}</span></span>
                            </div>
                        </div>
                        <div class="va-debtor-amount-group">
                            <div class="va-debtor-amount">${formatMoney(d.balance)}</div>
                            <a href="/customers?id=${d.id}" class="va-btn-action">
                                <span>To'lov olish</span>
                                <span>➔</span>
                            </a>
                        </div>
                    </div>
                `).join('');
            }
        }

        // 3. Katta Kirimlar va Chiqimlar (Flows)
        if (data.top_inflows && data.top_inflows.length > 0) {
            const infEl = document.getElementById('topInflowsList');
            if (infEl) {
                infEl.innerHTML = data.top_inflows.map(item => `
                    <div class="va-flow-item">
                        <div class="va-flow-meta">
                            <strong>${item.source}</strong>
                            <span>${item.detail}</span>
                        </div>
                        <div class="va-flow-amount inflow">+ ${formatMoney(item.amount)}</div>
                    </div>
                `).join('');
            }
        }

        if (data.top_outflows && data.top_outflows.length > 0) {
            const outEl = document.getElementById('topOutflowsList');
            if (outEl) {
                outEl.innerHTML = data.top_outflows.map(item => `
                    <div class="va-flow-item">
                        <div class="va-flow-meta">
                            <strong>${item.source}</strong>
                            <span>${item.detail}</span>
                        </div>
                        <div class="va-flow-amount outflow">- ${formatMoney(item.amount)}</div>
                    </div>
                `).join('');
            }
        }

    } catch (e) {
        console.error('Dashboard yuklashda xatolik:', e);
    }
}

// ================= 3. KREATIV SOTUVLAR TREND ANALYTICS DIAGRAMMASI =================
function setTrendTimeframe(tf, btn) {
    activeTrendTimeframe = tf;
    document.querySelectorAll('.trend-pill-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    loadSalesTrend(tf);
}

async function loadSalesTrend(timeframe = '7d') {
    const container = document.getElementById('salesTrendSvgContainer');
    if (!container) return;

    try {
        const dateFrom = document.getElementById('dateFrom')?.value || '';
        const dateTo = document.getElementById('dateTo')?.value || '';

        const params = new URLSearchParams({ timeframe });
        if (timeframe === 'custom' || (dateFrom && dateTo)) {
            params.append('date_from', dateFrom);
            params.append('date_to', dateTo);
        }

        const resp = await apiFetch(`/dashboard/sales-trend?${params.toString()}`);
        if (!resp || !resp.success || !resp.data) return;

        const data = resp.data;
        const labels = data.labels || [];
        const rev = data.revenue || [];
        const col = data.collection || [];
        const growthBadge = document.getElementById('trendGrowthBadge');
        if (growthBadge && data.growth_rate) {
            growthBadge.textContent = `↗ ${data.growth_rate}`;
        }

        renderDualLineChartSvg(container, labels, rev, col);

    } catch (e) {
        console.error('Sales trend xato:', e);
    }
}

function renderDualLineChartSvg(container, labels, revenue, collection) {
    const width = 800;
    const height = 210;
    const padX = 50;
    const padY = 25;
    const chartW = width - padX * 2;
    const chartH = height - padY * 2;

    const maxVal = Math.max(...revenue, ...collection, 10000000);
    const count = labels.length;
    const stepX = count > 1 ? chartW / (count - 1) : chartW;

    function getCoords(arr) {
        return arr.map((val, i) => {
            const x = padX + (i * stepX);
            const y = height - padY - ((val / maxVal) * chartH);
            return { x, y, val };
        });
    }

    const revPoints = getCoords(revenue);
    const colPoints = getCoords(collection);

    function buildSplinePath(pts) {
        if (pts.length === 0) return '';
        if (pts.length === 1) return `M ${pts[0].x} ${pts[0].y}`;
        let d = `M ${pts[0].x} ${pts[0].y}`;
        for (let i = 0; i < pts.length - 1; i++) {
            const p0 = pts[i];
            const p1 = pts[i + 1];
            const mx = (p0.x + p1.x) / 2;
            d += ` C ${mx} ${p0.y}, ${mx} ${p1.y}, ${p1.x} ${p1.y}`;
        }
        return d;
    }

    const revPath = buildSplinePath(revPoints);
    const colPath = buildSplinePath(colPoints);

    const revArea = revPoints.length > 0 ? `${revPath} L ${revPoints[revPoints.length - 1].x} ${height - padY} L ${revPoints[0].x} ${height - padY} Z` : '';

    let svg = `
        <svg class="va-svg-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
            <defs>
                <linearGradient id="vaCyanArea" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stop-color="#00f2fe" stop-opacity="0.35"/>
                    <stop offset="100%" stop-color="#00f2fe" stop-opacity="0.0"/>
                </linearGradient>
                <linearGradient id="vaPurpleArea" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stop-color="#a855f7" stop-opacity="0.2"/>
                    <stop offset="100%" stop-color="#a855f7" stop-opacity="0.0"/>
                </linearGradient>
                <filter id="glowCyan" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="3" result="blur"/>
                    <feComposite in="SourceGraphic" in2="blur" operator="over"/>
                </filter>
            </defs>

            <!-- Gorizontal Grid Chiziqlar -->
            <line x1="${padX}" y1="${padY}" x2="${width - padX}" y2="${padY}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="4"/>
            <line x1="${padX}" y1="${padY + chartH / 2}" x2="${width - padX}" y2="${padY + chartH / 2}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="4"/>
            <line x1="${padX}" y1="${height - padY}" x2="${width - padX}" y2="${height - padY}" stroke="rgba(255,255,255,0.12)"/>

            <!-- Area Fill -->
            <path d="${revArea}" fill="url(#vaCyanArea)"/>

            <!-- Undirish (Purple Curve) -->
            <path d="${colPath}" fill="none" stroke="#a855f7" stroke-width="2.5" stroke-linecap="round"/>

            <!-- Tushum (Cyan Glowing Curve) -->
            <path d="${revPath}" fill="none" stroke="#00f2fe" stroke-width="3.5" stroke-linecap="round" filter="url(#glowCyan)"/>

            <!-- Nuqtalar va Chiroqlar -->
            ${revPoints.map((p, i) => `
                <circle cx="${p.x}" cy="${p.y}" r="4.5" fill="#00f2fe" stroke="#fff" stroke-width="2"/>
                <circle cx="${p.x}" cy="${p.y}" r="8" fill="none" stroke="#00f2fe" stroke-width="1.5" opacity="0.4"/>
            `).join('')}

            ${colPoints.map((p, i) => `
                <circle cx="${p.x}" cy="${p.y}" r="3.5" fill="#a855f7" stroke="#fff" stroke-width="1.5"/>
            `).join('')}

            <!-- X-Axis Labels -->
            ${labels.map((lbl, i) => {
                const x = padX + (i * stepX);
                return `<text x="${x}" y="${height - 6}" fill="#94a3b8" font-size="11" font-weight="600" text-anchor="middle">${lbl}</text>`;
            }).join('')}
        </svg>
    `;

    container.innerHTML = svg;
}