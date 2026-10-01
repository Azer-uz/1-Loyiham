// frontend/js/dashboard.js - Variant A: Executive Glassmorphism Dashboard with Sales Trend Analytics

function formatCompact(val) {
    if (val >= 1_000_000_000) return (val / 1_000_000_000).toFixed(1) + ' mlrd';
    if (val >= 1_000_000) return (val / 1_000_000).toFixed(1) + ' mln';
    if (val >= 1_000) return (val / 1_000).toFixed(0) + ' ming';
    return val.toString();
}

const UZ_MONTHS = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
];

const UZ_WEEKDAYS = [
    "Yakshanba", "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"
];

let activeDatePivot = new Date();
let currentPeriod = 'today';
let activeTrendTimeframe = '7d';

function formatFullUzDate(d) {
    const day = String(d.getDate()).padStart(2, '0');
    const month = UZ_MONTHS[d.getMonth()];
    const year = d.getFullYear();
    const weekday = UZ_WEEKDAYS[d.getDay()];
    return `${weekday}, ${day}-${month} ${year}-yil`;
}

function formatPeriodDate(d) {
    const day = String(d.getDate()).padStart(2, '0');
    const month = UZ_MONTHS[d.getMonth()];
    const year = d.getFullYear();
    return `${day}-${month} ${year}`;
}

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
        labelText = `${UZ_MONTHS[month]} ${year}-yil`;
        if (navEl) navEl.style.display = 'inline-flex';
    } else if (currentPeriod === 'today') {
        fromDate = new Date(activeDatePivot.getFullYear(), activeDatePivot.getMonth(), activeDatePivot.getDate());
        toDate = new Date(activeDatePivot.getFullYear(), activeDatePivot.getMonth(), activeDatePivot.getDate());
        labelText = formatPeriodDate(fromDate);
        if (navEl) navEl.style.display = 'inline-flex';
    } else if (currentPeriod === 'yesterday') {
        fromDate = new Date(activeDatePivot.getFullYear(), activeDatePivot.getMonth(), activeDatePivot.getDate());
        toDate = new Date(activeDatePivot.getFullYear(), activeDatePivot.getMonth(), activeDatePivot.getDate());
        labelText = `Kecha (${formatPeriodDate(fromDate)})`;
        if (navEl) navEl.style.display = 'inline-flex';
    } else if (currentPeriod === 'week') {
        toDate = new Date(activeDatePivot.getFullYear(), activeDatePivot.getMonth(), activeDatePivot.getDate());
        fromDate = new Date(toDate.getTime() - 6 * 86400000);
        labelText = `${fromDate.getDate()}-${UZ_MONTHS[fromDate.getMonth()]} — ${toDate.getDate()}-${UZ_MONTHS[toDate.getMonth()]} ${toDate.getFullYear()}`;
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
        const tf = currentPeriod === 'today' ? 'today' : (currentPeriod === 'yesterday' ? 'yesterday' : (currentPeriod === 'week' ? '7d' : (currentPeriod === 'month' ? '30d' : '7d')));
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
        dateEl.textContent = formatFullUzDate(new Date());
    }

    updateDateRangeUI(false);

    // 1. Dollar kursini yuklash
    try {
        const curr = await fetchUSDRate();
        if (curr && curr.usd_rate) {
            window.currentUSDRate = curr.usd_rate;
            const refRateBadge = document.getElementById('heroRefRateBadge');
            if (refRateBadge) refRateBadge.textContent = `📈 Kurs: ${formatNumber(curr.usd_rate)} so'm`;
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

    // 3. Parallel tezkor yuklash: Kassa, Metrikalar va Sotuv Grafigi
    const initialTf = currentPeriod === 'today' ? 'today' : (currentPeriod === 'yesterday' ? 'yesterday' : (currentPeriod === 'week' ? '7d' : (currentPeriod === 'month' ? '30d' : '7d')));
    Promise.all([
        loadDashboardAccountsSummary().catch(() => null),
        loadDashboard().catch(() => null),
        loadSalesTrend(initialTf).catch(() => null)
    ]);
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

        const refRateBadge = document.getElementById('heroRefRateBadge');
        if (refRateBadge) refRateBadge.textContent = `📈 Kurs: ${formatNumber(refRate)} so'm`;

        // 2. Naqd, Karta, Dollar alohida hisoblash
        const cashAccs = accounts.filter(a => a.type === 'cash' || (!a.is_dollar && (a.id || '').includes('cash')));
        const bankAccs = accounts.filter(a => !a.is_dollar && a.type !== 'cash' && !(a.id || '').includes('cash'));
        const usdAccs = accounts.filter(a => a.is_dollar);

        const totalCash = cashAccs.reduce((s, a) => s + (a.current_balance || 0), 0);
        const totalCard = bankAccs.reduce((s, a) => s + (a.current_balance || 0), 0);

        const heroCash = document.getElementById('heroCashBalance');
        if (heroCash) heroCash.textContent = formatMoney(totalCash);

        const heroCard = document.getElementById('heroCardBalance');
        if (heroCard) heroCard.textContent = formatMoney(totalCard);

        const heroUsd = document.getElementById('heroUsdBalance');
        if (heroUsd) heroUsd.textContent = `$${formatNumber(totalUsd)}`;

        const heroUsdEquiv = document.getElementById('heroUsdEquivText');
        if (heroUsdEquiv) heroUsdEquiv.textContent = `~ ${formatMoney(totalUsd * refRate)}`;

        // 3. Inline Hisob Gridini chizish
        const inlineGrid = document.getElementById('vaAccountsInlineGrid');
        if (inlineGrid) {
            if (accounts.length === 0) {
                inlineGrid.innerHTML = '<div style="color:#94a3b8; padding:15px; grid-column:span 2; text-align:center;">Hisoblar topilmadi</div>';
            } else {
                inlineGrid.innerHTML = accounts.map(acc => {
                    const isDollar = acc.is_dollar;
                    const balVal = acc.current_balance !== undefined ? acc.current_balance : (acc.balance || 0);
                    const balanceText = isDollar ? `$${formatNumber(balVal)}` : formatMoney(balVal);
                    const subText = isDollar ? `<div style="font-size:10.5px; color:#cbd5e1; font-weight:600; opacity:0.85; margin-top:2px;">~ ${formatMoney(balVal * refRate)}</div>` : '';
                    const badgeClass = isDollar ? 'dollar' : (acc.type === 'cash' ? 'cash' : 'bank');
                    const badgeText = isDollar ? 'USD' : (acc.type === 'cash' ? 'NAQD' : 'BANK');

                    return `
                        <div class="va-inline-acc-card ${badgeClass}" onclick="location.href='/payments?account_id=${acc.id}'" title="Filtrlash uchun bosing" style="cursor:pointer;">
                            <div class="va-inline-acc-top">
                                <span class="va-inline-acc-name" title="${acc.name || acc.raw_name}">${acc.name || acc.raw_name}</span>
                                <span class="va-inline-acc-badge ${badgeClass}">${badgeText}</span>
                            </div>
                            <div class="va-inline-acc-bal ${badgeClass}">
                                ${balanceText}
                                ${subText}
                            </div>
                        </div>
                    `;
                }).join('');
            }
        }

    } catch (e) {
        console.error('Kassa qoldiqlari yuklanmadi:', e);
    }
}

