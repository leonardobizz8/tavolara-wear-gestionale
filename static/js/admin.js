/**
 * Tavolara Wear — Admin Dashboard Logic
 * Full management: orders, analytics, stock variants, config, discounts, CSV export.
 */

// State
const adminState = {
  authenticated: false,
  orders: [],
  analytics: null,
  config: {},
  variants: [],
  discounts: []
};

// DOM References
const admDom = {
  loginOverlay: document.getElementById("login-overlay"),
  loginForm: document.getElementById("login-form"),
  adminPwd: document.getElementById("admin-pwd"),
  loginError: document.getElementById("login-error"),
  adminApp: document.getElementById("admin-app"),
  btnLogout: document.getElementById("btn-logout"),

  // Tabs
  tabs: document.querySelectorAll(".adm-tab"),
  tabContents: document.querySelectorAll(".adm-tab-content"),

  // KPIs
  kpiTotalOrders: document.getElementById("kpi-total-orders"),
  kpiTotalShirts: document.getElementById("kpi-total-shirts"),
  kpiPendingOrders: document.getElementById("kpi-pending-orders"),
  kpiPendingRev: document.getElementById("kpi-pending-rev"),
  kpiVerifiedOrders: document.getElementById("kpi-verified-orders"),
  kpiVerifiedRev: document.getElementById("kpi-verified-rev"),

  // Orders table & filters
  ordersTbody: document.getElementById("orders-tbody"),
  searchInput: document.getElementById("order-search-input"),
  filterStatus: document.getElementById("filter-status"),
  filterDelivery: document.getElementById("filter-delivery"),
  filterDateFrom: document.getElementById("filter-date-from"),
  filterDateTo: document.getElementById("filter-date-to"),
  btnResetFilters: document.getElementById("btn-reset-filters"),
  btnExportCsv: document.getElementById("btn-export-csv"),

  // Analytics
  analyticsSizesList: document.getElementById("analytics-sizes-list"),
  analyticsColorsList: document.getElementById("analytics-colors-list"),

  // Config & Bank forms
  configForm: document.getElementById("config-form"),
  cfgShirtPrice: document.getElementById("cfg-shirt-price"),
  cfgShippingLocker: document.getElementById("cfg-shipping-locker"),
  cfgShippingHome: document.getElementById("cfg-shipping-home"),
  cfgShippingHand: document.getElementById("cfg-shipping-hand"),

  bankForm: document.getElementById("bank-form"),
  cfgBankHolder: document.getElementById("cfg-bank-holder"),
  cfgBankIban: document.getElementById("cfg-bank-iban"),
  cfgBankName: document.getElementById("cfg-bank-name"),
  cfgBankNotes: document.getElementById("cfg-bank-notes"),

  // Variants
  variantsMatrixContainer: document.getElementById("variants-matrix-container"),

  // Discounts
  discountsTbody: document.getElementById("discounts-tbody"),
  btnOpenNewDiscount: document.getElementById("btn-open-new-discount"),
  newDiscountModal: document.getElementById("new-discount-modal"),
  btnCloseDiscountModal: document.getElementById("btn-close-discount-modal"),
  newDiscountForm: document.getElementById("new-discount-form"),
  discCodeInput: document.getElementById("disc-code"),
  discValueInput: document.getElementById("disc-value"),

  // Security
  pwdForm: document.getElementById("pwd-form"),
  newPasswordInput: document.getElementById("new-password"),

  // Order Details Modal
  orderModal: document.getElementById("order-modal"),
  modalOrderTitle: document.getElementById("modal-order-title"),
  modalOrderContent: document.getElementById("modal-order-content"),
  btnCloseModal: document.getElementById("btn-close-modal"),

  // Toast
  admToast: document.getElementById("adm-toast"),
  admToastText: document.getElementById("adm-toast-text")
};

function showAdmToast(msg) {
  admDom.admToastText.textContent = msg;
  admDom.admToast.classList.add("show");
  setTimeout(() => admDom.admToast.classList.remove("show"), 3000);
}

