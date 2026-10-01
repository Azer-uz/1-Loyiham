// frontend/js/api.js
const API_BASE = '/api';

window.currentUSDRate = 11800.0;
window.cbuRateInfo = null;

// ================= AVTORIZATSIYA HIMOYASI (AUTH GUARD) =================
(function enforceAuth() {
    const path = window.location.pathname;
    const isLoginPage = path.endsWith('login.html') || path.endsWith('/login') || path === '/login';
    const token = localStorage.getItem('token');

    if (!token && !isLoginPage) {
        // Tizimga kirmagan bo'lsa, zudlik bilan login sahifasiga yo'naltirish
        window.location.href = '/login';
        return;
    } else if (token && isLoginPage) {
        // Agar kiritilgan bo'lsa, login sahifasidan dashboard'ga o'tish
        window.location.href = '/';
        return;
    }

    // Token haqiqiyligini tekshirish (fondan sokin tekshiruv)
    if (token && !isLoginPage) {
        fetch(`${API_BASE}/auth/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        }).then(res => {
            if (res.status === 401) {
                console.warn("Muddati o'tgan token, login sahifasiga o'tkazilmoqda...");
                localStorage.removeItem('token');
                localStorage.removeItem('user');
                window.location.href = '/login';
            }
        }).catch(() => {});
    }
})();

function getCurrentUser() {
    try {
        const u = localStorage.getItem('user');
        return u ? JSON.parse(u) : null;
    } catch {
        return null;
    }
}

function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/login';
}

// ================= ASOSIY FETCH FUNKSIYASI =================
async function apiFetch(endpoint, options = {}) {
    try {
        const token = localStorage.getItem('token');
        const headers = {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            ...options.headers,
        };

        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers,
        });

        if (response.status === 401) {
            console.warn('Avtorizatsiya muddati tugagan (401)');
            localStorage.removeItem('token');
            localStorage.removeItem('user');
            const isLoginPage = window.location.pathname.endsWith('login.html') || window.location.pathname === '/login';
            if (!isLoginPage) {
                window.location.href = '/login';
            }
            throw new Error("Iltimos, tizimga qayta kiring");
        }

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Xato: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API xato:', error);
        throw error;
    }
}

// ================= YUKLANAYOTGANDA MA'LUMOTLAR =================
window.addEventListener('DOMContentLoaded', () => {
    fetchUSDRate();
    initUserProfileAndDropdown();
    initUniversalSearchAndNotifications();
    initTheme();
});

// ================= ADMIN DROPDOWN VA PROFIL BOSHQARUVI =================
async function initUserProfileAndDropdown() {
    let u = getCurrentUser();
    
    // Serverdan eng so'nggi profil ma'lumotlarini olish
    const token = localStorage.getItem('token');
    if (token) {
        try {
            const resp = await apiFetch('/auth/profile');
            if (resp && resp.success && resp.data) {
                u = { ...u, ...resp.data };
                localStorage.setItem('user', JSON.stringify(u));
            }
        } catch (e) {
            // Offline yoki keshdan foydalanish
        }
    }

    renderUserNavbar(u);

    // Tashqariga bosilganda dropdownlarni yopish
    document.addEventListener('click', (e) => {
        const userDropdown = document.getElementById('navUserDropdownWrapper');
        if (userDropdown && !userDropdown.contains(e.target)) {
            userDropdown.classList.remove('open');
        }

        const notifWrapper = document.getElementById('navNotificationsWrapper');
        if (notifWrapper && !notifWrapper.contains(e.target)) {
            notifWrapper.classList.remove('open');
        }
    });
}

function renderUserNavbar(u) {
    if (!u) return;

    const displayName = u.full_name || u.username || 'Admin';
    const roleText = (u.role === 'admin' ? 'Administrator' : 'Foydalanuvchi');
    const avatarContent = u.avatar_url 
        ? `<img src="${u.avatar_url}" alt="${displayName}" style="width:100%; height:100%; border-radius:50%; object-fit:cover;">`
        : (displayName.charAt(0).toUpperCase() || '👤');

    // Navbar elementlari
    const lbl = document.getElementById('currentUserLabel');
    if (lbl) lbl.textContent = displayName;

    const greetingName = document.getElementById('adminGreetingName');
    if (greetingName) greetingName.textContent = displayName;

    const avatars = document.querySelectorAll('.user-avatar-circle');
    avatars.forEach(av => {
        av.innerHTML = avatarContent;
    });

    // Dropdown menyusi ichidagi elementlar
    const dropName = document.getElementById('dropdownUserName');
    if (dropName) dropName.textContent = displayName;

    const dropEmail = document.getElementById('dropdownUserLogin');
    if (dropEmail) dropEmail.textContent = `${u.username || 'admin'}@azer`;

    const dropAvatarLarge = document.getElementById('dropdownAvatarLarge');
    if (dropAvatarLarge) dropAvatarLarge.innerHTML = avatarContent;
}

window.toggleUserDropdown = function(event) {
    if (event) event.stopPropagation();
    const wrapper = document.getElementById('navUserDropdownWrapper');
    if (wrapper) {
        wrapper.classList.toggle('open');
    }
};

window.openUserProfileModal = function() {
    let modal = document.getElementById('userProfileModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'userProfileModal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 480px;">
                <div class="modal-header">
                    <h2>👤 Foydalanuvchi Profili</h2>
                    <button class="modal-close" onclick="closeUserProfileModal()">✖</button>
                </div>
                <div class="modal-body" style="display:flex; flex-direction:column; gap:16px;">
                    <!-- Avatar tanlash / ko'rish -->
                    <div style="display:flex; flex-direction:column; align-items:center; gap:10px; margin-bottom:6px;">
                        <div id="modalAvatarPreview" style="width:90px; height:90px; border-radius:50%; background:linear-gradient(135deg, #f97316, #1e60ff); color:white; display:flex; align-items:center; justify-content:center; font-size:36px; font-weight:700; overflow:hidden; border:3px solid var(--border); box-shadow:0 4px 15px rgba(0,0,0,0.1);">
                            👤
                        </div>
                        <div style="display:flex; gap:8px;">
                            <label class="btn-secondary" style="cursor:pointer; font-size:12px; padding:6px 12px; border-radius:8px; background:var(--bg); border:1px solid var(--border); font-weight:600;">
                                📷 Rasm yuklash
                                <input type="file" id="profileAvatarFile" accept="image/*" style="display:none;" onchange="handleAvatarFileSelect(event)">
                            </label>
                            <button type="button" class="btn-secondary" style="font-size:12px; padding:6px 12px; border-radius:8px; background:var(--bg); border:1px solid var(--border);" onclick="clearAvatar()">
                                🗑️ O'chirish
                            </button>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>To'liq Ism (Full Name)</label>
                        <input type="text" id="profileFullNameInput" class="form-control" placeholder="Masalan: Ibrohimxo'ja">
                    </div>

                    <div class="form-group">
                        <label>Yangi Parol (Agar o'zgartirmoqchi bo'lsangiz)</label>
                        <input type="password" id="profilePasswordInput" class="form-control" placeholder="Yangi parol...">
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn-secondary" onclick="closeUserProfileModal()">Bekor qilish</button>
                    <button type="button" class="btn-primary" onclick="saveUserProfile()">💾 Saqlash</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    const u = getCurrentUser() || {};
    const nameInput = document.getElementById('profileFullNameInput');
    if (nameInput) nameInput.value = u.full_name || '';

    const passInput = document.getElementById('profilePasswordInput');
    if (passInput) passInput.value = '';

    window.tempAvatarUrl = u.avatar_url || '';
    updateModalAvatarPreview(window.tempAvatarUrl, u.full_name || u.username);

    modal.classList.add('active');
};

function updateModalAvatarPreview(avatarUrl, name) {
    const preview = document.getElementById('modalAvatarPreview');
    if (!preview) return;
    if (avatarUrl) {
        preview.innerHTML = `<img src="${avatarUrl}" alt="Avatar" style="width:100%; height:100%; object-fit:cover;">`;
    } else {
        const char = name ? name.charAt(0).toUpperCase() : '👤';
        preview.innerHTML = `<span>${char}</span>`;
    }
}

window.handleAvatarFileSelect = function(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
        showToast("Rasm hajmi 2MB dan oshmasligi kerak", "warning");
        return;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
        window.tempAvatarUrl = e.target.result;
        updateModalAvatarPreview(window.tempAvatarUrl, document.getElementById('profileFullNameInput').value);
    };
    reader.readAsDataURL(file);
};

window.clearAvatar = function() {
    window.tempAvatarUrl = '';
    updateModalAvatarPreview('', document.getElementById('profileFullNameInput').value);
};

window.closeUserProfileModal = function() {
    const modal = document.getElementById('userProfileModal');
    if (modal) modal.classList.remove('active');
};

window.saveUserProfile = async function() {
    const fullName = document.getElementById('profileFullNameInput').value.trim();
    const password = document.getElementById('profilePasswordInput').value.trim();

    const payload = {
        full_name: fullName,
        avatar_url: window.tempAvatarUrl || ''
    };
    if (password) {
        payload.password = password;
    }

    try {
        const resp = await apiFetch('/auth/profile', {
            method: 'PUT',
            body: JSON.stringify(payload)
        });

        if (resp && resp.success) {
            showToast("Profil muvaffaqiyatli saqlandi!", "success");
            const user = resp.data;
            localStorage.setItem('user', JSON.stringify(user));
            renderUserNavbar(user);
            closeUserProfileModal();
        }
    } catch (e) {
        showToast("Xatolik: " + e.message, "error");
    }
};

// ================= UNIVERSAL SPOTLIGHT SEARCH & NOTIFICATIONS =================
function initUniversalSearchAndNotifications() {
    // 1. Qidiruv tugmasi (🔍) va Ctrl+K
    const globalSearchInput = document.getElementById('globalSearch');
    if (globalSearchInput) {
        globalSearchInput.addEventListener('focus', () => {
            openSpotlightSearch();
            globalSearchInput.blur();
        });
    }

    window.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            openSpotlightSearch();
        }
    });

    // 2. Bildirishnomalar tugmasi (🔔)
    const notifBtns = document.querySelectorAll('button[title="Bildirishnomalar"]');
    notifBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleNotifications(btn);
        });
    });
}

window.openSpotlightSearch = function() {
    let overlay = document.getElementById('spotlightOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'spotlightOverlay';
        overlay.className = 'spotlight-overlay';
        overlay.onclick = (e) => {
            if (e.target === overlay) closeSpotlightSearch();
        };
        overlay.innerHTML = `
            <div class="spotlight-box">
                <div class="spotlight-header">
                    <span style="font-size:20px;">🔍</span>
                    <input type="text" id="spotlightSearchInput" class="spotlight-input" placeholder="Tezkor qidiruv (Mijoz, Sotuv raqami yoki To'lov)..." autocomplete="off">
                    <span style="font-size:12px; color:var(--text-muted); background:var(--border-light); padding:3px 8px; border-radius:6px;">ESC yopish</span>
                </div>
                <div class="spotlight-results" id="spotlightResultsList">
                    <div style="padding:16px; text-align:center; color:var(--text-muted); font-size:13px;">
                        Qidirish uchun matn yoki raqam kiriting...
                    </div>
                </div>
                <div class="spotlight-footer">
                    <span>💡 Tezkor navigatsiya: Sotuvlar, Mijozlar, To'lovlar</span>
                    <span>Azer ERP 2.0</span>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        const input = document.getElementById('spotlightSearchInput');
        let searchTimeout = null;
        input.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => handleSpotlightSearch(input.value.trim()), 250);
        });

        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && overlay.classList.contains('active')) {
                closeSpotlightSearch();
            }
        });
    }

    overlay.classList.add('active');
    setTimeout(() => {
        const input = document.getElementById('spotlightSearchInput');
        if (input) {
            input.value = '';
            input.focus();
            handleSpotlightSearch('');
        }
    }, 100);
};