window.toggleAccountsInline = function() {
    const card = document.getElementById('vaCashCard');
    const heroContainer = card ? card.closest('.va-hero-container') : null;
    const icon = document.getElementById('btnToggleAccountsIcon');
    const text = document.getElementById('btnToggleAccountsText');
    if (!card) return;

    const isExpanded = card.classList.toggle('expanded');
    if (heroContainer) {
        heroContainer.classList.toggle('accounts-expanded', isExpanded);
    }
    if (icon) icon.style.transform = isExpanded ? 'rotate(90deg)' : 'rotate(0deg)';
    if (text) text.textContent = isExpanded ? '✖ Yopish' : '📊 Hisoblar qoldig\'i';
};

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

        // 3. Katta Kirimlar va Chiqimlar (Flows - Top 10 ta, to'g'ridan to'g'ri to'lovga havola bilan)
        const infEl = document.getElementById('topInflowsList');
        if (infEl) {
            if (data.top_inflows && data.top_inflows.length > 0) {
                infEl.innerHTML = data.top_inflows.map((item, idx) => `
                    <div class="va-flow-item ${idx >= 5 ? 'va-flow-extra' : ''}" style="${idx >= 5 ? 'display:none;' : ''} cursor:pointer;" onclick="location.href='${item.link || '/payments'}'" title="Tafsilotini ko'rish va ochish">
                        <div class="va-flow-meta">
                            <strong>${item.source} ➔</strong>
                            <span>${item.detail}</span>
                        </div>
                        <div class="va-flow-amount inflow">+ ${formatMoney(item.amount)}</div>
                    </div>
                `).join('') + (data.top_inflows.length > 5 ? `
                    <button type="button" class="va-btn-show-more-flows" onclick="toggleExtraFlows(this, 'topInflowsList')">
                        Barchasini ko'rish (${data.top_inflows.length} ta) ▼
                    </button>
                ` : '');
            } else {
                infEl.innerHTML = `<div style="text-align:center; padding:32px 16px; color:#94a3b8; font-size:13px; font-weight:600;">Ushbu davrda kirim to'lovlar mavjud emas</div>`;
            }
        }

        const outEl = document.getElementById('topOutflowsList');
        if (outEl) {
            if (data.top_outflows && data.top_outflows.length > 0) {
                outEl.innerHTML = data.top_outflows.map((item, idx) => `
                    <div class="va-flow-item ${idx >= 5 ? 'va-flow-extra' : ''}" style="${idx >= 5 ? 'display:none;' : ''} cursor:pointer;" onclick="location.href='${item.link || '/payments'}'" title="Tafsilotini ko'rish">
                        <div class="va-flow-meta">
                            <strong>${item.source} ➔</strong>
                            <span>${item.detail}</span>
                        </div>
                        <div class="va-flow-amount outflow">- ${formatMoney(item.amount)}</div>
                    </div>
                `).join('') + (data.top_outflows.length > 5 ? `
                    <button type="button" class="va-btn-show-more-flows" onclick="toggleExtraFlows(this, 'topOutflowsList')">
                        Barchasini ko'rish (${data.top_outflows.length} ta) ▼
                    </button>
                ` : '');
            } else {
                outEl.innerHTML = `<div style="text-align:center; padding:32px 16px; color:#94a3b8; font-size:13px; font-weight:600;">Ushbu davrda xarajatlar mavjud emas</div>`;
            }
        }

    } catch (e) {
        console.error('Dashboard yuklashda xatolik:', e);
    }
}

