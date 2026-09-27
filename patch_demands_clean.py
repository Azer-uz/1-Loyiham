import os

demands_js_path = os.path.join(os.path.dirname(__file__), 'frontend', 'js', 'demands.js')

with open(demands_js_path, 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Top variables & loadPaymentSettings
old_top = """// ===== GLOBAL O'ZGARUVCHILAR =====
let currentOffset = 0;
const pageSize = 50;
let totalSize = 0;
let currentPeriod = 'today';
let currentStateFilter = 'all';
let currentEditDemand = null;
let demandStates = [];
let orgAccounts = [];
let oplataAttribute = null;
let currentLoadedDemands = [];
let currentOrgName = 'Said_Baraka';
let appPaymentMethods = [];
let appAccountsList = [];
let appReferenceRate = 12850;

// ===== SARALASH HOLATI =====
let demandSortField = null;
let demandSortDir = 'asc';

async function loadPaymentSettings() {
    try {
        const [methodsResp, accsResp, rateResp] = await Promise.all([
            apiFetch('/settings/payment-methods').catch(() => null),
            apiFetch('/settings/accounts').catch(() => null),
            apiFetch('/settings/reference-rate').catch(() => null)
        ]);
        if (methodsResp && methodsResp.success && methodsResp.data) {
            appPaymentMethods = methodsResp.data.methods || (Array.isArray(methodsResp.data) ? methodsResp.data : []);
            const usdM = appPaymentMethods.find(m => m.id === 'usd' || m.currency === 'USD');
            if (usdM && usdM.default_rate) {
                appReferenceRate = usdM.default_rate;
            }
        }
        if (accsResp && accsResp.success && accsResp.data) {
            appAccountsList = accsResp.data.accounts || (Array.isArray(accsResp.data) ? accsResp.data : []);
        }
        if (rateResp && rateResp.success && rateResp.data && rateResp.data.rate && !appPaymentMethods.some(m => (m.id === 'usd' || m.currency === 'USD') && m.default_rate)) {
            appReferenceRate = rateResp.data.rate;
        }
        window.appReferenceRate = appReferenceRate;
    } catch (e) {
        console.warn("To'lov sozlamalarini olishda xatolik:", e);
    }
}"""

new_top = """// ===== GLOBAL O'ZGARUVCHILAR =====
let currentOffset = 0;
const pageSize = 50;
let totalSize = 0;
let currentPeriod = 'today';
let currentStateFilter = 'all';
let currentEditDemand = null;
let demandStates = [];
let orgAccounts = [];
let oplataAttribute = null;
let currentLoadedDemands = [];
let currentOrgName = 'Said_Baraka';
let appPaymentMethods = [];
let appAccountsList = [];
let appReferenceRate = 12850;
let appCustomers = [];
window.allLoadedCustomers = [];

// ===== SARALASH HOLATI =====
let demandSortField = null;
let demandSortDir = 'asc';

async function loadPaymentSettings() {
    try {
        const [methodsResp, accsResp, rateResp, custResp] = await Promise.all([
            apiFetch('/settings/payment-methods').catch(() => null),
            apiFetch('/settings/accounts').catch(() => null),
            apiFetch('/settings/reference-rate').catch(() => null),
            apiFetch('/customers?limit=2000').catch(() => null)
        ]);
        if (custResp && custResp.success && custResp.data) {
            window.allLoadedCustomers = Array.isArray(custResp.data) ? custResp.data : (custResp.data.customers || []);
            appCustomers = window.allLoadedCustomers;
        }
        if (methodsResp && methodsResp.success && methodsResp.data) {
            appPaymentMethods = methodsResp.data.methods || (Array.isArray(methodsResp.data) ? methodsResp.data : []);
            const usdM = appPaymentMethods.find(m => m.id === 'usd' || m.currency === 'USD');
            if (usdM && usdM.default_rate) {
                appReferenceRate = usdM.default_rate;
            }
        }
        if (accsResp && accsResp.success && accsResp.data) {
            appAccountsList = accsResp.data.accounts || (Array.isArray(accsResp.data) ? accsResp.data : []);
        }
        if (rateResp && rateResp.success && rateResp.data && rateResp.data.rate && !appPaymentMethods.some(m => (m.id === 'usd' || m.currency === 'USD') && m.default_rate)) {
            appReferenceRate = rateResp.data.rate;
        }
        window.appReferenceRate = appReferenceRate;
    } catch (e) {
        console.warn("To'lov sozlamalarini olishda xatolik:", e);
    }
}"""

if old_top in code:
    code = code.replace(old_top, new_top)
    print("Step 1: Top variables replaced")
else:
    print("ERROR in step 1")

# 2. Replace topbar in renderEditForm
old_topbar = """                <!-- Mijoz nomi va yangi tabda ochish silkasi -->
                <div class="agent-info-badge">
                    <span style="font-size:11px; color:var(--text-light); text-transform:uppercase; font-weight:700;">Mijoz:</span>
                    <a href="/customers?id=${encodeURIComponent(demand.agent_id || '')}" target="_blank" class="agent-name-link" onclick="openCustomerProfile(event, '${demand.agent_id || ''}')" title="Mijoz kartochkasini ochish (yangi oyna)">
                        <span>👤</span> <strong>${demand.agent_name}</strong>
                        <span style="font-size:11px; opacity:0.75;">↗️</span>
                    </a>
                </div>
                
                <!-- Mijozning joriy umumiy balansi / qarzi -->
                <div class="customer-balance-badge ${currentBalance > 0 ? 'debt' : (currentBalance < 0 ? 'credit' : 'zero')}" title="Mijozning barcha operatsiyalar bo'yicha jami balansi">
                    <span class="badge-label">${currentBalance > 0 ? 'Qarzi:' : (currentBalance < 0 ? 'Haqi:' : 'Balans:')}</span>
                    <strong class="badge-value">${formatMoney(Math.abs(currentBalance))}</strong>
                </div>"""

new_topbar = """                <!-- Mijoz tanlash (Yangi sotuv yoki mavjud sotuv) -->
                <div class="agent-info-badge" style="display:flex; align-items:center; gap:6px;">
                    <span style="font-size:11px; color:var(--text-light); text-transform:uppercase; font-weight:700;">Mijoz:</span>
                    <div style="position:relative; display:flex; align-items:center; gap:6px;">
                        <div style="position:relative; min-width:240px;">
                            <input type="text" id="customerSearchInput" class="form-control" 
                                placeholder="🔍 Mijozni qidirish yoki tanlash..." 
                                value="${(demand.agent_name || '').replace(/"/g, '&quot;')}" 
                                autocomplete="off" 
                                style="font-size:13px; font-weight:700; padding:6px 10px; border-radius:6px; width:100%; border:1.5px solid #0284c7; background:#fff;"
                                onfocus="showCustomerDropdownList()"
                                oninput="filterCustomerDropdownList(this.value)"
                            />
                            <input type="hidden" id="editCustomerSelect" value="${demand.agent_id || ''}">
                            
                            <div id="customerSuggestionsList" style="display:none; position:absolute; top:100%; left:0; right:0; max-height:220px; overflow-y:auto; background:#fff; border:1.5px solid #0284c7; border-top:none; border-radius:0 0 8px 8px; z-index:9999; box-shadow:0 8px 20px rgba(0,0,0,0.18);">
                            </div>
                        </div>
                        <button type="button" class="btn-top-action btn-save-cust" onclick="openNewCustomerModal()" style="font-size:11.5px; padding:6px 10px; background:#16a34a; color:#fff; border-radius:6px; cursor:pointer; font-weight:700; white-space:nowrap;" title="Yangi mijoz yaratish">
                            ➕ Yangi
                        </button>
                        ${demand.agent_id ? `
                        <a href="/customers?id=${encodeURIComponent(demand.agent_id)}" target="_blank" class="agent-name-link" onclick="openCustomerProfile(event, '${demand.agent_id}')" title="Mijoz kartochkasini ochish" style="font-size:11px; padding:4px 8px;">
                            <span>↗️</span>
                        </a>
                        ` : ''}
                    </div>
                </div>
                
                <!-- Mijozning joriy umumiy balansi / qarzi -->
                <div id="editCustomerBalanceBadge" class="customer-balance-badge ${currentBalance > 0 ? 'debt' : (currentBalance < 0 ? 'credit' : 'zero')}" title="Mijozning barcha operatsiyalar bo'yicha jami balansi">
                    <span class="badge-label">${currentBalance > 0 ? 'Qarzi:' : (currentBalance < 0 ? 'Haqi:' : 'Balans:')}</span>
                    <strong class="badge-value">${formatMoney(Math.abs(currentBalance))}</strong>
                </div>"""

if old_topbar in code:
    code = code.replace(old_topbar, new_topbar)
    print("Step 2: Topbar replaced")
else:
    print("ERROR in step 2")

# 3. Update saveEdit customer reading
old_save_cust = """        const payload = {
            discount_type: discountType,"""

new_save_cust = """        const customerSelect = document.getElementById('editCustomerSelect');
        const chosenAgentId = customerSelect && customerSelect.value ? customerSelect.value : (currentEditDemand ? currentEditDemand.agent_id : null);
        if (!chosenAgentId) {
            alert("Iltimos, avval mijozni tanlang yoki yangi mijoz qo'shing!");
            saveBtn.disabled = false;
            saveBtn.textContent = '💾 Saqlash';
            return;
        }

        const payload = {
            agent_id: chosenAgentId,
            discount_type: discountType,"""

if old_save_cust in code:
    code = code.replace(old_save_cust, new_save_cust, 1)
    print("Step 3: saveEdit updated")
else:
    print("ERROR in step 3")

# 4. Append bottom helper functions
bottom_helpers = """

// ================= MIJOZLAR BILAN ISHLASH (AUTOCOMPLETE & YANGI MIJOZ) =================
async function ensureCustomersLoaded() {
    if (window.allLoadedCustomers && window.allLoadedCustomers.length > 0) return window.allLoadedCustomers;
    try {
        const cResp = await apiFetch('/customers?limit=2000');
        if (cResp && cResp.success && cResp.data) {
            window.allLoadedCustomers = Array.isArray(cResp.data) ? cResp.data : (cResp.data.customers || []);
            appCustomers = window.allLoadedCustomers;
            return window.allLoadedCustomers;
        }
    } catch (e) {
        console.warn("Mijozlar ro'yxati yuklanmadi:", e);
    }
    return [];
}

window.showCustomerDropdownList = function() {
    const list = document.getElementById('customerSuggestionsList');
    if (!list) return;
    window.filterCustomerDropdownList(document.getElementById('customerSearchInput')?.value || '');
    list.style.display = 'block';
};

window.filterCustomerDropdownList = function(query) {
    const list = document.getElementById('customerSuggestionsList');
    if (!list) return;
    const q = (query || '').toLowerCase().trim();
    const customers = window.allLoadedCustomers || [];
    
    const filtered = q ? customers.filter(c => 
        (c.name && c.name.toLowerCase().includes(q)) || 
        (c.phone && c.phone.toLowerCase().includes(q))
    ) : customers.slice(0, 60);

    if (filtered.length === 0) {
        list.innerHTML = `
            <div style="padding:10px 12px; font-size:12px; color:#64748b; text-align:center;">
                Mijoz topilmadi.
                <button type="button" onclick="openNewCustomerModal()" style="display:block; margin:6px auto 0; padding:4px 10px; font-size:12px; background:#16a34a; color:#fff; border-radius:4px; border:none; cursor:pointer;">➕ Yangi mijoz yaratish</button>
            </div>
        `;
    } else {
        list.innerHTML = filtered.map(c => {
            const bal = Number(c.balance || 0);
            const balText = bal > 0 ? `<span style="color:#ef4444;font-size:11px;font-weight:700;">(Qarz: ${formatMoney(bal)})</span>` : (bal < 0 ? `<span style="color:#16a34a;font-size:11px;font-weight:700;">(Haq: ${formatMoney(Math.abs(bal))})</span>` : '');
            return `
                <div class="customer-suggest-item" onclick="selectCustomerFromList('${c.id}', '${(c.name || '').replace(/'/g, "\\\\'")}')" style="padding:7px 12px; cursor:pointer; font-size:12.5px; border-bottom:1px solid #f1f5f9; display:flex; justify-content:space-between; align-items:center; transition:background 0.15s;" onmouseover="this.style.background='#f0f9ff'" onmouseout="this.style.background='transparent'">
                    <div>
                        <strong style="color:var(--text-color);">👤 ${c.name}</strong>
                        ${c.phone ? `<span style="color:#64748b;font-size:11.5px;margin-left:6px;">📞 ${c.phone}</span>` : ''}
                    </div>
                    <div>${balText}</div>
                </div>
            `;
        }).join('');
    }
    list.style.display = 'block';
};

window.selectCustomerFromList = async function(id, name) {
    const input = document.getElementById('customerSearchInput');
    const hidden = document.getElementById('editCustomerSelect');
    const list = document.getElementById('customerSuggestionsList');
    
    if (input) input.value = name;
    if (hidden) hidden.value = id;
    if (list) list.style.display = 'none';

    if (currentEditDemand) {
        currentEditDemand.agent_id = id;
        currentEditDemand.agent_name = name;
    }

    let bal = 0;
    if (id) {
        try {
            const bResp = await apiFetch(`/payments/balance/${id}`);
            if (bResp && bResp.success && bResp.data) {
                bal = bResp.data.balance || 0;
            }
        } catch(e) {}
    }
    const badgeEl = document.getElementById('editCustomerBalanceBadge');
    if (badgeEl) {
        badgeEl.className = `customer-balance-badge ${bal > 0 ? 'debt' : (bal < 0 ? 'credit' : 'zero')}`;
        badgeEl.innerHTML = `<span class="badge-label">${bal > 0 ? 'Qarzi:' : (bal < 0 ? 'Haqi:' : 'Balans:')}</span><strong class="badge-value">${formatMoney(Math.abs(bal))}</strong>`;
    }
    recalculateTotals();
};

window.onCustomerSelectChange = function(customerId) {
    const found = (window.allLoadedCustomers || []).find(c => c.id === customerId);
    window.selectCustomerFromList(customerId, found ? found.name : '');
};

async function showCreateDemand(preselectedCustomerId = null, preselectedCustomerName = null) {
    if (!appPaymentMethods || appPaymentMethods.length === 0) {
        await loadPaymentSettings();
    }
    await ensureCustomersLoaded();

    let custName = preselectedCustomerName || '';
    if (preselectedCustomerId && !custName) {
        const found = (window.allLoadedCustomers || []).find(c => c.id === preselectedCustomerId);
        if (found) custName = found.name;
    }

    let initialBalance = 0;
    if (preselectedCustomerId) {
        try {
            const bResp = await apiFetch(`/payments/balance/${preselectedCustomerId}`);
            if (bResp && bResp.success && bResp.data) {
                initialBalance = bResp.data.balance || 0;
            }
        } catch(e) {}
    }

    const newDemand = {
        id: 'new',
        name: 'Yangi Sotuv',
        moment: new Date().toISOString(),
        agent_id: preselectedCustomerId || '',
        agent_name: custName || '',
        positions: [],
        sum: 0,
        discount: 0
    };
    currentEditDemand = newDemand;
    
    document.getElementById('editModal').classList.add('active');
    renderEditForm(newDemand, {payments:[], total_paid:0}, initialBalance);
}

// Click outside suggestions list to close
document.addEventListener('click', (e) => {
    const list = document.getElementById('customerSuggestionsList');
    const input = document.getElementById('customerSearchInput');
    if (list && input && !input.contains(e.target) && !list.contains(e.target)) {
        list.style.display = 'none';
    }
});

// ===== YANGI MIJOZ =====
function openNewCustomerModal() {
    const n = document.getElementById('newCustName');
    const p = document.getElementById('newCustPhone');
    const d = document.getElementById('newCustDesc');
    if (n) n.value = '';
    if (p) p.value = '';
    if (d) d.value = '';
    const modal = document.getElementById('newCustomerModal');
    if (modal) modal.classList.add('active');
}

function closeNewCustomerModal() {
    const modal = document.getElementById('newCustomerModal');
    if (modal) modal.classList.remove('active');
}

async function handleNewCustomerSubmit(e) {
    e.preventDefault();
    const name = document.getElementById('newCustName')?.value?.trim();
    const phone = document.getElementById('newCustPhone')?.value?.trim();
    const desc = document.getElementById('newCustDesc')?.value?.trim();

    if(!name) {
        alert("Iltimos, mijoz ismini kiriting!");
        return;
    }

    const btn = document.getElementById('saveNewCustomerBtn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '⏳...';
    }

    try {
        const payload = {
            name: name,
            phone: phone || '',
            description: desc || ''
        };
        const resp = await apiFetch('/customers', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        
        if(resp && resp.success) {
            alert('✅ Mijoz yaratildi!');
            closeNewCustomerModal();
            
            window.allLoadedCustomers = [];
            await ensureCustomersLoaded();
            window.selectCustomerFromList(resp.data.id, resp.data.name);
        } else {
            throw new Error(resp?.detail || 'Xatolik');
        }
    } catch(err) {
        alert('❌ Xato: ' + err.message);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '💾 Saqlash';
        }
    }
}
"""

code += bottom_helpers
with open(demands_js_path, 'w', encoding='utf-8') as f:
    f.write(code)

print("SUCCESSFULLY APPLIED ALL PATCHES TO demands.js")