window.closeSpotlightSearch = function() {
    const overlay = document.getElementById('spotlightOverlay');
    if (overlay) overlay.classList.remove('active');
};

async function handleSpotlightSearch(query) {
    const container = document.getElementById('spotlightResultsList');
    if (!container) return;

    if (!query) {
        container.innerHTML = `
            <div style="padding:12px 14px; font-weight:700; font-size:12px; color:var(--text-muted); text-transform:uppercase;">Tezkor Bo'limlar</div>
            <a href="/" class="spotlight-item">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:18px;">📊</span>
                    <div>
                        <div style="font-weight:700; font-size:14px;">Dashboard</div>
                        <div style="font-size:12px; color:var(--text-muted);">Asosiy tahlillar va kassa qoldiqlari</div>
                    </div>
                </div>
                <span style="font-size:12px; color:var(--primary-blue);">O'tish ➔</span>
            </a>
            <a href="/static/demands.html" class="spotlight-item">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:18px;">📦</span>
                    <div>
                        <div style="font-weight:700; font-size:14px;">Sotuvlar (Demands)</div>
                        <div style="font-size:12px; color:var(--text-muted);">Barcha yuk xatlari va buyurtmalar</div>
                    </div>
                </div>
                <span style="font-size:12px; color:var(--primary-blue);">O'tish ➔</span>
            </a>
            <a href="/static/customers.html" class="spotlight-item">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:18px;">👥</span>
                    <div>
                        <div style="font-weight:700; font-size:14px;">Mijozlar</div>
                        <div style="font-size:12px; color:var(--text-muted);">Kontragentlar, qarzlar va akt sverka</div>
                    </div>
                </div>
                <span style="font-size:12px; color:var(--primary-blue);">O'tish ➔</span>
            </a>
            <a href="/static/payments.html" class="spotlight-item">
                <div style="display:flex; align-items:center; gap:10px;">
                    <span style="font-size:18px;">💳</span>
                    <div>
                        <div style="font-weight:700; font-size:14px;">To'lovlar & Kassa</div>
                        <div style="font-size:12px; color:var(--text-muted);">Kirim, chiqim va valyuta oqimi</div>
                    </div>
                </div>
                <span style="font-size:12px; color:var(--primary-blue);">O'tish ➔</span>
            </a>
        `;
        return;
    }

    container.innerHTML = `<div style="padding:16px; text-align:center; color:var(--text-muted);">⏳ Qidirilmoqda...</div>`;

    try {
        const [demandsResp, custResp] = await Promise.allSettled([
            apiFetch(`/demands?limit=5&offset=0&search=${encodeURIComponent(query)}`),
            apiFetch(`/customers?limit=5&offset=0&search=${encodeURIComponent(query)}`)
        ]);

        let html = '';
        let foundAny = false;

        // Mijozlar
        if (custResp.status === 'fulfilled' && custResp.value && custResp.value.data && custResp.value.data.length > 0) {
            foundAny = true;
            html += `<div style="padding:8px 14px 4px; font-weight:700; font-size:12px; color:var(--text-muted); text-transform:uppercase;">Mijozlar</div>`;
            custResp.value.data.forEach(c => {
                html += `
                    <a href="/static/customers.html?customer_id=${c.id}" class="spotlight-item">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <span style="font-size:18px;">👤</span>
                            <div>
                                <div style="font-weight:700; font-size:14px;">${c.name}</div>
                                <div style="font-size:12px; color:var(--text-muted);">${c.phone || 'Telefon kiritilmagan'}</div>
                            </div>
                        </div>
                        <span style="font-weight:700; font-size:13px; color:var(--text);">${formatMoney(c.debt || 0)}</span>
                    </a>
                `;
            });
        }

        // Sotuvlar
        if (demandsResp.status === 'fulfilled' && demandsResp.value && demandsResp.value.data && demandsResp.value.data.length > 0) {
            foundAny = true;
            html += `<div style="padding:8px 14px 4px; font-weight:700; font-size:12px; color:var(--text-muted); text-transform:uppercase;">Sotuvlar</div>`;
            demandsResp.value.data.forEach(d => {
                html += `
                    <a href="/static/demands.html?search=${encodeURIComponent(d.name)}" class="spotlight-item">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <span style="font-size:18px;">📦</span>
                            <div>
                                <div style="font-weight:700; font-size:14px;">№ ${d.name} — ${d.agent_name || ''}</div>
                                <div style="font-size:12px; color:var(--text-muted);">${d.moment || ''}</div>
                            </div>
                        </div>
                        <span style="font-weight:700; font-size:13px; color:var(--success);">${formatMoney(d.sum || 0)}</span>
                    </a>
                `;
            });
        }

        if (!foundAny) {
            html = `<div style="padding:20px; text-align:center; color:var(--text-muted);">"${query}" bo'yicha hech narsa topilmadi</div>`;
        }

        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = `<div style="padding:16px; text-align:center; color:var(--danger);">Qidiruvda xatolik yuz berdi</div>`;
    }
}