// Check session on start
async function checkAuth() {
  try {
    const res = await fetch("/api/admin/me");
    if (res.ok) {
      const data = await res.json();
      if (data.authenticated) {
        showApp();
        return;
      }
    }
  } catch (e) {
    // not logged in
  }
  showLogin();
}

function showLogin() {
  adminState.authenticated = false;
  admDom.loginOverlay.style.display = "flex";
  admDom.adminApp.style.display = "none";
}

function showApp() {
  adminState.authenticated = true;
  admDom.loginOverlay.style.display = "none";
  admDom.adminApp.style.display = "block";
  loadAllAdminData();
}

// Login form handler
admDom.loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const password = admDom.adminPwd.value.trim();
  admDom.loginError.style.display = "none";

  try {
    const res = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password })
    });
    const data = await res.json();
    if (res.ok && data.authenticated) {
      admDom.adminPwd.value = "";
      showApp();
      showAdmToast("Accesso effettuato con successo.");
    } else {
      admDom.loginError.textContent = data.message || "Password errata.";
      admDom.loginError.style.display = "block";
    }
  } catch (err) {
    admDom.loginError.textContent = "Errore di connessione.";
    admDom.loginError.style.display = "block";
  }
});

// Logout
admDom.btnLogout.addEventListener("click", async () => {
  try {
    await fetch("/api/admin/logout", { method: "POST" });
  } catch (e) {}
  showLogin();
  showAdmToast("Sessione terminata.");
});

// Tab Switcher
admDom.tabs.forEach(tab => {
  tab.addEventListener("click", () => {
    admDom.tabs.forEach(t => t.classList.remove("active"));
    admDom.tabContents.forEach(c => c.classList.remove("active"));

    tab.classList.add("active");
    const target = tab.getAttribute("data-tab");
    const content = document.getElementById(`tab-${target}`);
    if (content) content.classList.add("active");

    if (target === "analytics") loadAnalytics();
    if (target === "variants") loadVariants();
    if (target === "discounts") loadDiscounts();
    if (target === "config" || target === "bank") loadConfig();
  });
});

// Load all primary data
async function loadAllAdminData() {
  await Promise.all([
    loadOrders(),
    loadAnalytics(),
    loadConfig(),
    loadVariants(),
    loadDiscounts()
  ]);
}

// Load Orders with filters
async function loadOrders() {
  try {
    const params = new URLSearchParams();
    const search = admDom.searchInput.value.trim();
    const status = admDom.filterStatus.value;
    const delivery = admDom.filterDelivery.value;
    const dateFrom = admDom.filterDateFrom.value;
    const dateTo = admDom.filterDateTo.value;

    if (search) params.append("search", search);
    if (status) params.append("status", status);
    if (delivery) params.append("delivery", delivery);
    if (dateFrom) params.append("date_from", dateFrom);
    if (dateTo) params.append("date_to", dateTo);

    const res = await fetch(`/api/admin/orders?${params.toString()}`);
    if (!res.ok) {
      if (res.status === 401) showLogin();
      return;
    }
    const data = await res.json();
    adminState.orders = data.orders || [];
    renderOrdersTable();
  } catch (err) {
    console.error("Errore recupero ordini:", err);
  }
}

// Filter listeners
let searchDebounce = null;
admDom.searchInput.addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(loadOrders, 300);
});

admDom.filterStatus.addEventListener("change", loadOrders);
admDom.filterDelivery.addEventListener("change", loadOrders);
admDom.filterDateFrom.addEventListener("change", loadOrders);
admDom.filterDateTo.addEventListener("change", loadOrders);

admDom.btnResetFilters.addEventListener("click", () => {
  admDom.searchInput.value = "";
  admDom.filterStatus.value = "";
  admDom.filterDelivery.value = "";
  admDom.filterDateFrom.value = "";
  admDom.filterDateTo.value = "";
  loadOrders();
});