window.toggleExtraFlows = function(btn, containerId) {
    const cont = document.getElementById(containerId);
    if (!cont) return;
    const extras = cont.querySelectorAll('.va-flow-extra');
    const isHidden = extras.length > 0 && extras[0].style.display === 'none';
    extras.forEach(el => {
        el.style.display = isHidden ? 'flex' : 'none';
    });
    if (btn) {
        btn.textContent = isHidden ? 'Yashirish ▲' : `Barchasini ko'rish (${extras.length + 5} ta) ▼`;
    }
};

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
        const prevRev = data.previous_revenue || [];
        const growthBadge = document.getElementById('trendGrowthBadge');
        if (growthBadge && data.growth_rate) {
            growthBadge.textContent = data.growth_rate;
            if (data.growth_rate.includes('+') || data.growth_rate.includes('↗')) {
                growthBadge.style.background = 'rgba(16,185,129,0.15)';
                growthBadge.style.color = '#10b981';
            } else if (data.growth_rate.includes('↘') || data.growth_rate.includes('-')) {
                growthBadge.style.background = 'rgba(239,68,68,0.15)';
                growthBadge.style.color = '#ef4444';
            }
        }

        const curSumEl = document.getElementById('chartCurrentPeriodSum');
        if (curSumEl) curSumEl.textContent = `Joriy: ${formatMoney(Math.round(data.total_revenue || 0))}`;

        const prevSumEl = document.getElementById('chartPrevPeriodSum');
        if (prevSumEl) prevSumEl.textContent = `Oldingi: ${formatMoney(Math.round(data.total_previous || 0))}`;

        renderDualLineChartSvg(container, labels, rev, prevRev);

    } catch (e) {
        console.error('Sales trend xato:', e);
    }
}