window.toggleNotifications = function(btn) {
    let notifWrapper = document.getElementById('navNotificationsWrapper');
    if (!notifWrapper) {
        notifWrapper = document.createElement('div');
        notifWrapper.id = 'navNotificationsWrapper';
        notifWrapper.className = 'notifications-wrapper';
        btn.parentNode.insertBefore(notifWrapper, btn);
        notifWrapper.appendChild(btn);

        const menu = document.createElement('div');
        menu.className = 'notifications-dropdown-menu';
        menu.id = 'notificationsDropdownMenu';
        menu.innerHTML = `
            <div class="notif-header">
                <span>🔔 Bildirishnomalar Markazi</span>
                <button onclick="triggerSyncNow()" style="border:none; background:transparent; color:var(--primary-blue); font-size:12px; font-weight:700; cursor:pointer;">Sinxronlash</button>
            </div>
            <div class="notif-item">
                <div class="notif-icon">💳</div>
                <div>
                    <div class="notif-title">Kassa Qoldiqlari</div>
                    <div class="notif-desc">Kassa & hisoblar balansi har 3 daqiqada MoySklad bilan yangilanadi.</div>
                </div>
            </div>
            <div class="notif-item">
                <div class="notif-icon">🔄</div>
                <div>
                    <div class="notif-title">Sinxronizatsiya Holati</div>
                    <div class="notif-desc">Mahalliy SQLite kesh faol rejimda tezkor ishlamoqda.</div>
                </div>
            </div>
            <div class="notif-item">
                <div class="notif-icon">🚨</div>
                <div>
                    <div class="notif-title">Qarzdorlik Nazorati</div>
                    <div class="notif-desc">Mijozlar sahifasida qarzlar va akt sverka tahlilini ko'rishingiz mumkin.</div>
                </div>
            </div>
        `;
        notifWrapper.appendChild(menu);
    }

    notifWrapper.classList.toggle('open');
};