// Export CSV
admDom.btnExportCsv.addEventListener("click", () => {
  const params = new URLSearchParams();
  const search = admDom.searchInput.value.trim();
  const status = admDom.filterStatus.value;
  const delivery = admDom.filterDelivery.value;
  const dateFrom = admDom.filterDateFrom.value;
  const dateTo = admDom.filterDateTo.value;

  if (search) params.append("search", search);
  if (status) params.append("status", status);
  if (delivery) params.append("delivery", delivery);
  if (dateFrom) params.append("date_from", dateFrom);
  if (dateTo) params.append("date_to", dateTo);

  window.open(`/api/admin/export-csv?${params.toString()}`, "_blank");
});

// Helper: Status badge
function getStatusBadge(status) {
  let cls = "new";
  if (status === "In attesa di pagamento") cls = "pending";
  else if (status === "Pagamento verificato") cls = "verified";
  else if (status === "In preparazione") cls = "prep";
  else if (status === "Spedito / Consegnato") cls = "shipped";
  else if (status === "Annullato") cls = "cancelled";

  return `<span class="status-badge ${cls}">${status}</span>`;
}

// Render Orders Table
function renderOrdersTable() {
  if (adminState.orders.length === 0) {
    admDom.ordersTbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; padding: 40px; color: #728ea0;">
          Nessun ordine trovato con i filtri correnti.
        </td>
      </tr>
    `;
    return;
  }

  const validStatuses = [
    "Nuovo ordine",
    "In attesa di pagamento",
    "Pagamento verificato",
    "In preparazione",
    "Spedito / Consegnato",
    "Annullato"
  ];

  admDom.ordersTbody.innerHTML = adminState.orders.map(o => {
    const dateFormatted = new Date(o.created_at).toLocaleString("it-IT", {
      day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"
    });

    const itemsSummary = (o.items || []).map(it => {
      const sz = it.size === "XXXL" ? "3XL" : (it.size === "XXL" ? "2XL" : it.size);
      return `<strong>${it.color_name} ${sz}</strong> (x${it.quantity})`;
    }).join("<br>");

    let deliveryLabel = "";
    if (o.delivery_method === "locker") {
      deliveryLabel = `📦 Locker: ${o.locker_name || ""}`;
    } else if (o.delivery_method === "home") {
      deliveryLabel = `🏠 Domicilio: ${o.delivery_city || ""}`;
    } else {
      deliveryLabel = `🤝 A mano: ${o.hand_location || ""}`;
    }

    return `
      <tr>
        <td>
          <strong style="color: #142f48;">${o.order_number}</strong>
        </td>
        <td style="color: #567285; font-size: 12px; white-space: nowrap;">
          ${dateFormatted}
        </td>
        <td>
          <strong style="color: #142f48;">${o.customer_first_name} ${o.customer_last_name}</strong>
          <div style="font-size: 12px; color: #567285;">${o.customer_phone}</div>
          <div style="font-size: 11px; color: #8ba2b1;">${o.customer_email}</div>
        </td>
        <td>
          ${itemsSummary}
        </td>
        <td style="font-size: 12px;">
          ${deliveryLabel}
        </td>
        <td>
          <strong style="font-size: 15px; color: #003760;">${(o.total_amount || 0).toFixed(2)} €</strong>
        </td>
        <td>
          <select class="adm-select status-selector" data-order-id="${o.id}" style="font-weight: 600; font-size: 12px; padding: 6px 8px;">
            ${validStatuses.map(st => `
              <option value="${st}" ${st === o.status ? 'selected' : ''}>${st}</option>
            `).join('')}
          </select>
        </td>
        <td>
          <button type="button" class="adm-btn adm-btn-secondary btn-view-order" data-order-id="${o.id}" style="padding: 6px 10px; font-size: 12px;">
            Dettagli
          </button>
        </td>
      </tr>
    `;
  }).join("");

  // Attach status change events
  document.querySelectorAll(".status-selector").forEach(sel => {
    sel.addEventListener("change", async (e) => {
      const orderId = sel.getAttribute("data-order-id");
      const newStatus = sel.value;
      await updateOrderStatus(orderId, newStatus);
    });
  });

  // Attach details button events
  document.querySelectorAll(".btn-view-order").forEach(btn => {
    btn.addEventListener("click", () => {
      const orderId = parseInt(btn.getAttribute("data-order-id"));
      const order = adminState.orders.find(o => o.id === orderId);
      if (order) openOrderModal(order);
    });
  });
}

// Update Order Status
async function updateOrderStatus(orderId, status) {
  try {
    const res = await fetch(`/api/admin/orders/${orderId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status })
    });
    const data = await res.json();
    if (res.ok) {
      showAdmToast(data.message || "Stato aggiornato.");
      loadAnalytics(); // Refresh KPI counts
    } else {
      showAdmToast("Errore: " + (data.message || "Impossibile aggiornare."));
      loadOrders();
    }
  } catch (err) {
    showAdmToast("Errore di rete.");
    loadOrders();
  }
}

