import codecs

with codecs.open('frontend/js/demands.js', 'r', 'utf-8') as f:
    js = f.read()

if 'let appCustomers = [];' not in js:
    js = js.replace('let allDemands = [];', 'let allDemands = [];\nlet appCustomers = [];\n')

load_cust = """
    try {
        const resp = await apiFetch('/customers');
        if (resp && resp.success && resp.data) {
            appCustomers = resp.data.customers || [];
        }
    } catch(e) {}
"""
if "apiFetch('/customers')" not in js:
    js = js.replace('async function loadPaymentSettings() {', 'async function loadPaymentSettings() {\n' + load_cust)

target_customer_html = """                        <div class="edit-agent-name">👤 ${demand.agent_name} <br>
                            <small style="color:var(--text-light);font-size:12px;">Qarz: <span class="${currentBalance < 0 ? 'debt-text' : 'credit-text'}">${formatCustomerBalance(currentBalance)}</span></small>
                        </div>"""

new_customer_html = """                        <div class="edit-agent-name">
                            <select id="editCustomerSelect" class="form-control" style="font-weight:bold; margin-bottom: 5px;">
                                <option value="">👤 Mijozni tanlang...</option>
                                ${appCustomers.map(c => `<option value="${c.id}" ${c.id === demand.agent_id ? 'selected' : ''}>👤 ${c.name}</option>`).join('')}
                            </select>
                            <small style="color:var(--text-light);font-size:12px;">Qarz: <span class="${currentBalance < 0 ? 'debt-text' : 'credit-text'}">${formatCustomerBalance(currentBalance)}</span></small>
                        </div>"""
js = js.replace(target_customer_html, new_customer_html)

if "const customerSelect = document.getElementById('editCustomerSelect');" not in js:
    js = js.replace('const payload = {', "const customerSelect = document.getElementById('editCustomerSelect');\n    const payload = {\n        agent_id: customerSelect && customerSelect.value ? customerSelect.value : currentEditDemand.agent_id,\n")

create_fn = """
async function showCreateDemand() {
    if (!appPaymentMethods || appPaymentMethods.length === 0) {
        await loadPaymentSettings();
    }
    const newDemand = {
        id: 'new',
        name: 'Yangi',
        moment: new Date().toISOString(),
        agent_id: '',
        agent_name: '',
        positions: [],
        sum: 0,
        discount: 0
    };
    currentEditDemand = newDemand;
    
    document.getElementById('editModal').classList.add('active');
    
    renderEditForm(newDemand, {payments:[], total_paid:0}, 0);
}
"""
if 'showCreateDemand' not in js:
    js += '\n' + create_fn

with codecs.open('frontend/js/demands.js', 'w', 'utf-8') as f:
    f.write(js)
print('demands.js patched')