function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    const isDark = savedTheme === 'dark';
    if (isDark) {
        document.body.classList.add('dark-mode');
    } else {
        document.body.classList.remove('dark-mode');
    }
    updateThemeIcons(isDark);
}

function updateThemeIcons(isDark) {
    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
        btn.textContent = isDark ? '☀️' : '🌙';
        btn.title = isDark ? 'Kunduzgi rejim (Variant 7)' : 'Kechki rejim (Variant 10)';
    });
}

// ================= DAY/NIGHT THEME TOGGLE =================
window.toggleTheme = function() {
    const isDark = document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    updateThemeIcons(isDark);
};

// ================= TOAST BILDIRISHNOMALARI (AUTO-DISMISS ON NEXT ACTION) =================
let activeToasts = [];

function dismissAllToasts() {
    if (!activeToasts || activeToasts.length === 0) return;
    activeToasts.forEach(toast => {
        if (toast && toast.parentElement) {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(12px) scale(0.95)';
            setTimeout(() => {
                try { toast.remove(); } catch(e) {}
            }, 250);
        }
    });
    activeToasts = [];
}

// Foydalanuvchi ekranning istalgan joyiga bosganda yoki klaviatura bosganda xabar avtomatik yo'qoladi
if (typeof window !== 'undefined') {
    window.addEventListener('pointerdown', (e) => {
        if (!e.target.closest('#toast-container')) {
            dismissAllToasts();
        }
    }, { capture: true, passive: true });

    window.addEventListener('keydown', () => {
        dismissAllToasts();
    }, { capture: true, passive: true });
}