// Open Order Details Modal
function openOrderModal(order) {
  admDom.modalOrderTitle.textContent = `Ordine #${order.order_number}`;
  
  const itemsHtml = (order.items || []).map(it => `
    <div style="display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #edf2f6;">
      <span>${it.product_name} (${it.color_name}, taglia ${it.size}) × ${it.quantity}</span>
      <strong>${it.total_price.toFixed(2)} €</strong>
    </div>
  `).join("");

  let deliveryDetailHtml = "";
  if (order.delivery_method === "locker") {
    deliveryDetailHtml = `
      <p><strong>Locker / Punto:</strong> ${order.locker_name}</p>
      <p><strong>Indirizzo:</strong> ${order.delivery_address}, ${order.delivery_zip} ${order.delivery_city}</p>
      <p><strong>Note:</strong> ${order.delivery_notes || "Nessuna"}</p>
    `;
  } else if (order.delivery_method === "home") {
    deliveryDetailHtml = `
      <p><strong>Indirizzo:</strong> ${order.delivery_address}, ${order.delivery_zip} ${order.delivery_city} (${order.delivery_province})</p>
      <p><strong>Note corriere:</strong> ${order.delivery_notes || "Nessuna"}</p>
    `;
  } else {
    deliveryDetailHtml = `
      <p><strong>Località concordata:</strong> ${order.hand_location}</p>
      <p><strong>Preferenze cliente:</strong> ${order.hand_preferences || "Nessuna"}</p>
    `;
  }

  admDom.modalOrderContent.innerHTML = `
    <div style="font-size: 14px; line-height: 1.6;">
      <div style="background: #f8fafc; padding: 12px; border-radius: 8px; margin-bottom: 16px;">
        <p><strong>Data Creazione:</strong> ${new Date(order.created_at).toLocaleString("it-IT")}</p>
        <p><strong>Stato Attuale:</strong> ${getStatusBadge(order.status)}</p>
        <p><strong>Cliente:</strong> ${order.customer_first_name} ${order.customer_last_name}</p>
        <p><strong>Email:</strong> ${order.customer_email} | <strong>Tel:</strong> ${order.customer_phone}</p>
      </div>

      <h4 style="font-size: 14px; text-transform: uppercase; color: #567285; margin: 14px 0 6px;">Articoli Ordinati</h4>
      ${itemsHtml}

      <div style="margin: 12px 0; padding: 10px; background: #eef5f9; border-radius: 8px;">
        <div style="display: flex; justify-content: space-between;">
          <span>Subtotale capi:</span>
          <span>${((order.shirt_price || 0) * (order.items?.reduce((s, i) => s + i.quantity, 0) || 1)).toFixed(2)} €</span>
        </div>
        <div style="display: flex; justify-content: space-between;">
          <span>Spedizione:</span>
          <span>${(order.shipping_cost || 0).toFixed(2)} €</span>
        </div>
        ${order.discount_amount ? `
          <div style="display: flex; justify-content: space-between; color: #198754;">
            <span>Sconto (${order.discount_code}):</span>
            <span>- ${(order.discount_amount).toFixed(2)} €</span>
          </div>
        ` : ''}
        <div style="display: flex; justify-content: space-between; font-weight: 700; font-size: 16px; margin-top: 6px; padding-top: 6px; border-top: 1px solid #d3e1eb;">
          <span>Totale Ordine:</span>
          <span style="color: #003760;">${(order.total_amount || 0).toFixed(2)} €</span>
        </div>
      </div>

      <h4 style="font-size: 14px; text-transform: uppercase; color: #567285; margin: 14px 0 6px;">Dettagli Consegna</h4>
      <div style="background: #ffffff; border: 1px solid #edf2f6; padding: 12px; border-radius: 8px;">
        ${deliveryDetailHtml}
      </div>

      <h4 style="font-size: 14px; text-transform: uppercase; color: #567285; margin: 14px 0 6px;">Dati Bonifico</h4>
      <div style="background: #ffffff; border: 1px solid #edf2f6; padding: 12px; border-radius: 8px; font-family: monospace;">
        <p><strong>Causale:</strong> ${order.wire_causale}</p>
        <p><strong>Intestatario:</strong> ${order.bank_holder || "Tavolara Srl"}</p>
        <p><strong>IBAN:</strong> ${order.bank_iban || "--"}</p>
      </div>
    </div>
  `;

  admDom.orderModal.showModal();
}