function renderDualLineChartSvg(container, labels, revenue, previousRevenue) {
    const width = 960;
    const height = 350;
    const padLeft = 90;
    const padRight = 45;
    const padTop = 45;
    const padBottom = 45;
    const chartW = width - padLeft - padRight;
    const chartH = height - padTop - padBottom;

    const rawMax = Math.max(...revenue, ...previousRevenue, 10000000);
    
    // Moslashuvchan Y-o'qi shkalasi (50 mln, 100 mln, 150 mln kabi qatorlar)
    function getNiceScale(maxV) {
        const targetSteps = 4;
        const rawStep = maxV / targetSteps;
        const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
        const normalized = rawStep / magnitude;
        let step;
        if (normalized < 1.5) step = 1 * magnitude;
        else if (normalized < 3.5) step = 2.5 * magnitude;
        else if (normalized < 7.5) step = 5 * magnitude;
        else step = 10 * magnitude;

        const ticks = [];
        let cur = 0;
        while (cur <= maxV + step * 0.1 || ticks.length <= 4) {
            ticks.push(cur);
            cur += step;
        }
        return { ticks, maxVal: ticks[ticks.length - 1] || maxV };
    }

    const { ticks, maxVal } = getNiceScale(rawMax);
    const count = labels.length;
    const stepX = count > 1 ? chartW / (count - 1) : chartW;

    function getCoords(arr) {
        return arr.map((val, i) => {
            const x = padLeft + (i * stepX);
            const y = height - padBottom - ((val / maxVal) * chartH);
            return { x, y, val };
        });
    }

    const revPoints = getCoords(revenue);
    const prevPoints = getCoords(previousRevenue);

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
    const prevPath = buildSplinePath(prevPoints);

    const revArea = revPoints.length > 0 ? `${revPath} L ${revPoints[revPoints.length - 1].x} ${height - padBottom} L ${revPoints[0].x} ${height - padBottom} Z` : '';

    function formatYTick(val) {
        if (val === 0) return '0';
        if (val >= 1000000000) return (val / 1000000000).toFixed(val % 1000000000 === 0 ? 0 : 1) + ' mlrd';
        if (val >= 1000000) return (val / 1000000).toFixed(val % 1000000 === 0 ? 0 : 1) + ' mln';
        if (val >= 1000) return (val / 1000).toFixed(0) + ' ming';
        return val.toString();
    }

    let svg = `
        <svg class="va-svg-chart" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" style="width:100%; height:100%; min-height:350px;">
            <defs>
                <linearGradient id="vaCyanArea" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stop-color="#00f2fe" stop-opacity="0.32"/>
                    <stop offset="100%" stop-color="#00f2fe" stop-opacity="0.0"/>
                </linearGradient>
                <linearGradient id="vaPurpleArea" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stop-color="#a855f7" stop-opacity="0.2"/>
                    <stop offset="100%" stop-color="#a855f7" stop-opacity="0.0"/>
                </linearGradient>
                <filter id="glowCyan" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="3.5" result="blur"/>
                    <feComposite in="SourceGraphic" in2="blur" operator="over"/>
                </filter>
            </defs>

            <!-- Gorizontal Grid Chiziqlar va Chap Y-Axis Summalar -->
            ${ticks.map(tVal => {
                const yPos = height - padBottom - ((tVal / maxVal) * chartH);
                return `
                    <line x1="${padLeft}" y1="${yPos}" x2="${width - padRight}" y2="${yPos}" stroke="${tVal === 0 ? 'rgba(255,255,255,0.22)' : 'rgba(255,255,255,0.08)'}" stroke-dasharray="${tVal === 0 ? '0' : '4 4'}"/>
                    <text x="${padLeft - 14}" y="${yPos + 4}" fill="#94a3b8" font-size="11.5" font-weight="700" text-anchor="end" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif">${formatYTick(tVal)}</text>
                `;
            }).join('')}

            <!-- Area Fill -->
            <path d="${revArea}" fill="url(#vaCyanArea)"/>

            <!-- Oldingi davr (Purple Curve) -->
            <path d="${prevPath}" fill="none" stroke="#a855f7" stroke-width="2.6" stroke-linecap="round" stroke-dasharray="6 4"/>

            <!-- Tushum (Cyan Glowing Curve) -->
            <path d="${revPath}" fill="none" stroke="#00f2fe" stroke-width="3.6" stroke-linecap="round" filter="url(#glowCyan)"/>

            <!-- Oldingi davr va Joriy davr nuqtalari va Qiymat Badgelari (Ustma-ust tushishni oldini olish) -->
            ${revPoints.map((pCurr, i) => {
                const pPrev = prevPoints[i] || { x: pCurr.x, y: pCurr.y, val: 0 };
                const currVal = pCurr.val;
                const prevVal = pPrev.val;
                const currStr = formatYTick(currVal);
                const prevStr = formatYTick(prevVal);

                const currClampedX = Math.max(padLeft + 28, Math.min(width - padRight - 28, pCurr.x));
                const prevClampedX = Math.max(padLeft + 28, Math.min(width - padRight - 28, pPrev.x));

                // Vertikal masofa
                const yDiff = Math.abs(pCurr.y - pPrev.y);
                const isClose = (currVal > 0 && prevVal > 0) && yDiff < 34;

                let currBadgeY, prevBadgeY;
                if (isClose) {
                    if (pCurr.y <= pPrev.y) {
                        // Joriy davr yuqorida (summasi kattaroq yoki teng)
                        currBadgeY = pCurr.y - 16;
                        prevBadgeY = pPrev.y + 18;
                    } else {
                        // Oldingi davr yuqorida
                        prevBadgeY = pPrev.y - 16;
                        currBadgeY = pCurr.y + 18;
                    }
                } else {
                    currBadgeY = pCurr.y < (padTop + 22) ? (pCurr.y + 18) : (pCurr.y - 15);
                    prevBadgeY = pPrev.y > (height - padBottom - 30) ? (pPrev.y - 15) : (pPrev.y + 18);
                }

                // Chegara tekshiruvi (SVG dan chiqib ketmasligi uchun)
                if (currBadgeY < padTop - 2) currBadgeY = padTop + 14;
                if (prevBadgeY < padTop - 2) prevBadgeY = padTop + 14;
                if (currBadgeY > height - padBottom + 16) currBadgeY = height - padBottom - 14;
                if (prevBadgeY > height - padBottom + 16) prevBadgeY = height - padBottom - 14;

                return `
                    <!-- Oldingi davr nuqtasi (${labels[i]}) -->
                    <g class="va-chart-prev-point">
                        <circle cx="${pPrev.x}" cy="${pPrev.y}" r="3.6" fill="#a855f7" stroke="#ffffff" stroke-width="1.5"/>
                        ${prevVal > 0 ? `
                        <g transform="translate(${prevClampedX}, ${prevBadgeY})">
                            <rect x="-25" y="-9" width="50" height="17" rx="4" fill="rgba(24, 15, 42, 0.95)" stroke="rgba(168, 85, 247, 0.85)" stroke-width="1.2"/>
                            <text x="0" y="3" fill="#e9d5ff" font-size="9.5" font-weight="800" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif">${prevStr}</text>
                        </g>
                        ` : ''}
                    </g>

                    <!-- Joriy davr nuqtasi (${labels[i]}) -->
                    <g class="va-chart-point-group">
                        <circle cx="${pCurr.x}" cy="${pCurr.y}" r="8" fill="none" stroke="#00f2fe" stroke-width="1.5" opacity="0.45"/>
                        <circle cx="${pCurr.x}" cy="${pCurr.y}" r="4.5" fill="#00f2fe" stroke="#ffffff" stroke-width="2"/>
                        
                        ${currVal > 0 ? `
                        <g transform="translate(${currClampedX}, ${currBadgeY})">
                            <rect x="-26" y="-9" width="52" height="17" rx="5" fill="rgba(8, 14, 28, 0.95)" stroke="rgba(0, 242, 254, 0.85)" stroke-width="1.2"/>
                            <text x="0" y="3" fill="#00f2fe" font-size="10" font-weight="800" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif">${currStr}</text>
                        </g>
                        ` : ''}
                    </g>
                `;
            }).join('')}

            <!-- X-Axis Labels -->
            ${labels.map((lbl, i) => {
                const x = padLeft + (i * stepX);
                return `<text x="${x}" y="${height - 12}" fill="#94a3b8" font-size="11.5" font-weight="700" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif">${lbl}</text>`;
            }).join('')}
        </svg>
    `;

    container.innerHTML = svg;
}