function showToast(message, type = 'info') {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = `
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 999999;
            display: flex;
            flex-direction: column;
            gap: 10px;
            pointer-events: none;
        `;
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    const bgColors = {
        success: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        error: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
        warning: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
        info: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
    };
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️',
    };

    toast.style.cssText = `
        background: ${bgColors[type] || '#1e293b'};
        color: #ffffff;
        padding: 12px 20px;
        border-radius: 10px;
        box-shadow: 0 12px 28px rgba(0,0,0,0.22), 0 2px 6px rgba(0,0,0,0.12);
        font-size: 13.5px;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 250px;
        max-width: 420px;
        pointer-events: auto;
        cursor: pointer;
        opacity: 0;
        transform: translateY(12px) scale(0.95);
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    `;

    toast.innerHTML = `<span style="font-size:16px;">${icons[type] || 'ℹ️'}</span><span style="flex:1;">${message}</span>`;
    
    toast.onclick = () => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(12px) scale(0.95)';
        setTimeout(() => {
            try { toast.remove(); } catch(e) {}
            activeToasts = activeToasts.filter(t => t !== toast);
        }, 200);
    };

    container.appendChild(toast);
    activeToasts.push(toast);

    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateY(0) scale(1)';
    });

    setTimeout(() => {
        if (toast && toast.parentElement) {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(12px) scale(0.95)';
            setTimeout(() => {
                try { toast.remove(); } catch(e) {}
                activeToasts = activeToasts.filter(t => t !== toast);
            }, 250);
        }
    }, 3500);
}

