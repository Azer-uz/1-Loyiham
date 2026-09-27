import os

payments_html_path = os.path.join(os.path.dirname(__file__), 'frontend', 'payments.html')
payments_js_path = os.path.join(os.path.dirname(__file__), 'frontend', 'js', 'payments.js')

with open(payments_html_path, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Add CSS for Quick-Pay Drawer
drawer_css = """
        /* ================= UNIFIED QUICK-PAY DRAWER (FINTECH) ================= */
        .drawer-backdrop {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(15, 23, 42, 0.55);
            backdrop-filter: blur(3px);
            z-index: 9998;
            opacity: 0;
            visibility: hidden;
            transition: all 0.25s ease;
        }
        .drawer-backdrop.active {
            opacity: 1;
            visibility: visible;
        }

        .quick-pay-drawer {
            position: fixed;
            top: 0;
            right: -600px;
            bottom: 0;
            width: 540px;
            max-width: 95vw;
            background: var(--card, #ffffff);
            box-shadow: -10px 0 35px rgba(0, 0, 0, 0.2);
            z-index: 9999;
            display: flex;
            flex-direction: column;
            transition: right 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            overflow: hidden;
        }
        .quick-pay-drawer.active {
            right: 0;
        }

        .drawer-header {
            padding: 14px 18px;
            background: #f8fafc;
            border-bottom: 1.5px solid #e2e8f0;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }

        .drawer-tabs {
            display: flex;
            background: #e2e8f0;
            padding: 3px;
            border-radius: 8px;
            gap: 3px;
        }

        .drawer-tab-btn {
            padding: 7px 14px;
            border-radius: 6px;
            border: none;
            font-size: 12.5px;
            font-weight: 700;
            cursor: pointer;
            background: transparent;
            color: #64748b;
            transition: all 0.15s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
        }
        .drawer-tab-btn.active#tabBtnIncome {
            background: #16a34a;
            color: #ffffff;
            box-shadow: 0 2px 6px rgba(22, 163, 74, 0.3);
        }
        .drawer-tab-btn.active#tabBtnExpense {
            background: #dc2626;
            color: #ffffff;
            box-shadow: 0 2px 6px rgba(220, 38, 38, 0.3);
        }

        .drawer-kbd-badge {
            font-size: 10.5px;
            font-weight: 700;
            color: #64748b;
            background: #e2e8f0;
            padding: 4px 8px;
            border-radius: 6px;
            border: 1px solid #cbd5e1;
        }

        .drawer-close-btn {
            background: transparent;
            border: none;
            font-size: 24px;
            line-height: 1;
            color: #64748b;
            cursor: pointer;
            padding: 2px 6px;
            border-radius: 6px;
            transition: background 0.15s;
        }
        .drawer-close-btn:hover {
            background: #e2e8f0;
            color: #0f172a;
        }

        .drawer-body {
            padding: 18px 20px;
            overflow-y: auto;
            flex: 1;
        }

        .drawer-section {
            display: none;
        }
        .drawer-section.active {
            display: block;
            animation: drawerFade 0.2s ease;
        }
        @keyframes drawerFade {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .drawer-suggest-box {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            max-height: 220px;
            overflow-y: auto;
            background: #fff;
            border: 1.5px solid #0284c7;
            border-top: none;
            border-radius: 0 0 8px 8px;
            z-index: 9999;
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
        }

        .drawer-chips-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: 4px;
        }
        .drawer-chip-btn {
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11.5px;
            font-weight: 700;
            color: #334155;
            cursor: pointer;
            transition: all 0.15s;
        }
        .drawer-chip-btn:hover, .drawer-chip-btn.active {
            background: #e0f2fe;
            border-color: #0284c7;
            color: #0369a1;
        }

        /* Dark mode drawer */
        body.dark-mode .quick-pay-drawer {
            background: #0f172a;
            border-left: 1px solid #1e293b;
        }
        body.dark-mode .drawer-header {
            background: #1e293b;
            border-color: #334155;
        }
        body.dark-mode .drawer-tabs {
            background: #0f172a;
        }
        body.dark-mode .drawer-suggest-box {
            background: #1e293b;
            border-color: #38bdf8;
        }
        body.dark-mode .drawer-chip-btn {
            background: #1e293b;
            border-color: #334155;
            color: #e2e8f0;
        }
"""

if '.quick-pay-drawer' not in html:
    html = html.replace('</style>', drawer_css + '\n    </style>', 1)
    print("Added drawer CSS to payments.html")

# 2. Update action buttons in header
html = html.replace(
    'onclick="openCustomerPaymentModal()"',
    'onclick="openQuickPayDrawer(\'income\')"'
)
html = html.replace(
    'onclick="openExpenseModal()"',
    'onclick="openQuickPayDrawer(\'expense\')"'
)

# 3. Add Drawer HTML
drawer_html = """
    <!-- ===== BIRLASHGAN TEZKOR TO'LOV PANELI (UNIFIED QUICK-PAY DRAWER) ===== -->
    <div id="quickPayDrawerBackdrop" class="drawer-backdrop" onclick="closeQuickPayDrawer()"></div>
    <div id="quickPayDrawer" class="quick-pay-drawer">
        <!-- Drawer Header -->
        <div class="drawer-header">
            <div class="drawer-tabs">
                <button type="button" class="drawer-tab-btn active" id="tabBtnIncome" onclick="switchDrawerTab('income')">
                    <span>📥</span> Yangi Kirim (Mijozdan)
                </button>
                <button type="button" class="drawer-tab-btn" id="tabBtnExpense" onclick="switchDrawerTab('expense')">
                    <span>💸</span> Yangi Xarajat (Chiqim)
                </button>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
                <span class="drawer-kbd-badge hide-mobile" title="Tezkor klaviatura: Ctrl+Enter saqlash, Esc yopish">Ctrl+Enter 💾</span>
                <button type="button" class="drawer-close-btn" onclick="closeQuickPayDrawer()">&times;</button>
            </div>
        </div>

        <!-- Drawer Body -->
        <div class="drawer-body">
            
            <!-- ===== TAB 1: KIRIM (INCOME) ===== -->
            <div id="drawerIncomeSection" class="drawer-section active">
                <form id="drawerIncomeForm" onsubmit="handleDrawerIncomeSubmit(event)">
                    
                    <!-- Mijoz qidirish / tanlash -->
                    <div class="form-group" style="margin-bottom:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">
                            <label for="drawerIncomeCustomerSearch" style="font-weight:700; font-size:12.5px;">👤 Mijoz (Kontragent) <span style="color:red;">*</span></label>
                            <button type="button" onclick="openNewCustomerModal()" style="background:none; border:none; color:var(--primary); font-size:11.5px; font-weight:700; cursor:pointer;">➕ Yangi mijoz</button>
                        </div>
                        
                        <div style="position:relative;">
                            <input type="text" id="drawerIncomeCustomerSearch" class="form-control" 
                                placeholder="🔍 Mijoz ismini yoki telefonini yozing..." 
                                autocomplete="off" 
                                style="font-size:13.5px; font-weight:700; padding:8px 12px; border-radius:8px; border:1.5px solid #0284c7; width:100%;"
                                onfocus="showDrawerCustList()"
                                oninput="filterDrawerCustList(this.value)"
                            />
                            <input type="hidden" id="drawerIncomeCustomerId" required>

                            <!-- Autocomplete Suggestions List -->
                            <div id="drawerCustSuggestionsList" class="drawer-suggest-box" style="display:none;"></div>
                        </div>

                        <!-- Mijoz balansi & qarzi info banner -->
                        <div id="drawerCustDebtBanner" style="display:none; margin-top:8px; padding:8px 12px; border-radius:8px; background:#f8fafc; border:1px solid #e2e8f0; font-size:12px; display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:#64748b;">Mijoz balansi:</span>
                            <strong id="drawerCustDebtValue" style="font-size:13px;">—</strong>
                        </div>

                        <!-- Bog'lanmagan sotuvlar qarz tugmalari -->
                        <div id="drawerCustDemandsList" style="margin-top:6px; display:flex; flex-wrap:wrap; gap:6px;"></div>
                    </div>

                    <!-- To'lov summalari (3 ta valyuta / kassa bo'yicha) -->
                    <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:14px; margin-bottom:14px;">
                        <div style="font-size:12px; font-weight:700; color:#334155; margin-bottom:10px; display:flex; justify-content:space-between;">
                            <span>To'lov taqsimoti:</span>
                            <span style="font-size:11px; color:#64748b;">(Aralash to'lov kiritish mumkin)</span>
                        </div>

                        <!-- 1. Naqd pul UZS -->
                        <div class="form-group" style="margin-bottom:10px;">
                            <label style="font-size:12px; font-weight:600; color:#047857; display:flex; align-items:center; gap:4px;">
                                💵 Naqd pul (so'm)
                            </label>
                            <input type="text" inputmode="numeric" id="drawerPayCash" class="form-control format-number" placeholder="0" style="font-size:15px; font-weight:700;" oninput="updateDrawerTotals()">
                        </div>

                        <!-- 2. Karta UZS + Karta hisobi -->
                        <div style="display:grid; grid-template-columns: 1fr 1.2fr; gap:10px; margin-bottom:10px;">
                            <div class="form-group" style="margin:0;">
                                <label style="font-size:12px; font-weight:600; color:#1d4ed8;">💳 Karta / Bank (so'm)</label>
                                <input type="text" inputmode="numeric" id="drawerPayCard" class="form-control format-number" placeholder="0" style="font-size:15px; font-weight:700;" oninput="updateDrawerTotals()">
                            </div>
                            <div class="form-group" style="margin:0;">
                                <label style="font-size:11px; font-weight:600; color:#64748b;">Karta hisobi</label>
                                <select id="drawerPayCardAccount" class="form-control" style="font-size:12.5px; padding:7px 8px;">
                                </select>
                            </div>
                        </div>

                        <!-- 3. Dollar USD + Dollar hisobi -->
                        <div style="display:grid; grid-template-columns: 1fr 1.2fr; gap:10px;">
                            <div class="form-group" style="margin:0;">
                                <label style="font-size:12px; font-weight:600; color:#b45309;">💲 Dollar miqdori ($)</label>
                                <input type="text" inputmode="decimal" id="drawerPayUsd" class="form-control format-number" placeholder="0.00" style="font-size:15px; font-weight:700;" oninput="updateDrawerTotals()">
                            </div>
                            <div class="form-group" style="margin:0;">
                                <label style="font-size:11px; font-weight:600; color:#64748b;">Dollar hisobi</label>
                                <select id="drawerPayUsdAccount" class="form-control" style="font-size:12.5px; padding:7px 8px;">
                                </select>
                            </div>
                        </div>
                    </div>

                    <!-- Jami hisoblangan summa preview -->
                    <div style="background:linear-gradient(135deg, #f0fdf4, #dcfce7); border:1.5px solid #86efac; border-radius:10px; padding:12px 16px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div style="font-size:11px; font-weight:700; color:#15803d; text-transform:uppercase;">Jami Kirim Summasi:</div>
                            <strong id="drawerIncomeTotalUzs" style="font-size:18px; color:#166534;">0 so'm</strong>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-size:11px; color:#15803d;">Ekvivalent:</div>
                            <strong id="drawerIncomeTotalUsd" style="font-size:14px; color:#047857;">$0.00 USD</strong>
                        </div>
                    </div>

                    <!-- Sana & Izoh -->
                    <div style="display:grid; grid-template-columns: 1.2fr 1.8fr; gap:10px; margin-bottom:16px;">
                        <div class="form-group" style="margin:0;">
                            <label for="drawerIncomeMoment" style="font-size:11.5px; font-weight:600;">Sana va vaqt</label>
                            <input type="datetime-local" id="drawerIncomeMoment" class="form-control" style="font-size:12px; padding:7px 8px;">
                        </div>
                        <div class="form-group" style="margin:0;">
                            <label for="drawerIncomeDesc" style="font-size:11.5px; font-weight:600;">Izoh / Maqsad</label>
                            <input type="text" id="drawerIncomeDesc" class="form-control" placeholder="Mijozdan to'lov..." style="font-size:12.5px; padding:7px 10px;">
                        </div>
                    </div>

                    <!-- Saqlash tugmasi -->
                    <div style="display:flex; justify-content:flex-end; gap:10px; padding-top:10px; border-top:1px solid #e2e8f0;">
                        <button type="button" class="btn-print" onclick="closeQuickPayDrawer()">Bekor qilish</button>
                        <button type="submit" id="saveDrawerIncomeBtn" class="btn-primary-action" style="background:linear-gradient(135deg, #16a34a, #15803d); font-size:13.5px; font-weight:700; padding:9px 20px; border-radius:8px;">
                            💾 Kirimni Saqlash (Ctrl+Enter)
                        </button>
                    </div>
                </form>
            </div>

            <!-- ===== TAB 2: XARAJAT (EXPENSE) ===== -->
            <div id="drawerExpenseSection" class="drawer-section">
                <form id="drawerExpenseForm" onsubmit="handleDrawerExpenseSubmit(event)">
                    
                    <!-- To'lov usuli tabs -->
                    <div class="form-group" style="margin-bottom:12px;">
                        <label style="font-size:12px; font-weight:700;">To'lov usuli / Kassa turi:</label>
                        <div class="type-selector-tabs" style="margin-top:4px;">
                            <button type="button" class="type-tab-btn active" id="drawerExpTypeCash" onclick="setDrawerExpenseType('cash')">💵 Naqd pul</button>
                            <button type="button" class="type-tab-btn" id="drawerExpTypeCard" onclick="setDrawerExpenseType('card')">💳 Karta / Bank</button>
                            <button type="button" class="type-tab-btn" id="drawerExpTypeUsd" onclick="setDrawerExpenseType('usd')">💲 Dollar</button>
                        </div>
                    </div>

                    <!-- Chiqim hisobi -->
                    <div class="form-group" style="margin-bottom:12px;">
                        <label for="drawerExpAccountSelect" style="font-size:12px; font-weight:700;">Chiqim hisobi / Kassasi <span style="color:red;">*</span></label>
                        <select id="drawerExpAccountSelect" class="form-control" required style="font-size:13px; font-weight:600; padding:8px 10px;">
                        </select>
                    </div>

                    <!-- Xarajat summasi -->
                    <div class="form-group" style="margin-bottom:12px;">
                        <label for="drawerExpAmount" style="font-size:12px; font-weight:700;">Xarajat summasi <span style="color:red;">*</span></label>
                        <input type="text" inputmode="numeric" id="drawerExpAmount" class="form-control format-number" placeholder="0" required style="font-size:18px; font-weight:800; padding:8px 12px; border:1.5px solid #dc2626;" oninput="updateDrawerExpUsdPreview()">
                        <small id="drawerExpUsdPreview" style="color:var(--success); font-weight:700; margin-top:3px; display:block;">~ $0.00 USD</small>
                    </div>

                    <!-- Xarajat toifasi (Tezkor tugmalar + Dropdown) -->
                    <div class="form-group" style="margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <label for="drawerExpItemSelect" style="font-size:12px; font-weight:700;">Xarajat toifasi (Moddasi) <span style="color:red;">*</span></label>
                            <button type="button" onclick="openNewExpenseItemModal()" style="background:none; border:none; color:var(--primary); font-size:11.5px; font-weight:700; cursor:pointer;">➕ Yangi toifa</button>
                        </div>

                        <!-- Tezkor toifa chip-tugmalari -->
                        <div class="drawer-chips-grid">
                            <button type="button" class="drawer-chip-btn" onclick="selectDrawerExpenseItemQuick('Ijara')">🏢 Ijara</button>
                            <button type="button" class="drawer-chip-btn" onclick="selectDrawerExpenseItemQuick('Oylik')">👥 Oylik</button>
                            <button type="button" class="drawer-chip-btn" onclick="selectDrawerExpenseItemQuick('Yoqilg\'i')">⛽ Yoqilg'i</button>
                            <button type="button" class="drawer-chip-btn" onclick="selectDrawerExpenseItemQuick('Reklama')">📢 Reklama</button>
                            <button type="button" class="drawer-chip-btn" onclick="selectDrawerExpenseItemQuick('Bozor')">🛒 Bozor</button>
                            <button type="button" class="drawer-chip-btn" onclick="selectDrawerExpenseItemQuick('Transport')">📦 Transport</button>
                        </div>

                        <select id="drawerExpItemSelect" class="form-control" required style="font-size:13px; font-weight:600; padding:8px 10px; margin-top:6px;">
                            <option value="">Toifani tanlang...</option>
                        </select>
                    </div>

                    <!-- Sana & Izoh -->
                    <div style="display:grid; grid-template-columns: 1.2fr 1.8fr; gap:10px; margin-bottom:16px;">
                        <div class="form-group" style="margin:0;">
                            <label for="drawerExpMoment" style="font-size:11.5px; font-weight:600;">Sana va vaqt</label>
                            <input type="datetime-local" id="drawerExpMoment" class="form-control" style="font-size:12px; padding:7px 8px;">
                        </div>
                        <div class="form-group" style="margin:0;">
                            <label for="drawerExpDesc" style="font-size:11.5px; font-weight:600;">Izoh / Tafsilot</label>
                            <input type="text" id="drawerExpDesc" class="form-control" placeholder="Xarajat sababi..." style="font-size:12.5px; padding:7px 10px;">
                        </div>
                    </div>

                    <!-- Saqlash tugmasi -->
                    <div style="display:flex; justify-content:flex-end; gap:10px; padding-top:10px; border-top:1px solid #e2e8f0;">
                        <button type="button" class="btn-print" onclick="closeQuickPayDrawer()">Bekor qilish</button>
                        <button type="submit" id="saveDrawerExpBtn" class="btn-primary-action" style="background:linear-gradient(135deg, #dc2626, #b91c1c); font-size:13.5px; font-weight:700; padding:9px 20px; border-radius:8px;">
                            💾 Xarajatni Saqlash (Ctrl+Enter)
                        </button>
                    </div>
                </form>
            </div>

        </div>
    </div>
"""

if '<div id="quickPayDrawer"' not in html:
    html = html.replace('</body>', drawer_html + '\n</body>', 1)
    print("Added drawer HTML to payments.html")

with open(payments_html_path, 'w', encoding='utf-8') as f:
    f.write(html)

print("SUCCESS: Updated payments.html")
