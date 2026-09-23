css_path = r'c:\Users\user\Documents\Anti APP\moysklad-app\frontend\css\style.css'

with open(css_path, 'a', encoding='utf-8') as f:
    f.write('''
/* ==========================================================================
   FORCE DARK MODE FOR ALL INLINE LIGHT COLORS
   ========================================================================== */
/* Generic fix for ANY element that has a very light background inline style */
body.dark-mode *[style*="background: #f"],
body.dark-mode *[style*="background:#f"],
body.dark-mode *[style*="background: #e"],
body.dark-mode *[style*="background:#e"],
body.dark-mode *[style*="background: var(--bg)"],
body.dark-mode *[style*="background: var(--card)"] {
    background-color: var(--card) !important;
    border-color: #1e293b !important;
}

/* For specific pastel colors often used for badges and small elements */
body.dark-mode .payment-cashin,
body.dark-mode .payment-paymentin,
body.dark-mode .payment-adjustment,
body.dark-mode .payment-demand,
body.dark-mode *[style*="background:#f0fff4"],
body.dark-mode *[style*="background: #f0fff4"],
body.dark-mode *[style*="background:#fff8e6"],
body.dark-mode *[style*="background: #fff8e6"],
body.dark-mode *[style*="background:#eef4ff"],
body.dark-mode *[style*="background: #eef4ff"],
body.dark-mode *[style*="background:#fef3c7"],
body.dark-mode *[style*="background: #fef3c7"],
body.dark-mode *[style*="background:#eff6ff"],
body.dark-mode *[style*="background: #eff6ff"],
body.dark-mode *[style*="background:#f0fdf4"],
body.dark-mode *[style*="background: #f0fdf4"] {
    background-color: rgba(255, 255, 255, 0.05) !important;
    border-color: rgba(255, 255, 255, 0.1) !important;
}

/* Force dark text to light in dark mode */
body.dark-mode *[style*="color:#555"],
body.dark-mode *[style*="color: #555"],
body.dark-mode *[style*="color:#333"],
body.dark-mode *[style*="color: #333"],
body.dark-mode *[style*="color:#000"],
body.dark-mode *[style*="color: #000"],
body.dark-mode *[style*="color:#111"],
body.dark-mode *[style*="color: #111"] {
    color: var(--text) !important;
}

/* Tables and Modals */
body.dark-mode .detail-modal-content,
body.dark-mode .modal-content {
    background: var(--card) !important;
}

body.dark-mode .drawer-account-item {
    background: var(--card) !important;
    border-color: #1e293b !important;
}
body.dark-mode .drawer-account-item strong,
body.dark-mode .drawer-account-item div {
    color: var(--text) !important;
}
''')

print("CSS appended.")