// Barcha muvaffaqiyatli saqlash alert'larini avtomatik pastdagi yashil toastga aylantirish
if (typeof window !== 'undefined') {
    window.showToast = showToast;

    window.handleSupplyComingSoon = function(e) {
        if (e) {
            e.preventDefault();
            e.stopPropagation();
        }
        showToast("🏬 'Asosiy ombor' bo'limi hozirda takomillashtirilmoqda va tez orada ishga tushiriladi!", "warning");
        return false;
    };

    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('a[href="/supply"], a[href="/static/supply.html"]').forEach(a => {
            a.addEventListener('click', (e) => {
                window.handleSupplyComingSoon(e);
            });
        });

        // Agar URL da ?supply_soon=1 parametri bo'lsa xabar berish
        const params = new URLSearchParams(window.location.search);
        if (params.get('supply_soon')) {
            setTimeout(() => {
                window.handleSupplyComingSoon();
                const cleanUrl = window.location.pathname;
                window.history.replaceState({}, document.title, cleanUrl);
            }, 300);
        }
    });

    const _origAlert = window.alert;
    window.alert = function(msg) {
        if (typeof msg === 'string' && (msg.includes('✅') || msg.toLowerCase().includes('saqlandi') || msg.toLowerCase().includes('muvaffaqiyatli'))) {
            showToast(msg, 'success');
            return;
        }
        _origAlert(msg);
    };
}

// ================= SINXRONIZATSIYA =================
async function triggerSyncNow() {
    try {
        showToast("Sinxronizatsiya orqa fonda boshlandi...", "info");
        const resp = await apiFetch('/webhooks/sync-now', { method: 'POST' });
        if (resp.success) {
            showToast("MoySklad bilan sinxronizatsiya yakunlanmoqda...", "success");
            // Agar sotuvlar yoki mijozlar sahifasida bo'lsa, ma'lumotlarni yangilash
            if (typeof loadDemands === 'function') {
                setTimeout(() => loadDemands(), 1500);
                setTimeout(() => loadDemands(), 4000);
            }
            if (typeof loadCustomers === 'function') {
                setTimeout(() => loadCustomers(true), 1500);
                setTimeout(() => loadCustomers(), 4000);
            }
        }
    } catch (e) {
        showToast("Sinxronizatsiyada xatolik: " + e.message, "error");
    }
}

// ================= VALYUTA VA FORMATLASH =================
async function fetchUSDRate() {
    try {
        const resp = await apiFetch('/currency');
        if (resp.success && resp.data) {
            if (resp.data.usd_rate) {
                window.currentUSDRate = resp.data.usd_rate;
            }
            if (resp.data.cbu) {
                window.cbuRateInfo = resp.data.cbu;
            }
            return resp.data;
        }
    } catch (e) {
        console.warn('Valyuta kursi yuklanmadi:', e);
    }
    return null;
}

function formatNumber(num, preserveDecimals = false) {
    if (num === undefined || num === null || num === '') return "0";
    if (typeof num === 'string') {
        num = num.replace(/[\s\u00A0]/g, '').replace(/,/g, '.');
    }
    const n = Number(num);
    if (isNaN(n)) return "0";
    
    const hasDecimals = Math.abs(n % 1) > 0.001;
    if (!preserveDecimals && !hasDecimals) {
        const rounded = Math.round(n);
        return rounded.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    } else {
        const fixed = typeof num === 'string' && num.includes('.') ? num : n.toFixed(2);
        const parts = String(fixed).split('.');
        const intPart = Math.trunc(Number(parts[0])).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
        return parts.length > 1 ? `${intPart}.${parts[1]}` : intPart;
    }
}
window.formatNumber = formatNumber;

window.parseAmount = function(val) {
    if (val === undefined || val === null) return 0;
    if (typeof val === 'number') return isNaN(val) ? 0 : val;
    const clean = String(val).replace(/[\s\u00A0]/g, '').replace(/,/g, '.');
    const n = parseFloat(clean);
    return isNaN(n) ? 0 : n;
};

