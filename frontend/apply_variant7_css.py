# frontend/apply_variant7_css.py
import re

css_path = r"c:\Users\user\Documents\Anti APP\moysklad-app\frontend\css\style.css"

with open(css_path, "r", encoding="utf-8") as f:
    css = f.read()

variant7_styles = """
/* ==========================================================================
   VARIANT 7 DESIGN SYSTEM (Apple-style sleek, pastel cards, top navbar)
   ========================================================================== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
    /* Day Mode Colors (Variant 7) */
    --primary: #0f172a;
    --primary-blue: #1e60ff;
    --accent: #f97316;
    --success: #10b981;
    --danger: #ef4444;
    --warning: #f59e0b;
    --info: #3b82f6;
    --bg: #f4f7fb;
    --card: #ffffff;
    --text: #0f172a;
    --text-light: #64748b;
    --text-muted: #94a3b8;
    --border: #e2e8f0;
    --border-light: #f1f5f9;
    --nav-bg: #ffffff;
    --nav-border: #eef2f6;
    --base-font-size: 14px;
}

body.dark-mode {
    /* Night Mode Colors (Variant 10 Integration) */
    --primary: #f8fafc;
    --primary-blue: #3b82f6;
    --accent: #ff8a00;
    --success: #10b981;
    --danger: #f87171;
    --warning: #fbbf24;
    --info: #38bdf8;
    --bg: #0b0f19;
    --card: #131a2a;
    --text: #f1f5f9;
    --text-light: #94a3b8;
    --text-muted: #64748b;
    --border: #1e293b;
    --border-light: #162032;
    --nav-bg: #101624;
    --nav-border: rgba(255, 255, 255, 0.08);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: var(--base-font-size);
    background: var(--bg);
    color: var(--text);
    -webkit-font-smoothing: antialiased;
    transition: background 0.25s ease, color 0.25s ease;
}

/* ===== APP NAVBAR (VARIANT 7 TOP HEADER BAR) ===== */
.app-navbar {
    position: sticky;
    top: 0;
    z-index: 1000;
    background: var(--nav-bg);
    border-bottom: 1px solid var(--nav-border);
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
    transition: background 0.25s ease, border-color 0.25s ease;
}

.app-navbar-inner {
    max-width: 1440px;
    margin: 0 auto;
    height: 68px;
    padding: 0 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.navbar-brand-group {
    display: flex;
    align-items: center;
    gap: 28px;
}

.brand-link {
    display: flex;
    align-items: center;
    gap: 10px;
    text-decoration: none;
    color: var(--text);
}

.brand-icon-box {
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: linear-gradient(135deg, #f97316 0%, #1e60ff 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    box-shadow: 0 4px 10px rgba(30, 96, 255, 0.2);
}

.brand-title {
    font-size: 18px;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: var(--text);
}

.navbar-tabs {
    display: flex;
    align-items: center;
    gap: 6px;
}

.nav-tab-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 14px;
    font-weight: 600;
    color: var(--text-light);
    text-decoration: none;
    transition: all 0.2s ease;
}

.nav-tab-item:hover {
    color: var(--text);
    background: rgba(0, 0, 0, 0.04);
}

body.dark-mode .nav-tab-item:hover {
    background: rgba(255, 255, 255, 0.06);
    color: #ffffff;
}

.nav-tab-item.active {
    color: #1e60ff;
    background: #eff6ff;
    font-weight: 700;
}

body.dark-mode .nav-tab-item.active {
    color: #60a5fa;
    background: rgba(59, 130, 246, 0.15);
    box-shadow: 0 0 12px rgba(59, 130, 246, 0.2);
}

.navbar-right-group {
    display: flex;
    align-items: center;
    gap: 12px;
}

.nav-search-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #f1f5f9;
    padding: 7px 14px;
    border-radius: 20px;
    border: 1px solid transparent;
    width: 190px;
    transition: all 0.2s;
}

body.dark-mode .nav-search-bar {
    background: #1a2234;
    border-color: #243048;
}

.nav-search-bar input {
    border: none;
    background: transparent;
    outline: none;
    font-size: 13px;
    font-family: inherit;
    color: var(--text);
    width: 100%;
}

.nav-icon-circle-btn {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: #ffffff;
    border: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    color: var(--text);
}

body.dark-mode .nav-icon-circle-btn {
    background: #1a2234;
    border-color: #243048;
    color: #f1f5f9;
}

.nav-icon-circle-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 3px 8px rgba(0,0,0,0.08);
}

.nav-sync-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    border-radius: 20px;
    background: #eff6ff;
    border: 1px solid rgba(30, 96, 255, 0.25);
    color: #1e60ff;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.2s;
}

body.dark-mode .nav-sync-pill {
    background: rgba(59, 130, 246, 0.15);
    color: #60a5fa;
    border-color: rgba(59, 130, 246, 0.3);
}

.nav-sync-pill:hover {
    background: #1e60ff;
    color: #ffffff;
}

.nav-user-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 12px 4px 6px;
    border-radius: 24px;
    background: #ffffff;
    border: 1px solid var(--border);
    cursor: pointer;
}

body.dark-mode .nav-user-pill {
    background: #1a2234;
    border-color: #243048;
}

.user-avatar-circle {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: linear-gradient(135deg, #10b981, #1e60ff);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 700;
}

.user-name-text {
    font-size: 13px;
    font-weight: 700;
    color: var(--text);
}

.user-logout-btn {
    border: none;
    background: transparent;
    cursor: pointer;
    color: #ef4444;
    font-size: 14px;
    padding-left: 4px;
}

/* ===== MAIN CONTENT CONTAINER ===== */
.main-content {
    max-width: 1440px;
    margin: 0 auto;
    padding: 24px 28px 80px;
    width: 100%;
}

/* ===== GREETING HEADER (VARIANT 7: Good morning, Alex. | Today's Overview) ===== */
.v7-greeting-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 22px;
    flex-wrap: wrap;
    gap: 16px;
}

.v7-greeting-text-group {
    display: flex;
    align-items: baseline;
    gap: 12px;
    flex-wrap: wrap;
}

.v7-greeting-title {
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -0.6px;
    color: var(--text);
}

.v7-greeting-subtitle {
    font-size: 22px;
    font-weight: 500;
    color: var(--text-light);
}

.v7-org-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(30, 96, 255, 0.08);
    color: #1e60ff;
    border: 1px solid rgba(30, 96, 255, 0.2);
    padding: 4px 12px;
    border-radius: 14px;
    font-size: 12px;
    font-weight: 700;
    margin-left: 8px;
}

body.dark-mode .v7-org-badge {
    background: rgba(59, 130, 246, 0.15);
    color: #60a5fa;
    border-color: rgba(59, 130, 246, 0.3);
}

.v7-btn-new-order {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: #1e60ff;
    color: #ffffff !important;
    text-decoration: none;
    padding: 11px 22px;
    border-radius: 12px;
    font-weight: 700;
    font-size: 14px;
    box-shadow: 0 4px 14px rgba(30, 96, 255, 0.3);
    transition: all 0.2s ease;
    border: none;
    cursor: pointer;
}

.v7-btn-new-order:hover {
    background: #174ed1;
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(30, 96, 255, 0.4);
}

/* ===== DATE NAVIGATOR TOOLBAR (PILL STYLE) ===== */
.v7-date-toolbar {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 10px 18px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.02);
}

/* ===== STATS GRID (VARIANT 7 PASTEL GRADIENT CARDS) ===== */
.stats-grid-v7 {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    margin-bottom: 22px;
}

@media (max-width: 1150px) {
    .stats-grid-v7 {
        grid-template-columns: repeat(2, 1fr);
    }
}
@media (max-width: 640px) {
    .stats-grid-v7 {
        grid-template-columns: 1fr;
    }
}

.v7-stat-card {
    border-radius: 20px;
    padding: 22px 24px;
    min-height: 168px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    position: relative;
    overflow: hidden;
    transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.v7-stat-card:hover {
    transform: translateY(-3px);
}

/* 1. Baby Blue Card (Active Accounts / Umumiy Savdo) */
.card-pastel-blue {
    background: linear-gradient(145deg, #eef4ff 0%, #dfedff 100%);
    border: 1px solid rgba(193, 216, 255, 0.9);
    box-shadow: 0 10px 25px -5px rgba(30, 96, 255, 0.07);
}
body.dark-mode .card-pastel-blue {
    background: linear-gradient(145deg, #0f1d35 0%, #132545 100%);
    border: 1px solid rgba(59, 130, 246, 0.4);
    box-shadow: 0 10px 25px -5px rgba(30, 96, 255, 0.2);
}

/* 2. Mint Green Card (Total Sales / Naqd Tushum) */
.card-pastel-green {
    background: linear-gradient(145deg, #eefbf4 0%, #d8f6e5 100%);
    border: 1px solid rgba(167, 243, 208, 0.9);
    box-shadow: 0 10px 25px -5px rgba(16, 185, 129, 0.07);
}
body.dark-mode .card-pastel-green {
    background: linear-gradient(145deg, #09261a 0%, #0d3826 100%);
    border: 1px solid rgba(16, 185, 129, 0.4);
    box-shadow: 0 10px 25px -5px rgba(16, 185, 129, 0.2);
}

/* 3. Warm Amber/Peach Card (Pending Orders / Qarz Sotuvlar) */
.card-pastel-amber {
    background: linear-gradient(145deg, #fff7ed 0%, #feecd6 100%);
    border: 1px solid rgba(254, 215, 170, 0.9);
    box-shadow: 0 10px 25px -5px rgba(245, 158, 11, 0.07);
}
body.dark-mode .card-pastel-amber {
    background: linear-gradient(145deg, #2b1908 0%, #3d230b 100%);
    border: 1px solid rgba(245, 158, 11, 0.4);
    box-shadow: 0 10px 25px -5px rgba(245, 158, 11, 0.2);
}

/* 4. Lavender/Cyan Card (Avg Order Value / Qarzdorlik) */
.card-pastel-purple {
    background: linear-gradient(145deg, #f0f5ff 0%, #e3ecfc 100%);
    border: 1px solid rgba(199, 218, 255, 0.9);
    box-shadow: 0 10px 25px -5px rgba(59, 130, 246, 0.07);
}
body.dark-mode .card-pastel-purple {
    background: linear-gradient(145deg, #1d1838 0%, #271f4b 100%);
    border: 1px solid rgba(139, 92, 246, 0.4);
    box-shadow: 0 10px 25px -5px rgba(139, 92, 246, 0.2);
}

/* 5. Coral/Rose Card (Umumiy Qarzdorlik) */
.card-pastel-rose {
    background: linear-gradient(145deg, #fef2f2 0%, #fee2e2 100%);
    border: 1px solid rgba(254, 202, 202, 0.9);
    box-shadow: 0 10px 25px -5px rgba(239, 68, 68, 0.07);
}
body.dark-mode .card-pastel-rose {
    background: linear-gradient(145deg, #2d0f0f 0%, #3e1515 100%);
    border: 1px solid rgba(239, 68, 68, 0.4);
    box-shadow: 0 10px 25px -5px rgba(239, 68, 68, 0.2);
}

/* Secondary row for 2 cards */
.stats-subgrid-v7 {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
    margin-bottom: 24px;
}
@media (max-width: 640px) {
    .stats-subgrid-v7 {
        grid-template-columns: 1fr;
    }
}

.v7-card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
}

.v7-card-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--text);
}

.v7-badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 9999px;
    font-size: 12px;
    font-weight: 700;
    color: #ffffff;
}

.badge-blue { background: #1e60ff; }
.badge-green { background: #10b981; }
.badge-amber { background: #f97316; }
.badge-purple { background: #8b5cf6; }
.badge-danger { background: #ef4444; }

.v7-card-main {
    margin-bottom: 12px;
}

.v7-card-val {
    font-size: 27px;
    font-weight: 800;
    letter-spacing: -0.6px;
    color: var(--text);
    line-height: 1.2;
}

.v7-trend {
    font-size: 13px;
    font-weight: 700;
    margin-top: 4px;
}
.v7-trend.green { color: #10b981; }
.v7-trend.blue { color: #1e60ff; }
.v7-trend.amber { color: #f59e0b; }
.v7-trend.red { color: #ef4444; }

.v7-card-bottom {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.v7-card-actions {
    display: flex;
    gap: 6px;
}

.v7-mini-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(0, 0, 0, 0.06);
    font-size: 13px;
    user-select: none;
}

body.dark-mode .v7-mini-icon {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.1);
}

.v7-sparkline {
    width: 90px;
    height: 28px;
}
.v7-sparkline svg {
    width: 100%;
    height: 100%;
    display: block;
}

/* ===== RECENT ORDERS TABLE CARD (VARIANT 7) ===== */
.v7-table-card {
    background: var(--card);
    border-radius: 22px;
    padding: 24px 28px;
    box-shadow: 0 4px 25px rgba(0, 0, 0, 0.03);
    border: 1px solid var(--border);
    margin-bottom: 28px;
}

.v7-table-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 12px;
}

.v7-table-title-group {
    display: flex;
    align-items: center;
    gap: 12px;
}

.v7-table-title {
    font-size: 22px;
    font-weight: 800;
    color: var(--text);
    letter-spacing: -0.4px;
}

.v7-period-tag {
    font-size: 12px;
    font-weight: 600;
    background: rgba(0, 0, 0, 0.05);
    color: var(--text-light);
    padding: 4px 10px;
    border-radius: 12px;
}

body.dark-mode .v7-period-tag {
    background: rgba(255, 255, 255, 0.08);
}

.v7-pill-select {
    padding: 7px 16px;
    border-radius: 20px;
    background: var(--bg);
    border: 1px solid var(--border);
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
    cursor: pointer;
}

.v7-data-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
}

.v7-data-table th {
    padding: 14px 16px;
    text-align: left;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-light);
    border-bottom: 1.5px solid var(--border);
}

.v7-data-table td {
    padding: 16px 16px;
    font-size: 14px;
    color: var(--text);
    border-bottom: 1px solid var(--border-light);
    transition: background 0.15s ease;
}

.v7-data-table tr:hover td {
    background: rgba(0, 0, 0, 0.02);
}

body.dark-mode .v7-data-table tr:hover td {
    background: rgba(255, 255, 255, 0.03);
}

/* Status Pills (Variant 7 Pastel badges) */
.v7-status-pill {
    display: inline-flex;
    align-items: center;
    padding: 5px 14px;
    border-radius: 9999px;
    font-size: 12px;
    font-weight: 700;
    white-space: nowrap;
}

.status-delivered {
    background: #dcfce7;
    color: #15803d;
}
.status-shipped {
    background: #e0f2fe;
    color: #0369a1;
}
.status-processing {
    background: #fef3c7;
    color: #b45309;
}
.status-pending {
    background: #fee2e2;
    color: #b91c1c;
}

body.dark-mode .status-delivered { background: rgba(16, 185, 129, 0.2); color: #34d399; }
body.dark-mode .status-shipped { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
body.dark-mode .status-processing { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
body.dark-mode .status-pending { background: rgba(239, 68, 68, 0.2); color: #f87171; }

.v7-action-link {
    color: #1e60ff;
    text-decoration: none;
    font-weight: 600;
    font-size: 13px;
    margin: 0 4px;
}
.v7-action-link:hover {
    text-decoration: underline;
}

/* ===== BOTTOM 2-COLUMN ANALYTICS GRID (VARIANT 7) ===== */
.v7-bottom-grid {
    display: grid;
    grid-template-columns: 1fr 1.6fr;
    gap: 24px;
    margin-bottom: 30px;
}

@media (max-width: 990px) {
    .v7-bottom-grid {
        grid-template-columns: 1fr;
    }
}

.v7-chart-card {
    background: var(--card);
    border-radius: 22px;
    padding: 24px 28px;
    box-shadow: 0 4px 25px rgba(0, 0, 0, 0.03);
    border: 1px solid var(--border);
}

.v7-chart-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 10px;
}

.v7-chart-title {
    font-size: 20px;
    font-weight: 800;
    color: var(--text);
    letter-spacing: -0.4px;
}

.v7-chart-legend {
    display: flex;
    align-items: center;
    gap: 14px;
}

.legend-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-light);
}

.legend-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}
.legend-dot.green { background: #10b981; }
.legend-dot.amber { background: #f59e0b; }
.legend-dot.blue { background: #1e60ff; }

/* Mini Bar indicators for Inventory Pulse */
.inventory-pulse-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}

.inventory-mini-box {
    background: var(--bg);
    border-radius: 16px;
    padding: 14px 16px;
    border: 1px solid var(--border);
}

.mini-box-label {
    font-size: 13px;
    font-weight: 700;
    color: var(--text);
    display: block;
    margin-bottom: 12px;
}

.mini-bars-row {
    display: flex;
    align-items: flex-end;
    gap: 6px;
    height: 48px;
    margin-bottom: 8px;
}

.mini-bar {
    flex: 1;
    border-radius: 4px;
    transition: height 0.3s;
}

.mini-bar.green { background: #10b981; }
.mini-bar.amber { background: #f59e0b; }
.mini-bar.blue { background: #1e60ff; }
.mini-bar.orange { background: #f97316; }
.mini-bar.gray { background: #cbd5e1; }

body.dark-mode .mini-bar.gray { background: #334155; }

.h-10 { height: 10%; }
.h-15 { height: 15%; }
.h-30 { height: 30%; }
.h-40 { height: 40%; }
.h-50 { height: 50%; }
.h-60 { height: 60%; }
.h-65 { height: 65%; }
.h-70 { height: 70%; }
.h-75 { height: 75%; }
.h-80 { height: 80%; }
.h-85 { height: 85%; }
.h-90 { height: 90%; }
.h-95 { height: 95%; }

.mini-bars-labels {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    font-weight: 600;
    color: var(--text-muted);
}

/* Trends SVG Area Chart */
.v7-trends-visual {
    width: 100%;
}
.trends-svg {
    width: 100%;
    height: 180px;
    display: block;
}
.trends-x-axis {
    display: flex;
    justify-content: space-between;
    margin-top: 10px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    padding-left: 35px;
}

/* ===== LEGACY .stat-card COMPATIBILITY (Upgrading older pages to Variant 7 pastel) ===== */
.stat-card {
    border-radius: 20px !important;
    border: 1px solid rgba(193, 216, 255, 0.85) !important;
    border-left: none !important;
    background: linear-gradient(145deg, #eef4ff 0%, #dfedff 100%) !important;
    box-shadow: 0 10px 25px -5px rgba(30, 96, 255, 0.07) !important;
    padding: 22px 24px !important;
}
.stat-card.success {
    background: linear-gradient(145deg, #eefbf4 0%, #d8f6e5 100%) !important;
    border: 1px solid rgba(167, 243, 208, 0.85) !important;
}
.stat-card.warning {
    background: linear-gradient(145deg, #fff7ed 0%, #feecd6 100%) !important;
    border: 1px solid rgba(254, 215, 170, 0.85) !important;
}
.stat-card.info {
    background: linear-gradient(145deg, #f0f5ff 0%, #e3ecfc 100%) !important;
    border: 1px solid rgba(199, 218, 255, 0.85) !important;
}
.stat-card.danger {
    background: linear-gradient(145deg, #fef2f2 0%, #fee2e2 100%) !important;
    border: 1px solid rgba(254, 202, 202, 0.85) !important;
}

body.dark-mode .stat-card {
    background: linear-gradient(145deg, #0f1d35 0%, #132545 100%) !important;
    border: 1px solid rgba(59, 130, 246, 0.4) !important;
}
body.dark-mode .stat-card.success {
    background: linear-gradient(145deg, #09261a 0%, #0d3826 100%) !important;
    border: 1px solid rgba(16, 185, 129, 0.4) !important;
}
body.dark-mode .stat-card.warning {
    background: linear-gradient(145deg, #2b1908 0%, #3d230b 100%) !important;
    border: 1px solid rgba(245, 158, 11, 0.4) !important;
}
body.dark-mode .stat-card.danger {
    background: linear-gradient(145deg, #2d0f0f 0%, #3e1515 100%) !important;
    border: 1px solid rgba(239, 68, 68, 0.4) !important;
}
"""

with open(css_path, "w", encoding="utf-8") as f:
    f.write(variant7_styles + "\n\n" + css)

print("Variant 7 CSS applied successfully!")
