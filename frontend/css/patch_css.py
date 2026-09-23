import re

with open('style.css', 'r', encoding='utf-8') as f:
    css = f.read()

# 1. Update .main-content to remove left margin
main_content_old = r"""\.main-content \{.*?\}"""
main_content_new = """.main-content {
    flex: 1;
    margin: 0 auto;
    padding: 24px 32px 80px;
    width: 100%;
    max-width: 1400px;
}"""
css = re.sub(main_content_old, main_content_new, css, flags=re.DOTALL)

# 2. Add .top-horizontal-nav CSS and remove old sidebar
nav_css = """
/* ===== TOP HORIZONTAL NAVIGATION (Variant 10 / Perfect Hybrid) ===== */
.top-horizontal-nav {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
    background: var(--nav-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(255, 255, 255, 0.05);
    padding: 8px 16px;
    border-radius: 40px;
    margin: 0 auto 24px auto;
    width: max-content;
    box-shadow: 0 10px 30px rgba(0,0,0,0.15);
}

.top-horizontal-nav .nav-link {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 20px;
    color: rgba(255,255,255,0.7);
    text-decoration: none;
    font-weight: 600;
    font-size: 14px;
    border-radius: 30px;
    transition: all 0.3s ease;
}

.top-horizontal-nav .nav-link:hover {
    background: rgba(255,255,255,0.1);
    color: #ffffff;
}

.top-horizontal-nav .nav-link.active {
    background: var(--info); /* Electric blue active state */
    color: #ffffff;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
}

.top-horizontal-nav .nav-link .icon {
    font-size: 18px;
}

/* Remove old sidebar css safely */
"""
# Replace old sidebar CSS with empty or comment
sidebar_pattern = r"""/\* ===== SIDEBAR \(Desktop\) ===== \*/.*?/\* ===== MAIN CONTENT ===== \*/"""
css = re.sub(sidebar_pattern, nav_css + "\n/* ===== MAIN CONTENT ===== */", css, flags=re.DOTALL)

with open('style.css', 'w', encoding='utf-8') as f:
    f.write(css)
print("Updated style.css for Top Nav")
