# frontend/apply_comprehensive_darkmode.py
import re

css_path = r"c:\Users\user\Documents\Anti APP\moysklad-app\frontend\css\style.css"

with open(css_path, "r", encoding="utf-8") as f:
    css = f.read()

darkmode_fixes = """
/* ==========================================================================
   COMPREHENSIVE NIGHT MODE (VARIANT 10 HIGH-CONTRAST DARK FIXES)
   ========================================================================== */
body.dark-mode {
    background-color: #0b0f19 !important;
    color: #f1f5f9 !important;
}

/* Headings & Texts */
body.dark-mode h1,
body.dark-mode h2,
body.dark-mode h3,
body.dark-mode h4,
body.dark-mode h5,
body.dark-mode h6,
body.dark-mode .page-title,
body.dark-mode .section-title,
body.dark-mode .v7-greeting-title,
body.dark-mode .v7-table-title,
body.dark-mode .v7-chart-title,
body.dark-mode .stat-value,
body.dark-mode .customer-name,
body.dark-mode strong {
    color: #f8fafc !important;
}

body.dark-mode .subtitle,
body.dark-mode .v7-greeting-subtitle,
body.dark-mode .stat-label,
body.dark-mode .stat-sub,
body.dark-mode .text-muted,
body.dark-mode .header-date,
body.dark-mode .accounts-title {
    color: #94a3b8 !important;
}

/* Cards, Sections, Panels */
body.dark-mode .filter-panel,
body.dark-mode .date-filter-panel,
body.dark-mode .section,
body.dark-mode .v7-table-card,
body.dark-mode .v7-chart-card,
body.dark-mode .table-wrapper,
body.dark-mode .account-card,
body.dark-mode .dual-card,
body.dark-mode .detail-card,
body.dark-mode .summary-card,
body.dark-mode .v7-date-toolbar,
body.dark-mode .currency-strip,
body.dark-mode .modal-content,
body.dark-mode .detail-modal-content {
    background: #131a2a !important;
    border-color: #1e293b !important;
    color: #f1f5f9 !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4) !important;
}

/* Quick Date Buttons & Navigators */
body.dark-mode .quick-btn {
    background: #162032 !important;
    border-color: #25334d !important;
    color: #cbd5e1 !important;
    box-shadow: none !important;
}
body.dark-mode .quick-btn:hover {
    background: #1e2c45 !important;
    border-color: #3b82f6 !important;
    color: #ffffff !important;
}
body.dark-mode .quick-btn.active {
    background: #1e60ff !important;
    border-color: #1e60ff !important;
    color: #ffffff !important;
    box-shadow: 0 2px 10px rgba(30, 96, 255, 0.4) !important;
}

body.dark-mode .period-navigator {
    background: #162032 !important;
    border-color: #25334d !important;
}
body.dark-mode .nav-arrow-btn {
    background: #1a253a !important;
    color: #cbd5e1 !important;
    border-color: #25334d !important;
}
body.dark-mode .nav-arrow-btn:hover {
    background: #1e60ff !important;
    color: #ffffff !important;
}
body.dark-mode .nav-period-label {
    background: #162032 !important;
    color: #f1f5f9 !important;
    border-color: #25334d !important;
}

body.dark-mode .date-inputs-compact {
    background: #162032 !important;
    border-color: #25334d !important;
}
body.dark-mode .date-inputs-compact input[type="date"] {
    background: transparent !important;
    color: #f1f5f9 !important;
    color-scheme: dark !important;
}

/* Status Filter Pills */
body.dark-mode .status-filter-pill {
    background: #162032 !important;
    border-color: #25334d !important;
    color: #94a3b8 !important;
}
body.dark-mode .status-filter-pill:hover {
    background: #1e2c45 !important;
    color: #ffffff !important;
    border-color: #3b82f6 !important;
}
body.dark-mode .status-filter-pill.active {
    background: #1e60ff !important;
    border-color: #1e60ff !important;
    color: #ffffff !important;
    box-shadow: 0 2px 10px rgba(30, 96, 255, 0.4) !important;
}

/* Form Controls & Inputs */
body.dark-mode input[type="text"],
body.dark-mode input[type="date"],
body.dark-mode input[type="number"],
body.dark-mode input[type="password"],
body.dark-mode input[type="search"],
body.dark-mode select,
body.dark-mode textarea,
body.dark-mode .filter-input,
body.dark-mode .form-control {
    background: #162032 !important;
    border-color: #25334d !important;
    color: #f1f5f9 !important;
    color-scheme: dark !important;
}
body.dark-mode input::placeholder,
body.dark-mode textarea::placeholder {
    color: #64748b !important;
}
body.dark-mode select option {
    background: #131a2a !important;
    color: #f1f5f9 !important;
}

/* Tables (Customers, Demands, Cashflow, Dashboard) */
body.dark-mode table,
body.dark-mode .data-table,
body.dark-mode .customers-table,
body.dark-mode .v7-data-table {
    background: transparent !important;
}

body.dark-mode table th,
body.dark-mode .data-table th,
body.dark-mode .customers-table th,
body.dark-mode .v7-data-table th {
    background: #162032 !important;
    color: #94a3b8 !important;
    border-bottom: 1.5px solid #1e293b !important;
}

body.dark-mode table td,
body.dark-mode .data-table td,
body.dark-mode .customers-table td,
body.dark-mode .v7-data-table td {
    background: transparent !important;
    color: #e2e8f0 !important;
    border-bottom: 1px solid #1a2333 !important;
}

body.dark-mode table tr:hover td,
body.dark-mode .data-table tr:hover td,
body.dark-mode .customers-table tr:hover td,
body.dark-mode .v7-data-table tr:hover td {
    background: rgba(255, 255, 255, 0.04) !important;
}

body.dark-mode .balance-cell.debt {
    color: #f87171 !important;
}
body.dark-mode .balance-cell.paid {
    color: #34d399 !important;
}

/* Buttons */
body.dark-mode .btn-secondary {
    background: #162032 !important;
    border-color: #25334d !important;
    color: #e2e8f0 !important;
}
body.dark-mode .btn-secondary:hover {
    background: #1e2c45 !important;
    color: #ffffff !important;
}

body.dark-mode .btn-print {
    background: #162032 !important;
    border-color: #25334d !important;
    color: #e2e8f0 !important;
}
body.dark-mode .btn-print:hover {
    background: #1e2c45 !important;
    color: #ffffff !important;
}

body.dark-mode .print-dropdown-menu,
body.dark-mode .dropdown-menu {
    background: #131a2a !important;
    border-color: #1e293b !important;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5) !important;
}
body.dark-mode .print-dropdown-menu button,
body.dark-mode .dropdown-menu button,
body.dark-mode .dropdown-menu a {
    color: #e2e8f0 !important;
}
body.dark-mode .print-dropdown-menu button:hover,
body.dark-mode .dropdown-menu button:hover,
body.dark-mode .dropdown-menu a:hover {
    background: #1a253a !important;
    color: #ffffff !important;
}

/* Modals & Quick States */
body.dark-mode .quick-state-option-btn {
    background: #162032 !important;
    border-color: #25334d !important;
    color: #f1f5f9 !important;
}
body.dark-mode .quick-state-option-btn:hover {
    background: #1e2c45 !important;
    border-color: #3b82f6 !important;
}
body.dark-mode .quick-state-option-btn.current {
    background: rgba(30, 96, 255, 0.2) !important;
    border-color: #1e60ff !important;
}

/* Badges & Icons */
body.dark-mode .stat-icon {
    background: #162032 !important;
    color: #f1f5f9 !important;
}
body.dark-mode .v7-pill-select {
    background: #162032 !important;
    border-color: #25334d !important;
    color: #f1f5f9 !important;
}
body.dark-mode .inventory-mini-box {
    background: #162032 !important;
    border-color: #25334d !important;
}

/* Rate Pills & Currency Bar */
body.dark-mode .rate-pill {
    background: rgba(255, 255, 255, 0.08) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    color: #f1f5f9 !important;
}
"""

# Append to style.css
with open(css_path, "a", encoding="utf-8") as f:
    f.write("\n" + darkmode_fixes)

print("Comprehensive Night Mode CSS applied successfully!")