function formatMoney(amount) {
    if (amount === undefined || amount === null || isNaN(amount)) return "0 so'm";
    const n = Number(amount);
    if (Math.abs(n % 1) > 0.001) {
        return formatNumber(n.toFixed(2), true) + " so'm";
    }
    return formatNumber(amount) + " so'm";
}

function formatUSD(amountUzs, customRate) {
    const rate = customRate || window.currentUSDRate || 11800.0;
    if (!amountUzs || isNaN(amountUzs) || rate <= 0) return "$0.00";
    const usd = amountUzs / rate;
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(usd);
}

function formatDual(amountUzs, customRate) {
    const uzsStr = formatMoney(amountUzs);
    const usdStr = formatUSD(amountUzs, customRate);
    return `${uzsStr} <span class="usd-badge" style="font-size:0.85em; opacity:0.85; font-weight:600; color:#16a34a; background:rgba(22,163,74,0.08); padding:2px 6px; border-radius:4px; margin-left:4px;">(${usdStr})</span>`;
}

// ================= SANA VA VAQTNI FORMATLASH (MOYSKLAD UTC+3 -> TOSHKENT UTC+5 SINXRON) =================
function parseMoySkladDate(dateStr) {
    if (!dateStr) return null;
    if (dateStr instanceof Date) return dateStr;
    try {
        let clean = String(dateStr).trim().replace(' ', 'T');
        // MoySklad serveri vaqti Moskva (UTC+3) da beriladi. Timezone bo'lmasa +03:00 qo'shamiz
        if (!clean.includes('+') && !clean.endsWith('Z')) {
            clean += '+03:00';
        }
        const d = new Date(clean);
        return isNaN(d.getTime()) ? new Date(dateStr) : d;
    } catch {
        return new Date(dateStr);
    }
}

function formatDate(dateStr) {
    if (!dateStr) return "—";
    try {
        const d = parseMoySkladDate(dateStr);
        if (!d || isNaN(d.getTime())) return dateStr;
        // O'zbekiston (Toshkent) vaqtida 24 soatlik aniq format
        const datePart = d.toLocaleDateString('uz-UZ', { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'Asia/Tashkent' });
        const timePart = d.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Tashkent' });
        return `${datePart} ${timePart}`;
    } catch {
        return dateStr;
    }
}

// ================= UNIVERSAL MODAL Z-INDEX STACKING =================
window.highestModalZIndex = 1100;
window.bringModalToFront = function(modal) {
    if (!modal) return;
    if (typeof modal === 'string') modal = document.getElementById(modal);
    if (modal && modal.style) {
        window.highestModalZIndex += 10;
        modal.style.zIndex = window.highestModalZIndex;
    }
};

// Har bir modal ochilganda (class 'active' qo'shilganda) avtomatik ustki qatlamga ko'tarish
if (typeof MutationObserver !== 'undefined') {
    const modalObserver = new MutationObserver((mutations) => {
        mutations.forEach(m => {
            if (m.type === 'attributes' && m.attributeName === 'class') {
                const target = m.target;
                if (target && target.classList && target.classList.contains('modal') && target.classList.contains('active')) {
                    window.bringModalToFront(target);
                    if (window.initGhostZeros) {
                        window.initGhostZeros(target);
                    }
                }
            }
        });
    });

    const initModalObservers = () => {
        document.querySelectorAll('.modal').forEach(modal => {
            modalObserver.observe(modal, { attributes: true, attributeFilter: ['class'] });
        });
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initModalObservers);
    } else {
        initModalObservers();
    }
}