admDom.btnCloseModal.addEventListener("click", () => admDom.orderModal.close());
admDom.orderModal.addEventListener("click", (e) => {
  if (e.target === admDom.orderModal) admDom.orderModal.close();
});

// Load Analytics
async function loadAnalytics() {
  try {
    const res = await fetch("/api/admin/analytics");
    if (!res.ok) return;
    const data = await res.json();
    adminState.analytics = data.analytics;

    // Update KPIs
    admDom.kpiTotalOrders.textContent = data.analytics.total_orders;
    admDom.kpiTotalShirts.textContent = data.analytics.shirts_sold;
    admDom.kpiPendingOrders.textContent = data.analytics.pending_orders_count;
    admDom.kpiPendingRev.textContent = (data.analytics.pending_revenue || 0).toFixed(2) + " €";
    admDom.kpiVerifiedOrders.textContent = data.analytics.verified_orders_count;
    admDom.kpiVerifiedRev.textContent = (data.analytics.verified_revenue || 0).toFixed(2) + " €";

    // By size
    admDom.analyticsSizesList.innerHTML = (data.analytics.by_size || []).map(s => {
      const sz = s.size === "XXXL" ? "3XL" : (s.size === "XXL" ? "2XL" : s.size);
      return `
        <div class="stat-item">
          <span>Taglia <strong>${sz}</strong></span>
          <strong>${s.qty} pz</strong>
        </div>
      `;
    }).join("") || `<p style="color: #728ea0; font-size: 13px;">Nessuna vendita registrata.</p>`;

    // By color
    admDom.analyticsColorsList.innerHTML = (data.analytics.by_color || []).map(c => `
      <div class="stat-item">
        <span>Colore <strong>${c.color_name}</strong></span>
        <strong>${c.qty} pz</strong>
      </div>
    `).join("") || `<p style="color: #728ea0; font-size: 13px;">Nessuna vendita registrata.</p>`;

  } catch (err) {
    console.error("Errore statistiche:", err);
  }
}

// Load Config
async function loadConfig() {
  try {
    const res = await fetch("/api/admin/config");
    if (!res.ok) return;
    const data = await res.json();
    adminState.config = data.config || {};

    admDom.cfgShirtPrice.value = adminState.config.shirt_price || "";
    admDom.cfgShippingLocker.value = adminState.config.shipping_locker || "";
    admDom.cfgShippingHome.value = adminState.config.shipping_home || "";
    admDom.cfgShippingHand.value = adminState.config.shipping_hand !== undefined ? adminState.config.shipping_hand : "0.00";

    admDom.cfgBankHolder.value = adminState.config.bank_holder || "";
    admDom.cfgBankIban.value = adminState.config.bank_iban || "";
    admDom.cfgBankName.value = adminState.config.bank_name || "";
    if (adminState.config.bank_notes) {
      admDom.cfgBankNotes.value = adminState.config.bank_notes;
    }
  } catch (err) {
    console.error("Errore configurazione:", err);
  }
}

// Save Pricing Config
admDom.configForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    shirt_price: admDom.cfgShirtPrice.value.trim(),
    shipping_locker: admDom.cfgShippingLocker.value.trim(),
    shipping_home: admDom.cfgShippingHome.value.trim(),
    shipping_hand: admDom.cfgShippingHand.value.trim()
  };

  try {
    const res = await fetch("/api/admin/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      showAdmToast("Prezzi e tariffe salvati!");
    } else {
      showAdmToast(data.message || "Errore durante il salvataggio.");
    }
  } catch (err) {
    showAdmToast("Errore di connessione.");
  }
});

// Save Bank Config
admDom.bankForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    bank_holder: admDom.cfgBankHolder.value.trim(),
    bank_iban: admDom.cfgBankIban.value.trim().replace(/\s/g, "").toUpperCase(),
    bank_name: admDom.cfgBankName.value.trim(),
    bank_notes: admDom.cfgBankNotes.value.trim()
  };

  try {
    const res = await fetch("/api/admin/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      showAdmToast("Coordinate bancarie salvate!");
    } else {
      showAdmToast(data.message || "Errore durante il salvataggio.");
    }
  } catch (err) {
    showAdmToast("Errore di connessione.");
  }
});

// Load Variants & Stock Matrix
async function loadVariants() {
  try {
    const res = await fetch("/api/admin/variants");
    if (!res.ok) return;
    const data = await res.json();
    adminState.variants = data.variants || [];
    renderVariantsMatrix();
  } catch (err) {
    console.error("Errore varianti:", err);
  }
}

function renderVariantsMatrix() {
  const allowedOrder = ["S", "M", "L", "XL", "XXL", "XXXL"];
  const navyVariants = adminState.variants.filter(v => v.color === "navy");
  const whiteVariants = adminState.variants.filter(v => v.color === "white");

  navyVariants.sort((a, b) => allowedOrder.indexOf(a.size) - allowedOrder.indexOf(b.size));
  whiteVariants.sort((a, b) => allowedOrder.indexOf(a.size) - allowedOrder.indexOf(b.size));

  function buildColorGroup(title, list) {
    return `
      <div style="background: #ffffff; border: 1px solid var(--adm-border); border-radius: var(--adm-radius); margin-bottom: 20px;">
        <div style="padding: 14px 18px; border-bottom: 1px solid var(--adm-border); background: #f8fafc; font-weight: 700; color: #142f48;">
          ${title}
        </div>
        ${list.map(v => {
          const szLabel = v.size === "XXXL" ? "3XL" : (v.size === "XXL" ? "2XL" : v.size);
          return `
            <div class="matrix-row">
              <div>
                <strong>Taglia ${szLabel}</strong>
                <small style="display: block; color: #567285;">${v.is_available ? 'In catalogo e selezionabile' : '<span style="color: #dc2626; font-weight: 600;">Esaurita nel modulo</span>'}</small>
              </div>
              <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 12px; font-weight: 600; color: ${v.is_available ? '#15803d' : '#94a3b8'};">
                  ${v.is_available ? 'Disponibile' : 'Esaurita'}
                </span>
                <label class="switch">
                  <input type="checkbox" class="var-toggle" data-variant-id="${v.id}" ${v.is_available ? 'checked' : ''}>
                  <span class="slider"></span>
                </label>
              </div>
            </div>
          `;
        }).join("")}
      </div>
    `;
  }

  admDom.variantsMatrixContainer.innerHTML = `
    ${buildColorGroup("T-shirt Blu navy", navyVariants)}
    ${buildColorGroup("T-shirt Bianca", whiteVariants)}
  `;

  // Attach toggle events
  document.querySelectorAll(".var-toggle").forEach(tg => {
    tg.addEventListener("change", async (e) => {
      const variantId = tg.getAttribute("data-variant-id");
      const isAvailable = tg.checked;
      try {
        const res = await fetch(`/api/admin/variants/${variantId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_available: isAvailable })
        });
        if (res.ok) {
          showAdmToast("Disponibilità aggiornata!");
          loadVariants();
        }
      } catch (err) {
        showAdmToast("Errore durante l'aggiornamento.");
        loadVariants();
      }
    });
  });
}

// Load Discounts
async function loadDiscounts() {
  try {
    const res = await fetch("/api/admin/discounts");
    if (!res.ok) return;
    const data = await res.json();
    adminState.discounts = data.discounts || [];
    renderDiscountsTable();
  } catch (err) {
    console.error("Errore codici sconto:", err);
  }
}

function renderDiscountsTable() {
  admDom.discountsTbody.innerHTML = adminState.discounts.map(d => `
    <tr>
      <td><strong style="font-family: monospace; font-size: 14px; color: #003760;">${d.code}</strong></td>
      <td>${d.discount_type === 'percentage' ? 'Percentuale' : 'Importo Fisso'}</td>
      <td><strong>${d.discount_type === 'percentage' ? d.discount_value + '%' : d.discount_value.toFixed(2) + ' €'}</strong></td>
      <td>${d.usage_count} ${d.max_uses ? '/ ' + d.max_uses : ''}</td>
      <td>
        <span class="status-badge ${d.is_active ? 'verified' : 'cancelled'}">
          ${d.is_active ? 'Attivo' : 'Disattivato'}
        </span>
      </td>
      <td>
        <button type="button" class="adm-btn adm-btn-secondary btn-toggle-discount" data-discount-id="${d.id}" data-active="${d.is_active}">
          ${d.is_active ? 'Disattiva' : 'Attiva'}
        </button>
      </td>
    </tr>
  `).join("");

  document.querySelectorAll(".btn-toggle-discount").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-discount-id");
      const currentActive = btn.getAttribute("data-active") === "1";
      try {
        const res = await fetch(`/api/admin/discounts/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: !currentActive })
        });
        if (res.ok) {
          showAdmToast("Codice sconto aggiornato.");
          loadDiscounts();
        }
      } catch (err) {
        showAdmToast("Errore di rete.");
      }
    });
  });
}