// ================= UNIVERSAL HAR 3 TA RAQAMDAN SO'NG BO'SH JOY QO'YISH VA GHOST ZERO =================
window.attachNumberFormatter = function(input) {
    if (!input || input.dataset.numFormatBound) return;
    input.dataset.numFormatBound = "true";

    // input[type="number"] brauzerda probellarni qabul qilmaydi, shuning uchun type="text" ga o'tkaziladi
    if (input.type === 'number') {
        input.type = 'text';
        input.inputMode = (input.step && input.step.includes('.')) ? 'decimal' : 'numeric';
    }

    const inputId = (input.id || '').toLowerCase();
    const allowNegative = inputId.includes('corr_') || input.dataset.allowNegative === 'true';
    const allowDecimal = inputId.includes('usd') || inputId.includes('rate') || input.inputMode === 'decimal' || input.dataset.allowDecimal === 'true' || (input.step && input.step.includes('.'));

    function formatInput() {
        const val = input.value;
        if (val === '' || val === undefined || val === null) return;

        const selStart = input.selectionStart ?? val.length;
        const textBeforeCursor = val.slice(0, selStart);
        const nonSpacesBefore = textBeforeCursor.replace(/[\s\u00A0]/g, '').length;

        const isNegative = allowNegative && val.trim().startsWith('-');

        let clean = val.replace(/[\s\u00A0]/g, '');
        if (allowDecimal) {
            clean = clean.replace(/,/g, '.');
        }

        const validCharsRegex = allowDecimal ? /[^0-9.]/g : /[^0-9]/g;
        clean = clean.replace(validCharsRegex, '');

        let intPart = clean;
        let decPart = '';
        let hasDot = false;
        if (allowDecimal && clean.includes('.')) {
            const firstDot = clean.indexOf('.');
            intPart = clean.slice(0, firstDot);
            decPart = clean.slice(firstDot + 1).replace(/\./g, '');
            hasDot = true;
        }

        let formattedInt = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
        let formatted = (isNegative ? '-' : '') + formattedInt;
        if (hasDot) {
            formatted += '.' + decPart;
        }

        if (input.value !== formatted) {
            input.value = formatted;
            let targetPos = 0;
            let count = 0;
            for (let i = 0; i < formatted.length; i++) {
                if (formatted[i] !== ' ') {
                    count++;
                }
                if (count === nonSpacesBefore) {
                    targetPos = i + 1;
                    break;
                }
            }
            if (nonSpacesBefore === 0) {
                targetPos = (isNegative && formatted.startsWith('-')) ? 1 : 0;
            }
            try {
                input.setSelectionRange(targetPos, targetPos);
            } catch (e) {}
        }
    }

    input.addEventListener('input', formatInput);

    // Probeldan keyin Backspace bosilganda oldingi raqamni to'g'ridan-to'g'ri o'chirish
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace') {
            const start = input.selectionStart;
            const end = input.selectionEnd;
            if (start === end && start > 0 && input.value[start - 1] === ' ') {
                e.preventDefault();
                const val = input.value;
                input.value = val.slice(0, start - 2) + val.slice(start);
                try {
                    input.setSelectionRange(start - 2, start - 2);
                } catch (err) {}
                formatInput();
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }
    });

    input.addEventListener('focus', () => {
        if (input.value === '0' || input.value === '0.00' || input.value === '0,00') {
            input.value = '';
        }
    });

    input.addEventListener('blur', () => {
        if (input.value.trim() === '') {
            // Bo'sh qolsa placeholder="0" ko'rinadi
        } else {
            formatInput();
        }
    });

    // Agar boshlang'ich qiymat bo'lsa darhol formatlaymiz
    if (input.value && input.value !== '0') {
        formatInput();
    }
};

window.initGhostZeros = function(container = document) {
    if (!container || !container.querySelectorAll) container = document;
    const selector = [
        'input.format-number',
        'input.amount-input',
        'input.ghost-zero',
        'input[data-format-number]',
        'input[type="number"]',
        '#pay_cash',
        '#pay_card',
        '#pay_usd',
        '#pay_usd_rate',
        '#corr_adjustment_sum',
        '#corr_final_balance',
        '#payCashAmount',
        '#payCardAmount',
        '#expenseAmount',
        '#newUsdRateInput',
        '#adjNewBalance',
        '#editPayAmount',
        '#editPayUsdAmount',
        '#editPayUsdRate',
        '#cashAmount',
        '#cardAmount',
        '#usdAmount',
        '#usdRate',
        '#purchasePrice',
        '#salePrice',
        '.demand-alloc-input'
    ].join(',');

    container.querySelectorAll(selector).forEach(input => {
        if (input.type === 'date' || input.type === 'datetime-local' || input.type === 'checkbox' || input.type === 'radio' || input.type === 'hidden' || input.type === 'file') return;
        if (input.id === 'searchInput' || input.id.includes('phone') || input.id.includes('Moment') || input.id.includes('Reason') || input.id.includes('Desc') || input.id.includes('Name')) return;

        if (!input.placeholder && input.placeholder !== '0') input.placeholder = "0";
        window.attachNumberFormatter(input);
    });
};

document.addEventListener('DOMContentLoaded', () => {
    window.initGhostZeros();
});