admDom.btnOpenNewDiscount.addEventListener("click", () => admDom.newDiscountModal.showModal());
admDom.btnCloseDiscountModal.addEventListener("click", () => admDom.newDiscountModal.close());
admDom.newDiscountModal.addEventListener("click", (e) => {
  if (e.target === admDom.newDiscountModal) admDom.newDiscountModal.close();
});

admDom.newDiscountForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const code = admDom.discCodeInput.value.trim().toUpperCase();
  const val = parseFloat(admDom.discValueInput.value);

  try {
    const res = await fetch("/api/admin/discounts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code, discount_value: val, discount_type: "fixed", is_active: true })
    });
    const data = await res.json();
    if (res.ok) {
      admDom.newDiscountModal.close();
      admDom.discCodeInput.value = "";
      admDom.discValueInput.value = "5.00";
      showAdmToast("Codice sconto creato con successo!");
      loadDiscounts();
    } else {
      showAdmToast("Errore: " + (data.message || "Impossibile creare codice."));
    }
  } catch (err) {
    showAdmToast("Errore di rete.");
  }
});

// Change Password
admDom.pwdForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const newPassword = admDom.newPasswordInput.value.trim();
  if (newPassword.length < 6) {
    showAdmToast("La password deve contenere almeno 6 caratteri.");
    return;
  }

  try {
    const res = await fetch("/api/admin/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_password: newPassword })
    });
    const data = await res.json();
    if (res.ok) {
      admDom.newPasswordInput.value = "";
      showAdmToast("Password aggiornata con successo!");
    } else {
      showAdmToast("Errore: " + (data.message || "Impossibile cambiare password."));
    }
  } catch (err) {
    showAdmToast("Errore di connessione.");
  }
});

// Boot
window.addEventListener("DOMContentLoaded", () => {
  checkAuth();
});
