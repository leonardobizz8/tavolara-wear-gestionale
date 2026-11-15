/**
 * TAVOLARA WEAR — GESTIONALE FINANZIARIO & DASHBOARD
 * Core Engine & Interactive UI (Apple Glass Design)
 */

// ---------------------------------------------------------------------------
// 1. STATE MANAGEMENT
// ---------------------------------------------------------------------------
const state = {
  token: localStorage.getItem("tavolara_admin_token") || "",
  authenticated: false,
  currentView: "overview",
  
  // Date filter
  period: "all",
  customStartDate: "",
  customEndDate: "",
  
  // Data caches
  overviewData: null,
  incomes: [],
  incomesSummary: {},
  incomeStatusFilter: "all",
  incomeSearchQuery: "",
  
  expenses: [],
  expensesSummary: {},
  expenseCategoryTab: "all",
  expenseSearchQuery: "",
  
  insightsData: null,
  insightsColorFilter: "all",
  insightsSizeFilter: "all",
  
  orders: [],
  ordersStatusFilter: "all",
  ordersSearchQuery: "",
  
  variants: [],
  config: {}
};

// Global chart references
const charts = {
  cashflow: null,
  balance: null,
  expensesCat: null,
  sales: null,
  expensesTrend: null,
  insightsColor: null,
  insightsSize: null
};

// ---------------------------------------------------------------------------
// CLAUDE EDITORIAL CHART.JS CONFIGURATION
// ---------------------------------------------------------------------------
if (window.Chart) {
  Chart.defaults.font.family = '"Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
  Chart.defaults.font.size = 11.5;
  Chart.defaults.color = '#716E68';
  Chart.defaults.borderColor = '#ECEAE4';
  
  if (Chart.defaults.plugins) {
    if (Chart.defaults.plugins.legend) {
      Chart.defaults.plugins.legend.labels.usePointStyle = true;
      Chart.defaults.plugins.legend.labels.boxWidth = 7;
      Chart.defaults.plugins.legend.labels.padding = 16;
      Chart.defaults.plugins.legend.labels.font = { size: 11.5, weight: '500' };
      Chart.defaults.plugins.legend.labels.color = '#716E68';
    }
    if (Chart.defaults.plugins.tooltip) {
      Chart.defaults.plugins.tooltip.backgroundColor = '#292825';
      Chart.defaults.plugins.tooltip.titleColor = '#FAF9F6';
      Chart.defaults.plugins.tooltip.bodyColor = '#E5E3DD';
      Chart.defaults.plugins.tooltip.titleFont = { size: 12, weight: '600' };
      Chart.defaults.plugins.tooltip.bodyFont = { size: 12, weight: '400' };
      Chart.defaults.plugins.tooltip.padding = 10;
      Chart.defaults.plugins.tooltip.cornerRadius = 6;
      Chart.defaults.plugins.tooltip.boxPadding = 5;
      Chart.defaults.plugins.tooltip.usePointStyle = true;
      Chart.defaults.plugins.tooltip.borderWidth = 1;
      Chart.defaults.plugins.tooltip.borderColor = 'rgba(255, 255, 255, 0.1)';
    }
  }
}

// ---------------------------------------------------------------------------
// 2. UTILITY & FORMATTING HELPERS
// ---------------------------------------------------------------------------
function formatEuro(amount) {
  if (amount === undefined || amount === null || isNaN(amount)) return "€ 0,00";
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(amount);
}

function formatDate(dateStr) {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("it-IT", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric"
    });
  } catch (e) {
    return dateStr;
  }
}

function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  
  const toast = document.createElement("div");
  toast.className = `apple-toast ${type}`;
  toast.innerHTML = `
    <span>${type === "success" ? "✓" : "⚠️"}</span>
    <span>${message}</span>
  `;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ---------------------------------------------------------------------------
// 3. API COMMUNICATION LAYER
// ---------------------------------------------------------------------------
async function apiRequest(path, method = "GET", data = null) {
  const headers = {
    "Content-Type": "application/json"
  };
  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }

  const options = {
    method,
    headers
  };
  if (data && (method === "POST" || method === "PUT" || method === "PATCH")) {
    options.body = JSON.stringify(data);
  }

  try {
    const res = await fetch(path, options);
    if (res.status === 401) {
      handleUnauthorized();
      throw new Error("Sessione scaduta o non autorizzata.");
    }
    const json = await res.json();
    if (!res.ok || json.error) {
      throw new Error(json.message || `Errore HTTP ${res.status}`);
    }
    return json;
  } catch (err) {
    console.error(`API Error on ${method} ${path}:`, err);
    throw err;
  }
}

function handleUnauthorized() {
  state.authenticated = false;
  state.token = "";
  localStorage.removeItem("tavolara_admin_token");
  document.getElementById("login-overlay").style.display = "flex";
  document.getElementById("admin-app").style.display = "none";
}

// ---------------------------------------------------------------------------
// 4. AUTHENTICATION (PERMANENT APP SESSION)
// ---------------------------------------------------------------------------
async function checkAuth() {
  const savedToken = localStorage.getItem("tavolara_admin_token");
  if (!savedToken) {
    handleUnauthorized();
    return;
  }

  // Instant Native Unlock: render app immediately from local persistent token
  state.token = savedToken;
  state.authenticated = true;
  document.getElementById("login-overlay").style.display = "none";
  document.getElementById("admin-app").style.display = "flex";
  loadInitialData();

  // Background verification (silent, never logs out on network glitch or offline)
  try {
    const res = await apiRequest("/api/admin/me");
    if (res && res.authenticated === false) {
      handleUnauthorized();
    }
  } catch (err) {
    console.info("[Auth] Persistent session active on device.");
  }
}

async function login(password) {
  const errBox = document.getElementById("login-error");
  errBox.style.display = "none";
  try {
    // 1. Supabase Auth
    if (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured()) {
      try {
        await window.TavolaraSupabase.adminLogin(password);
      } catch (sbErr) {
        console.warn("[Admin] Supabase login aviso:", sbErr.message);
      }
    }

    const res = await apiRequest("/api/admin/login", "POST", { password });
    if (res.authenticated && res.token) {
      state.token = res.token;
      state.authenticated = true;
      localStorage.setItem("tavolara_admin_token", res.token);
      document.getElementById("login-overlay").style.display = "none";
      document.getElementById("admin-app").style.display = "flex";
      showToast("Accesso eseguito con successo");
      loadInitialData();
    }
  } catch (err) {
    errBox.textContent = err.message || "Password non corretta.";
    errBox.style.display = "block";
  }
}

async function logout() {
  if (window.TavolaraSupabase) {
    await window.TavolaraSupabase.adminLogout();
  }
  try {
    await apiRequest("/api/admin/logout", "POST");
  } catch (e) {}
  handleUnauthorized();
  showToast("Disconnessione effettuata");
}

// ---------------------------------------------------------------------------
// 5. VIEW & TAB NAVIGATION & MOBILE DRAWER
// ---------------------------------------------------------------------------
function openMobileSidebar() {
  const sb = document.getElementById("sidebar");
  const bd = document.getElementById("sidebar-backdrop");
  if (sb) sb.classList.add("open");
  if (bd) {
    bd.style.display = "block";
    requestAnimationFrame(() => bd.classList.add("active"));
  }
}

function closeMobileSidebar() {
  const sb = document.getElementById("sidebar");
  const bd = document.getElementById("sidebar-backdrop");
  if (sb) sb.classList.remove("open");
  if (bd) {
    bd.classList.remove("active");
    setTimeout(() => {
      if (!bd.classList.contains("active")) {
        bd.style.display = "none";
      }
    }, 250);
  }
}

function toggleMobileSidebar() {
  const sb = document.getElementById("sidebar");
  if (sb?.classList.contains("open")) {
    closeMobileSidebar();
  } else {
    openMobileSidebar();
  }
}

function switchView(viewName) {
  state.currentView = viewName;

  // Update sidebar links
  document.querySelectorAll(".sidebar-link").forEach(link => {
    if (link.dataset.view === viewName) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });

  // Update mobile bottom nav buttons
  document.querySelectorAll(".mobile-nav-btn[data-view]").forEach(btn => {
    if (btn.dataset.view === viewName) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  // Auto-close mobile drawer
  closeMobileSidebar();

  // Update view sections
  document.querySelectorAll(".view-section").forEach(sec => {
    sec.classList.remove("active");
  });
  const activeSec = document.getElementById(`view-${viewName}`);
  if (activeSec) activeSec.classList.add("active");

  // Update top header titles
  const titles = {
    overview: { title: "Overview Finanziaria", sub: "Quadro economico consolidato e KPI Tavolara Wear" },
    attivo: { title: "Attivo (Entrate)", sub: "Monitoraggio incassi, conferme ed entrate commerciali" },
    passivo: { title: "Passivo (Uscite & Spese)", sub: "Gestione analitica di trasporto, imballaggio, prove e magliette" },
    insights: { title: "Insights & Analytics", sub: "Spaccato vendite per colore, taglie, matrice e redditività" },
    orders: { title: "Ordini Clienti", sub: "Riepilogo e sincronizzazione ordini raccolti online" },
    config: { title: "Impostazioni & Magazzino", sub: "Prezzi, disponibilità taglie e coordinate bancarie" }
  };
  const t = titles[viewName] || titles.overview;
  document.getElementById("page-title").textContent = t.title;
  document.getElementById("page-subtitle").textContent = t.sub;

  // Refresh data for the newly selected view
  refreshCurrentView();
}

function refreshCurrentView() {
  switch (state.currentView) {
    case "overview":
      loadOverview();
      break;
    case "attivo":
      loadIncomes();
      break;
    case "passivo":
      loadExpenses();
      break;
    case "insights":
      loadInsights();
      break;
    case "orders":
      loadOrders();
      break;
    case "config":
      loadConfig();
      break;
  }
}

function setTimePeriod(period, customStart = null, customEnd = null) {
  state.period = period;
  state.customStartDate = customStart || "";
  state.customEndDate = customEnd || "";

  document.querySelectorAll("#time-filter-control .segment-item").forEach(btn => {
    if (btn.dataset.period === period) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  const customBox = document.getElementById("custom-date-box");
  if (period === "custom") {
    customBox.classList.add("visible");
  } else {
    customBox.classList.remove("visible");
    refreshCurrentView();
  }
}

// ---------------------------------------------------------------------------
// 6. OVERVIEW SECTION (DASHBOARD PRINCIPALE)
// ---------------------------------------------------------------------------
async function loadOverview() {
  try {
    let res = null;
    if (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured()) {
      try {
        res = await window.TavolaraSupabase.getOverviewData(state.period, state.customStartDate, state.customEndDate);
      } catch (sbErr) {
        console.warn("[Admin] Supabase getOverviewData error, fallback:", sbErr);
      }
    }

    if (!res) {
      let url = `/api/admin/financial/overview?period=${state.period}`;
      if (state.period === "custom" && state.customStartDate && state.customEndDate) {
        url += `&start_date=${state.customStartDate}&end_date=${state.customEndDate}`;
      }
      res = await apiRequest(url);
    }
    state.overviewData = res;

    // Render Hero KPIs
    const k = res?.kpis || {};
    const totalIncomes = k.total_incomes ?? 0;
    const totalExpenses = k.total_expenses ?? 0;
    const currentBal = k.current_balance ?? (totalIncomes - totalExpenses);
    const grossProfit = k.gross_profit ?? currentBal;
    const grossMargin = k.gross_profit_margin ?? (totalIncomes > 0 ? (grossProfit / totalIncomes) * 100 : 0);

    const elTotalIncomes = document.getElementById("ov-total-incomes");
    if (elTotalIncomes) elTotalIncomes.textContent = formatEuro(totalIncomes);

    const elTotalExpenses = document.getElementById("ov-total-expenses");
    if (elTotalExpenses) elTotalExpenses.textContent = formatEuro(totalExpenses);
    
    const balEl = document.getElementById("ov-current-balance");
    if (balEl) {
      balEl.textContent = formatEuro(currentBal);
      balEl.className = "kpi-value " + (currentBal >= 0 ? "emerald-val" : "rose-val");
    }

    const elGrossProfit = document.getElementById("ov-gross-profit");
    if (elGrossProfit) elGrossProfit.textContent = formatEuro(grossProfit);

    const elGrossMargin = document.getElementById("ov-gross-margin");
    if (elGrossMargin) elGrossMargin.textContent = `Margine: ${Number(grossMargin).toFixed(1)}%`;

    const incCollected = k.incomes_breakdown?.collected ?? 0;
    const expCount = k.expenses_breakdown?.count ?? 0;
    const incCount = k.incomes_breakdown?.count ?? 0;

    const elIncomesSub = document.getElementById("ov-incomes-sub");
    if (elIncomesSub) elIncomesSub.textContent = `Incassate: ${formatEuro(incCollected)}`;

    const elExpensesSub = document.getElementById("ov-expenses-sub");
    if (elExpensesSub) elExpensesSub.textContent = `4 categorie | ${expCount} registrazioni`;

    // Secondary KPIs (supports both schema conventions)
    const shirtsSold = k.total_shirts_sold ?? k.shirts_sold ?? 0;
    const ordersCount = k.total_orders_count ?? k.orders_count ?? 0;
    const avgShirtCost = k.avg_shirt_cost ?? k.average_shirt_cost ?? 0;
    const avgOrderRev = k.avg_order_revenue ?? k.average_order_revenue ?? 0;

    const elShirtsSold = document.getElementById("ov-shirts-sold");
    if (elShirtsSold) elShirtsSold.textContent = shirtsSold;

    const elOrdersCount = document.getElementById("ov-orders-count");
    if (elOrdersCount) elOrdersCount.textContent = ordersCount;

    const elAvgShirtCost = document.getElementById("ov-avg-shirt-cost");
    if (elAvgShirtCost) elAvgShirtCost.textContent = formatEuro(avgShirtCost);

    const elAvgOrderRev = document.getElementById("ov-avg-order-rev");
    if (elAvgOrderRev) elAvgOrderRev.textContent = formatEuro(avgOrderRev);

    // Update sidebar badges
    const sideBadgeIncomes = document.getElementById("side-badge-incomes");
    if (sideBadgeIncomes) sideBadgeIncomes.textContent = incCount;

    const sideBadgeExpenses = document.getElementById("side-badge-expenses");
    if (sideBadgeExpenses) sideBadgeExpenses.textContent = expCount;

    const sideBadgeOrders = document.getElementById("side-badge-orders");
    if (sideBadgeOrders) sideBadgeOrders.textContent = ordersCount;

    // Render Charts safely
    renderOverviewCharts(res?.charts || {});
  } catch (err) {
    showToast("Errore caricamento Overview: " + err.message, "error");
  }
}

function renderOverviewCharts(chartsData) {
  if (!window.Chart) return;
  if (!chartsData) chartsData = {};

  const cashflowTimeline = Array.isArray(chartsData.cashflow_timeline) ? chartsData.cashflow_timeline : [];
  const balanceTimeline = Array.isArray(chartsData.balance_timeline) ? chartsData.balance_timeline : [];
  const catData = chartsData.expenses_by_category || { labels: ["Trasporto", "Imballaggio", "Prove", "Magliette"], values: [0, 0, 0, 0] };
  const salesTimeline = Array.isArray(chartsData.sales_timeline) ? chartsData.sales_timeline : [];

  // Chart 1: Cashflow Timeline (Incomes vs Expenses)
  const ctxCashflow = document.getElementById("chart-cashflow")?.getContext("2d");
  if (ctxCashflow) {
    if (charts.cashflow) charts.cashflow.destroy();

    const labels = cashflowTimeline.map(d => formatDate(d.date));
    const incomesData = cashflowTimeline.map(d => d.incomes);
    const expensesData = cashflowTimeline.map(d => d.expenses);

    charts.cashflow = new Chart(ctxCashflow, {
      type: "bar",
      data: {
        labels: labels.length ? labels : ["Nessun dato"],
        datasets: [
          {
            label: "Entrate (€)",
            data: incomesData.length ? incomesData : [0],
            backgroundColor: "#2B6E4F",
            borderRadius: 4,
            maxBarThickness: 28
          },
          {
            label: "Uscite (€)",
            data: expensesData.length ? expensesData : [0],
            backgroundColor: "#BA4A38",
            borderRadius: 4,
            maxBarThickness: 28
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "top", labels: { boxWidth: 8, font: { size: 11.5 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${formatEuro(ctx.raw)}`
            }
          }
        },
        scales: {
          x: { grid: { display: false } },
          y: {
            grid: { color: "#ECEAE4" },
            ticks: { callback: v => "€ " + v }
          }
        }
      }
    });
  }

  // Chart 2: Net Balance Timeline
  const ctxBalance = document.getElementById("chart-balance")?.getContext("2d");
  if (ctxBalance) {
    if (charts.balance) charts.balance.destroy();

    const labels = balanceTimeline.map(d => formatDate(d.date));
    const balanceData = balanceTimeline.map(d => d.balance);

    const grad = ctxBalance.createLinearGradient(0, 0, 0, 240);
    grad.addColorStop(0, "rgba(196, 119, 91, 0.18)");
    grad.addColorStop(1, "rgba(196, 119, 91, 0.0)");

    charts.balance = new Chart(ctxBalance, {
      type: "line",
      data: {
        labels: labels.length ? labels : ["Nessun dato"],
        datasets: [{
          label: "Saldo Netto (€)",
          data: balanceData.length ? balanceData : [0],
          borderColor: "#C4775B",
          backgroundColor: grad,
          borderWidth: 2,
          tension: 0.35,
          fill: true,
          pointRadius: 3.5,
          pointHoverRadius: 5.5,
          pointBackgroundColor: "#C4775B"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => `Saldo: ${formatEuro(ctx.raw)}`
            }
          }
        },
        scales: {
          x: { grid: { display: false } },
          y: {
            grid: { color: "#ECEAE4" },
            ticks: { callback: v => "€ " + v }
          }
        }
      }
    });
  }

  // Chart 3: Expenses by Category (Donut)
  const ctxCat = document.getElementById("chart-expenses-cat")?.getContext("2d");
  if (ctxCat) {
    if (charts.expensesCat) charts.expensesCat.destroy();

    const values = Array.isArray(catData.values) ? catData.values : [0, 0, 0, 0];
    const labels = Array.isArray(catData.labels) ? catData.labels : ["Trasporto", "Imballaggio", "Prove", "Magliette"];
    const hasValues = values.some(v => v > 0);
    const claudePalette = ["#3B7A9E", "#A76B29", "#6E4973", "#1F364D"];

    charts.expensesCat = new Chart(ctxCat, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{
          data: hasValues ? values : [1, 1, 1, 1],
          backgroundColor: hasValues ? claudePalette : ["#E5E3DD", "#E5E3DD", "#E5E3DD", "#E5E3DD"],
          borderWidth: 2,
          borderColor: "#FFFFFF"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "72%",
        plugins: {
          legend: { position: "right", labels: { boxWidth: 8, font: { size: 11.5 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                if (!hasValues) return "Nessuna spesa registrata";
                return `${ctx.label}: ${formatEuro(ctx.raw)}`;
              }
            }
          }
        }
      }
    });
  }

  // Chart 4: Sales Timeline
  const ctxSales = document.getElementById("chart-sales")?.getContext("2d");
  if (ctxSales) {
    if (charts.sales) charts.sales.destroy();

    const labels = salesTimeline.map(d => formatDate(d.date));
    const shirtsData = salesTimeline.map(d => d.shirts);
    const revData = salesTimeline.map(d => d.revenue);

    charts.sales = new Chart(ctxSales, {
      type: "line",
      data: {
        labels: labels.length ? labels : ["Nessun dato"],
        datasets: [
          {
            type: "bar",
            label: "Magliette Vendute",
            data: shirtsData.length ? shirtsData : [0],
            backgroundColor: "#1F364D",
            borderRadius: 4,
            maxBarThickness: 24,
            yAxisID: "y"
          },
          {
            type: "line",
            label: "Fatturato (€)",
            data: revData.length ? revData : [0],
            borderColor: "#C4775B",
            borderWidth: 2,
            tension: 0.3,
            fill: false,
            pointBackgroundColor: "#C4775B",
            yAxisID: "y1"
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "top", labels: { boxWidth: 8 } }
        },
        scales: {
          x: { grid: { display: false } },
          y: {
            type: "linear",
            display: true,
            position: "left",
            grid: { display: false },
            ticks: { precision: 0 }
          },
          y1: {
            type: "linear",
            display: true,
            position: "right",
            grid: { color: "#ECEAE4" },
            ticks: { callback: v => "€ " + v }
          }
        }
      }
    });
  }
}

// ---------------------------------------------------------------------------
// 7. ATTIVO (ENTRATE) SECTION
// ---------------------------------------------------------------------------
async function loadIncomes() {
  try {
    let res = null;
    if (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured()) {
      try {
        let sDate = null;
        let eDate = null;
        if (state.period === "custom") {
          sDate = state.customStartDate;
          eDate = state.customEndDate;
        }
        res = await window.TavolaraSupabase.getIncomes({
          status: state.incomeStatusFilter,
          search: state.incomeSearchQuery,
          startDate: sDate,
          endDate: eDate
        });
      } catch (sbErr) {
        console.warn("[Admin] Supabase getIncomes error, fallback:", sbErr);
      }
    }

    if (!res) {
      let url = `/api/admin/incomes?period=${state.period}&status=${state.incomeStatusFilter}&search=${encodeURIComponent(state.incomeSearchQuery)}`;
      if (state.period === "custom" && state.customStartDate && state.customEndDate) {
        url += `&start_date=${state.customStartDate}&end_date=${state.customEndDate}`;
      }
      res = await apiRequest(url);
    }
    state.incomes = res.incomes;
    state.incomesSummary = res.summary;

    // Render Summary Cards
    document.getElementById("inc-sum-total").textContent = formatEuro(res.summary.total);
    document.getElementById("inc-sum-count").textContent = `${res.count} movimenti registrati`;
    document.getElementById("inc-sum-collected").textContent = formatEuro(res.summary.collected);
    document.getElementById("inc-sum-pending").textContent = formatEuro(res.summary.pending);
    document.getElementById("inc-sum-confirmed").textContent = formatEuro(res.summary.confirmed);

    // Render Table
    renderIncomesTable(res.incomes);
  } catch (err) {
    showToast("Errore caricamento entrate: " + err.message, "error");
  }
}

function renderIncomesTable(incomes) {
  const tbody = document.getElementById("incomes-table-body");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (incomes.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8">
          <div class="empty-table-state">
            <div class="empty-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
            </div>
            <strong>Nessuna entrata trovata</strong>
            <p style="font-size: 13px; max-width: 320px;">Registra manualmente una nuova entrata con il pulsante in alto o sincronizza gli ordini confermati.</p>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  incomes.forEach(inc => {
    const tr = document.createElement("tr");

    // Status pill class
    let pillClass = "confermata";
    if (inc.status === "Incassata") pillClass = "incassata";
    else if (inc.status === "In attesa") pillClass = "in-attesa";

    tr.innerHTML = `
      <td>${formatDate(inc.date)}</td>
      <td class="fw-bold">${escapeHtml(inc.description)}</td>
      <td>${inc.order_reference ? `<span class="kpi-badge" style="background: rgba(2, 132, 199, 0.1); color: #0284c7;">${escapeHtml(inc.order_reference)}</span>` : "—"}</td>
      <td><span style="font-size: 12.5px;">${escapeHtml(inc.payment_method)}</span></td>
      <td><span class="status-pill ${pillClass}">${escapeHtml(inc.status)}</span></td>
      <td style="text-align: right;" class="fw-bold" style="color: var(--emerald);">${formatEuro(inc.amount)}</td>
      <td style="font-size: 12px; color: var(--text-muted); max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(inc.notes || '')}">
        ${escapeHtml(inc.notes || "—")}
      </td>
      <td style="text-align: center;">
        <button type="button" class="table-btn-icon btn-edit-income" data-id="${inc.id}" title="Modifica">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        </button>
        <button type="button" class="table-btn-icon delete btn-delete-income" data-id="${inc.id}" title="Elimina">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach table events
  tbody.querySelectorAll(".btn-edit-income").forEach(btn => {
    btn.addEventListener("click", () => openIncomeModal(parseInt(btn.dataset.id)));
  });
  tbody.querySelectorAll(".btn-delete-income").forEach(btn => {
    btn.addEventListener("click", () => deleteIncome(parseInt(btn.dataset.id)));
  });
}

function openIncomeModal(incomeId = null) {
  const modal = document.getElementById("modal-income");
  const form = document.getElementById("form-income");
  form.reset();

  const titleEl = document.getElementById("modal-income-title");
  const idInput = document.getElementById("income-id");

  if (incomeId) {
    titleEl.textContent = `Modifica Entrata #${incomeId}`;
    const inc = state.incomes.find(i => i.id === incomeId);
    if (inc) {
      idInput.value = inc.id;
      document.getElementById("inc-desc").value = inc.description;
      document.getElementById("inc-amount").value = inc.amount;
      document.getElementById("inc-date").value = inc.date;
      document.getElementById("inc-method").value = inc.payment_method;
      document.getElementById("inc-status").value = inc.status;
      document.getElementById("inc-ref").value = inc.order_reference || "";
      document.getElementById("inc-notes").value = inc.notes || "";
    }
  } else {
    titleEl.textContent = "Nuova Entrata Economica";
    idInput.value = "";
    document.getElementById("inc-date").value = new Date().toISOString().substring(0, 10);
    document.getElementById("inc-status").value = "Incassata";
  }

  modal.classList.add("active");
}

async function saveIncome(e) {
  e.preventDefault();
  const idInput = document.getElementById("income-id").value;
  const isEdit = !!idInput;

  const payload = {
    description: document.getElementById("inc-desc").value.trim(),
    amount: parseFloat(document.getElementById("inc-amount").value),
    date: document.getElementById("inc-date").value,
    payment_method: document.getElementById("inc-method").value,
    status: document.getElementById("inc-status").value,
    order_reference: document.getElementById("inc-ref").value.trim(),
    notes: document.getElementById("inc-notes").value.trim()
  };

  try {
    if (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured()) {
      try {
        if (isEdit) {
          await window.TavolaraSupabase.updateIncome(idInput, payload);
        } else {
          await window.TavolaraSupabase.createIncome(payload);
        }
      } catch (sbErr) {
        console.warn("[Admin] Supabase saveIncome error, fallback:", sbErr);
      }
    }

    if (isEdit) {
      await apiRequest(`/api/admin/incomes/${idInput}`, "PUT", payload);
      showToast(`Entrata #${idInput} aggiornata con successo`);
    } else {
      await apiRequest("/api/admin/incomes", "POST", payload);
      showToast("Nuova entrata registrata con successo");
    }
    document.getElementById("modal-income").classList.remove("active");
    loadIncomes();
    loadOverview(); // update global KPI
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function deleteIncome(id) {
  if (!confirm(`Sei sicuro di voler eliminare l'entrata #${id}?`)) return;
  try {
    if (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured()) {
      try {
        await window.TavolaraSupabase.deleteIncome(id);
      } catch (sbErr) {
        console.warn("[Admin] Supabase deleteIncome error, fallback:", sbErr);
      }
    }
    await apiRequest(`/api/admin/incomes/${id}`, "DELETE");
    showToast(`Entrata #${id} eliminata`);
    loadIncomes();
    loadOverview();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function openSyncOrdersModal() {
  const modal = document.getElementById("modal-sync-orders");
  const tbody = document.getElementById("sync-orders-tbody");
  tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px;">Caricamento ordini in corso...</td></tr>`;
  modal.classList.add("active");

  try {
    const res = await apiRequest("/api/admin/orders");
    const orders = res.orders || [];

    // Filter orders that have verified payments or shipped
    const syncable = orders.filter(o => o.status !== "Annullato");

    if (syncable.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--text-muted);">Nessun ordine pronto per la sincronizzazione.</td></tr>`;
      return;
    }

    tbody.innerHTML = "";
    syncable.forEach(ord => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="fw-bold">#${escapeHtml(ord.order_number)}</td>
        <td>${escapeHtml(ord.customer_first_name)} ${escapeHtml(ord.customer_last_name)}</td>
        <td class="fw-bold">${formatEuro(ord.total_amount)}</td>
        <td><span class="status-pill confermata">${escapeHtml(ord.status)}</span></td>
        <td style="text-align: right;">
          <button type="button" class="apple-btn apple-btn-emerald apple-btn-sm btn-sync-single" data-order-id="${ord.id}">
            + Sincronizza
          </button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    tbody.querySelectorAll(".btn-sync-single").forEach(btn => {
      btn.addEventListener("click", async () => {
        const orderId = btn.dataset.orderId;
        try {
          btn.disabled = true;
          btn.textContent = "Sincronizzo...";
          await apiRequest(`/api/admin/incomes/sync-order/${orderId}`, "POST");
          showToast(`Ordine #${orderId} sincronizzato nell'Attivo`);
          btn.textContent = "✓ Sincronizzato";
          loadIncomes();
          loadOverview();
        } catch (err) {
          showToast(err.message, "error");
          btn.disabled = false;
          btn.textContent = "+ Sincronizza";
        }
      });
    });

  } catch (err) {
    showToast("Errore caricamento ordini: " + err.message, "error");
  }
}

// ---------------------------------------------------------------------------
// 8. PASSIVO (USCITE & SPESE - 4 CATEGORIE)
// ---------------------------------------------------------------------------
async function loadExpenses() {
  try {
    let res = null;
    if (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured()) {
      try {
        let sDate = null;
        let eDate = null;
        if (state.period === "custom") {
          sDate = state.customStartDate;
          eDate = state.customEndDate;
        }
        res = await window.TavolaraSupabase.getExpenses({
          category: state.expenseCategoryTab,
          search: state.expenseSearchQuery,
          startDate: sDate,
          endDate: eDate
        });
      } catch (sbErr) {
        console.warn("[Admin] Supabase getExpenses error, fallback:", sbErr);
      }
    }

    if (!res) {
      let url = `/api/admin/expenses?category=${state.expenseCategoryTab}&period=${state.period}&search=${encodeURIComponent(state.expenseSearchQuery)}`;
      if (state.period === "custom" && state.customStartDate && state.customEndDate) {
        url += `&start_date=${state.customStartDate}&end_date=${state.customEndDate}`;
      }
      res = await apiRequest(url);
    }

    state.expenses = res.expenses;
    state.expensesSummary = res.summary;

    renderExpensesMetrics(res.summary);
    renderExpensesTable(res.expenses);
    renderExpensesTrendChart(res.expenses);
  } catch (err) {
    showToast("Errore caricamento uscite: " + err.message, "error");
  }
}

function renderExpensesMetrics(summary) {
  const cat = state.expenseCategoryTab;
  const grid = document.getElementById("expenses-metrics-grid");
  const totalVal = document.getElementById("exp-metric-total");
  const totalCount = document.getElementById("exp-metric-count");

  totalVal.textContent = formatEuro(summary.total_amount);
  totalCount.textContent = `${state.expenses.length} uscite registrate`;

  const kpi2Lbl = document.getElementById("exp-metric-kpi2-label");
  const kpi2Val = document.getElementById("exp-metric-kpi2-val");
  const kpi2Sub = document.getElementById("exp-metric-kpi2-sub");

  const kpi3Lbl = document.getElementById("exp-metric-kpi3-label");
  const kpi3Val = document.getElementById("exp-metric-kpi3-val");
  const kpi3Sub = document.getElementById("exp-metric-kpi3-sub");

  const kpi4Lbl = document.getElementById("exp-metric-kpi4-label");
  const kpi4Val = document.getElementById("exp-metric-kpi4-val");
  const kpi4Sub = document.getElementById("exp-metric-kpi4-sub");

  if (cat === "trasporto") {
    kpi2Lbl.textContent = "Spedizioni Totali";
    kpi2Val.textContent = summary.category_metrics.total_shipments;
    kpi2Sub.textContent = "Colli / spedizioni effettuate";

    const avgTrans = summary.category_metrics.total_shipments > 0 ? summary.by_category.trasporto / summary.category_metrics.total_shipments : 0;
    kpi3Lbl.textContent = "Costo Medio Spedizione";
    kpi3Val.textContent = formatEuro(avgTrans);
    kpi3Sub.textContent = "Per singola spedizione";

    kpi4Lbl.textContent = "Incidenza Categoria";
    kpi4Val.textContent = "100%";
    kpi4Sub.textContent = "Filtro attivo Trasporto";

  } else if (cat === "imballaggio") {
    kpi2Lbl.textContent = "Articoli Acquistati";
    kpi2Val.textContent = summary.category_metrics.total_packaging_items;
    kpi2Sub.textContent = "Scatole, buste ed etichette";

    const avgPack = summary.category_metrics.total_packaging_items > 0 ? summary.by_category.imballaggio / summary.category_metrics.total_packaging_items : 0;
    kpi3Lbl.textContent = "Costo Medio Articolo";
    kpi3Val.textContent = formatEuro(avgPack);
    kpi3Sub.textContent = "Per singolo pezzo";

    kpi4Lbl.textContent = "Incidenza Categoria";
    kpi4Val.textContent = "100%";
    kpi4Sub.textContent = "Filtro attivo Imballaggio";

  } else if (cat === "prove") {
    kpi2Lbl.textContent = "Prove Registrate";
    kpi2Val.textContent = state.expenses.length;
    kpi2Sub.textContent = "Campionature e test serigrafia";

    kpi3Lbl.textContent = "Totale Speso Prove";
    kpi3Val.textContent = formatEuro(summary.by_category.prove);
    kpi3Sub.textContent = "Sviluppo prototipale";

    kpi4Lbl.textContent = "Incidenza Categoria";
    kpi4Val.textContent = "100%";
    kpi4Sub.textContent = "Filtro attivo Prove";

  } else if (cat === "magliette") {
    kpi2Lbl.textContent = "Magliette Acquistate";
    kpi2Val.textContent = summary.category_metrics.total_shirts_purchased;
    kpi2Sub.textContent = "Capi complessivi in magazzino";

    kpi3Lbl.textContent = "Costo Unitario Medio";
    kpi3Val.textContent = formatEuro(summary.category_metrics.avg_unit_cost);
    kpi3Sub.textContent = "Costo medio acquisto t-shirt";

    kpi4Lbl.textContent = "Totale Fornitura Capi";
    kpi4Val.textContent = formatEuro(summary.by_category.magliette);
    kpi4Sub.textContent = "Inclusi costi extra lavorazione";

  } else {
    // All categories overview
    kpi2Lbl.textContent = "Spese di Trasporto";
    kpi2Val.textContent = formatEuro(summary.by_category.trasporto);
    kpi2Sub.textContent = `${summary.category_metrics.total_shipments} spedizioni registrate`;

    kpi3Lbl.textContent = "Spese di Imballaggio";
    kpi3Val.textContent = formatEuro(summary.by_category.imballaggio);
    kpi3Sub.textContent = `${summary.category_metrics.total_packaging_items} packaging acquistati`;

    kpi4Lbl.textContent = "Magliette & Prove";
    kpi4Val.textContent = formatEuro(summary.by_category.magliette + summary.by_category.prove);
    kpi4Sub.textContent = "Produzione, prototipi e stock";
  }
}

function renderExpensesTrendChart(expenses) {
  const ctx = document.getElementById("chart-expenses-trend")?.getContext("2d");
  if (!ctx || !window.Chart) return;
  if (charts.expensesTrend) charts.expensesTrend.destroy();

  // Group by date
  const dateMap = {};
  expenses.forEach(e => {
    dateMap[e.date] = (dateMap[e.date] || 0) + e.amount;
  });
  const sortedDates = Object.keys(dateMap).sort();

  const labels = sortedDates.map(d => formatDate(d));
  const values = sortedDates.map(d => dateMap[d]);

  const grad = ctx.createLinearGradient(0, 0, 0, 200);
  grad.addColorStop(0, "rgba(186, 74, 56, 0.16)");
  grad.addColorStop(1, "rgba(186, 74, 56, 0.0)");

  charts.expensesTrend = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels.length ? labels : ["Nessuna spesa nel periodo"],
      datasets: [{
        label: "Spesa (€)",
        data: values.length ? values : [0],
        borderColor: "#BA4A38",
        backgroundColor: grad,
        borderWidth: 2,
        tension: 0.35,
        fill: true,
        pointRadius: 3.5,
        pointBackgroundColor: "#BA4A38"
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => `Spesa: ${formatEuro(ctx.raw)}`
          }
        }
      },
      scales: {
        x: { grid: { display: false } },
        y: {
          grid: { color: "#ECEAE4" },
          ticks: { callback: v => "€ " + v }
        }
      }
    }
  });
}

function renderExpensesTable(expenses) {
  const tbody = document.getElementById("expenses-table-body");
  if (!tbody) return;
  tbody.innerHTML = "";

  document.getElementById("expenses-table-counter").textContent = `Mostrando ${expenses.length} uscite`;

  if (expenses.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7">
          <div class="empty-table-state">
            <div class="empty-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="17" y1="7" x2="7" y2="17"/><polyline points="17 17 7 17 7 7"/></svg>
            </div>
            <strong>Nessuna spesa trovata</strong>
            <p style="font-size: 13px; max-width: 320px;">Registra una nuova spesa per Trasporto, Imballaggio, Prove o Magliette.</p>
          </div>
        </td>
      </tr>
    `;
    return;
  }

  expenses.forEach(exp => {
    const tr = document.createElement("tr");

    // Build category specific details badge
    let detailsHtml = "";
    if (exp.category === "trasporto") {
      detailsHtml = `
        <span><strong>${escapeHtml(exp.carrier || "Corriere")}</strong></span>
        <span style="font-size: 11.5px; color: var(--text-muted);"> • ${exp.shipment_count || 1} sped. (${escapeHtml(exp.shipment_type || "singola")})</span>
      `;
    } else if (exp.category === "imballaggio") {
      detailsHtml = `
        <span><strong>${escapeHtml(exp.material_type || "Packaging")}</strong></span>
        ${exp.quantity ? `<span style="font-size: 11.5px; color: var(--text-muted);"> • Q.tà: ${exp.quantity}</span>` : ""}
        ${exp.unit_cost ? `<span style="font-size: 11.5px; color: var(--text-muted);"> (@ ${formatEuro(exp.unit_cost)})</span>` : ""}
      `;
    } else if (exp.category === "prove") {
      detailsHtml = `
        <span><strong>${escapeHtml(exp.proof_type || "Test prototipo")}</strong></span>
      `;
    } else if (exp.category === "magliette") {
      detailsHtml = `
        <span><strong>${escapeHtml(exp.supplier || "Fornitore")}</strong></span>
        ${exp.quantity ? `<span style="font-size: 11.5px; color: var(--text-muted);"> • ${exp.quantity} magliette</span>` : ""}
        ${exp.unit_cost ? `<span style="font-size: 11.5px; color: var(--text-muted);"> (@ ${formatEuro(exp.unit_cost)})</span>` : ""}
        ${exp.extra_production_costs ? `<span style="font-size: 11.5px; color: var(--brand-ice);"> [+${formatEuro(exp.extra_production_costs)} extra]</span>` : ""}
      `;
    }

    tr.innerHTML = `
      <td>${formatDate(exp.date)}</td>
      <td><span class="category-chip ${exp.category}">${escapeHtml(exp.category)}</span></td>
      <td class="fw-bold">${escapeHtml(exp.description)}</td>
      <td>${detailsHtml || "—"}</td>
      <td style="text-align: right;" class="fw-bold" style="color: var(--rose);">${formatEuro(exp.amount)}</td>
      <td style="font-size: 12px; color: var(--text-muted); max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(exp.notes || '')}">
        ${escapeHtml(exp.notes || "—")}
      </td>
      <td style="text-align: center;">
        <button type="button" class="table-btn-icon btn-edit-expense" data-id="${exp.id}" title="Modifica">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        </button>
        <button type="button" class="table-btn-icon delete btn-delete-expense" data-id="${exp.id}" title="Elimina">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll(".btn-edit-expense").forEach(btn => {
    btn.addEventListener("click", () => openExpenseModal(parseInt(btn.dataset.id)));
  });
  tbody.querySelectorAll(".btn-delete-expense").forEach(btn => {
    btn.addEventListener("click", () => deleteExpense(parseInt(btn.dataset.id)));
  });
}

function updateExpenseModalFields(category) {
  const categories = ["trasporto", "imballaggio", "prove", "magliette"];
  categories.forEach(cat => {
    const el = document.getElementById(`exp-fields-${cat}`);
    if (el) {
      el.style.display = (cat === category) ? "block" : "none";
    }
  });

  // Calculate amount dynamically
  calcExpenseModalAmount();
}

function calcExpenseModalAmount() {
  const cat = document.getElementById("exp-cat").value;
  const amountInput = document.getElementById("exp-amount");

  if (cat === "magliette") {
    const qty = parseInt(document.getElementById("exp-shirt-qty").value) || 0;
    const unit = parseFloat(document.getElementById("exp-shirt-unit").value) || 0;
    const extra = parseFloat(document.getElementById("exp-shirt-extra").value) || 0;
    if (qty > 0 && unit > 0) {
      amountInput.value = (qty * unit + extra).toFixed(2);
    }
  } else if (cat === "imballaggio") {
    const qty = parseInt(document.getElementById("exp-pack-qty").value) || 0;
    const unit = parseFloat(document.getElementById("exp-pack-unit").value) || 0;
    if (qty > 0 && unit > 0) {
      amountInput.value = (qty * unit).toFixed(2);
    }
  }
}

function openExpenseModal(expenseId = null, preselectedCat = null) {
  const modal = document.getElementById("modal-expense");
  const form = document.getElementById("form-expense");
  form.reset();

  const titleEl = document.getElementById("modal-expense-title");
  const idInput = document.getElementById("expense-id");
  const catSelect = document.getElementById("exp-cat");

  if (expenseId) {
    titleEl.textContent = `Modifica Spesa #${expenseId}`;
    const exp = state.expenses.find(e => e.id === expenseId);
    if (exp) {
      idInput.value = exp.id;
      catSelect.value = exp.category;
      document.getElementById("exp-desc").value = exp.description;
      document.getElementById("exp-amount").value = exp.amount;
      document.getElementById("exp-date").value = exp.date;
      document.getElementById("exp-notes").value = exp.notes || "";

      // Specific fields
      if (exp.category === "trasporto") {
        document.getElementById("exp-trans-carrier").value = exp.carrier || "";
        document.getElementById("exp-trans-count").value = exp.shipment_count || 1;
        document.getElementById("exp-trans-type").value = exp.shipment_type || "singola";
      } else if (exp.category === "imballaggio") {
        document.getElementById("exp-pack-material").value = exp.material_type || "Scatole";
        document.getElementById("exp-pack-qty").value = exp.quantity || "";
        document.getElementById("exp-pack-unit").value = exp.unit_cost || "";
      } else if (exp.category === "prove") {
        document.getElementById("exp-proof-type").value = exp.proof_type || "Campioni e prototipi";
      } else if (exp.category === "magliette") {
        document.getElementById("exp-shirt-supplier").value = exp.supplier || "";
        document.getElementById("exp-shirt-qty").value = exp.quantity || "";
        document.getElementById("exp-shirt-unit").value = exp.unit_cost || "";
        document.getElementById("exp-shirt-extra").value = exp.extra_production_costs || "0.00";
      }
    }
  } else {
    titleEl.textContent = "Registra Nuova Spesa";
    idInput.value = "";
    document.getElementById("exp-date").value = new Date().toISOString().substring(0, 10);
    
    // Auto-select category based on active tab or arg
    const chosenCat = preselectedCat || (state.expenseCategoryTab !== "all" ? state.expenseCategoryTab : "trasporto");
    catSelect.value = chosenCat;
  }

  updateExpenseModalFields(catSelect.value);
  modal.classList.add("active");
}

async function saveExpense(e) {
  e.preventDefault();
  const idInput = document.getElementById("expense-id").value;
  const isEdit = !!idInput;

  const cat = document.getElementById("exp-cat").value;
  const payload = {
    category: cat,
    description: document.getElementById("exp-desc").value.trim(),
    amount: parseFloat(document.getElementById("exp-amount").value),
    date: document.getElementById("exp-date").value,
    notes: document.getElementById("exp-notes").value.trim()
  };

  // Add category specific fields
  if (cat === "trasporto") {
    payload.carrier = document.getElementById("exp-trans-carrier").value.trim();
    payload.shipment_count = parseInt(document.getElementById("exp-trans-count").value) || 1;
    payload.shipment_type = document.getElementById("exp-trans-type").value;
  } else if (cat === "imballaggio") {
    payload.material_type = document.getElementById("exp-pack-material").value;
    payload.quantity = parseInt(document.getElementById("exp-pack-qty").value) || 0;
    payload.unit_cost = parseFloat(document.getElementById("exp-pack-unit").value) || 0;
  } else if (cat === "prove") {
    payload.proof_type = document.getElementById("exp-proof-type").value;
  } else if (cat === "magliette") {
    payload.supplier = document.getElementById("exp-shirt-supplier").value.trim();
    payload.quantity = parseInt(document.getElementById("exp-shirt-qty").value) || 0;
    payload.unit_cost = parseFloat(document.getElementById("exp-shirt-unit").value) || 0;
    payload.extra_production_costs = parseFloat(document.getElementById("exp-shirt-extra").value) || 0;
  }

  try {
    if (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured()) {
      try {
        if (isEdit) {
          await window.TavolaraSupabase.updateExpense(idInput, payload);
        } else {
          await window.TavolaraSupabase.createExpense(payload);
        }
      } catch (sbErr) {
        console.warn("[Admin] Supabase saveExpense error, fallback:", sbErr);
      }
    }

    if (isEdit) {
      await apiRequest(`/api/admin/expenses/${idInput}`, "PUT", payload);
      showToast(`Spesa #${idInput} aggiornata con successo`);
    } else {
      await apiRequest("/api/admin/expenses", "POST", payload);
      showToast("Nuova spesa registrata con successo");
    }
    document.getElementById("modal-expense").classList.remove("active");
    loadExpenses();
    loadOverview();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function deleteExpense(id) {
  if (!confirm(`Sei sicuro di voler eliminare la spesa #${id}?`)) return;
  try {
    if (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured()) {
      try {
        await window.TavolaraSupabase.deleteExpense(id);
      } catch (sbErr) {
        console.warn("[Admin] Supabase deleteExpense error, fallback:", sbErr);
      }
    }
    await apiRequest(`/api/admin/expenses/${id}`, "DELETE");
    showToast(`Spesa #${id} eliminata`);
    loadExpenses();
    loadOverview();
  } catch (err) {
    showToast(err.message, "error");
  }
}

// ---------------------------------------------------------------------------
// 9. INSIGHTS & ANALYTICS SECTION
// ---------------------------------------------------------------------------
async function loadInsights() {
  try {
    let url = `/api/admin/insights?period=${state.period}`;
    if (state.insightsColorFilter !== "all") {
      url += `&color=${state.insightsColorFilter}`;
    }
    if (state.insightsSizeFilter !== "all") {
      url += `&size=${state.insightsSizeFilter}`;
    }
    if (state.period === "custom" && state.customStartDate && state.customEndDate) {
      url += `&start_date=${state.customStartDate}&end_date=${state.customEndDate}`;
    }

    const res = await apiRequest(url);
    state.insightsData = res;

    // 1. Color Stats
    renderColorStats(res.color_stats);

    // 2. Size Stats & Matrix Table
    renderSizeStats(res.size_stats);

    // 3. Commercial Stats
    renderCommercialStats(res.commercial_stats);

    // 4. Economic Stats
    renderEconomicStats(res.economic_stats);

  } catch (err) {
    showToast("Errore caricamento Insights: " + err.message, "error");
  }
}

function renderColorStats(colorStats) {
  document.getElementById("ins-navy-count").textContent = `${colorStats.navy_sold} capi`;
  document.getElementById("ins-navy-pct").textContent = `${colorStats.navy_percentage.toFixed(1)}%`;
  document.getElementById("ins-navy-bar").style.width = `${colorStats.navy_percentage}%`;

  document.getElementById("ins-white-count").textContent = `${colorStats.white_sold} capi`;
  document.getElementById("ins-white-pct").textContent = `${colorStats.white_percentage.toFixed(1)}%`;
  document.getElementById("ins-white-bar").style.width = `${colorStats.white_percentage}%`;

  // Donut chart
  const ctx = document.getElementById("chart-insights-color")?.getContext("2d");
  if (ctx && window.Chart) {
    if (charts.insightsColor) charts.insightsColor.destroy();

    const hasData = colorStats.total_shirts > 0;
    charts.insightsColor = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: colorStats.chart.labels,
        datasets: [{
          data: hasData ? colorStats.chart.values : [1, 1],
          backgroundColor: hasData ? ["#1F364D", "#D8D5CD"] : ["#EFECE6", "#EFECE6"],
          borderWidth: 2,
          borderColor: "#FFFFFF"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "72%",
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 8, font: { size: 11.5 } } },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                if (!hasData) return "Nessuna vendita";
                return `${ctx.label}: ${ctx.raw} magliette`;
              }
            }
          }
        }
      }
    });
  }
}

function renderSizeStats(sizeStats) {
  // Best / Least Seller
  const bestEl = document.getElementById("ins-best-seller");
  const bestSub = document.getElementById("ins-best-seller-sub");
  if (sizeStats.best_seller) {
    bestEl.textContent = `Taglia ${sizeStats.best_seller.size}`;
    bestSub.textContent = `${sizeStats.best_seller.total} vendute (${sizeStats.best_seller.percentage.toFixed(1)}%)`;
  } else {
    bestEl.textContent = "—";
    bestSub.textContent = "Nessuna vendita";
  }

  const leastEl = document.getElementById("ins-least-seller");
  const leastSub = document.getElementById("ins-least-seller-sub");
  if (sizeStats.least_seller) {
    leastEl.textContent = `Taglia ${sizeStats.least_seller.size}`;
    leastSub.textContent = `${sizeStats.least_seller.total} vendute (${sizeStats.least_seller.percentage.toFixed(1)}%)`;
  } else {
    leastEl.textContent = "—";
    leastSub.textContent = "Nessuna vendita";
  }

  // Cross Matrix Table
  const tbody = document.getElementById("cross-matrix-tbody");
  if (tbody) {
    tbody.innerHTML = "";
    const matrix = sizeStats.cross_matrix;

    matrix.rows.forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="fw-bold" style="color: var(--text-main); font-size: 15px;">${r.size}</td>
        <td><span style="font-weight: 600; color: #1F364D;">${r.navy}</span></td>
        <td><span style="font-weight: 600; color: #716E68;">${r.white}</span></td>
        <td class="fw-bold" style="font-size: 14.5px;">${r.total}</td>
        <td>
          <div style="display: flex; align-items: center; justify-content: center; gap: 8px;">
            <div style="width: 70px; height: 6px; background: var(--border-main); border-radius: 3px; overflow: hidden;">
              <div style="width: ${r.percentage}%; height: 100%; background: #C4775B; border-radius: 3px;"></div>
            </div>
            <span style="font-size: 12px; font-weight: 600; color: var(--text-secondary);">${r.percentage.toFixed(1)}%</span>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });

    // Total Row
    const tot = matrix.total_row;
    const trTot = document.createElement("tr");
    trTot.className = "total-row";
    trTot.innerHTML = `
      <td>${tot.size}</td>
      <td style="color: #1F364D;">${tot.navy}</td>
      <td style="color: #716E68;">${tot.white}</td>
      <td style="font-size: 16px;">${tot.total}</td>
      <td>100.0%</td>
    `;
    tbody.appendChild(trTot);
  }

  // Size Bar Chart
  const ctx = document.getElementById("chart-insights-size")?.getContext("2d");
  if (ctx && window.Chart) {
    if (charts.insightsSize) charts.insightsSize.destroy();

    const labels = sizeStats.cross_matrix.rows.map(r => r.size);
    const navyData = sizeStats.cross_matrix.rows.map(r => r.navy);
    const whiteData = sizeStats.cross_matrix.rows.map(r => r.white);

    charts.insightsSize = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Blu navy",
            data: navyData,
            backgroundColor: "#1F364D",
            borderRadius: 3
          },
          {
            label: "Bianca",
            data: whiteData,
            backgroundColor: "#C5C1B8",
            borderRadius: 3
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "top", labels: { boxWidth: 8, font: { size: 11.5 } } }
        },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: {
            stacked: true,
            grid: { color: "#ECEAE4" },
            ticks: { precision: 0 }
          }
        }
      }
    });
  }
}

function renderCommercialStats(comm) {
  document.getElementById("ins-comm-orders").textContent = comm.total_orders;
  document.getElementById("ins-comm-customers").textContent = comm.unique_customers;
  document.getElementById("ins-comm-shirts").textContent = comm.total_shirts_sold;
  document.getElementById("ins-comm-avg-qty").textContent = comm.avg_qty_per_order.toFixed(2);
  document.getElementById("ins-comm-aov").textContent = formatEuro(comm.avg_order_value);
  document.getElementById("ins-comm-revenue").textContent = formatEuro(comm.total_revenue);
}

function renderEconomicStats(econ) {
  document.getElementById("ins-econ-prod-cost").textContent = formatEuro(econ.production_cost);
  document.getElementById("ins-econ-trans-cost").textContent = formatEuro(econ.transport_cost);
  document.getElementById("ins-econ-pack-cost").textContent = formatEuro(econ.packaging_cost);
  document.getElementById("ins-econ-proof-cost").textContent = formatEuro(econ.proof_cost);

  document.getElementById("ins-econ-avg-cost").textContent = formatEuro(econ.avg_shirt_cost);
  document.getElementById("ins-econ-avg-rev").textContent = formatEuro(econ.avg_shirt_revenue);

  document.getElementById("ins-econ-gross-margin").textContent = formatEuro(econ.gross_margin_amount);
  document.getElementById("ins-econ-gross-margin-pct").textContent = `${econ.gross_margin_percentage.toFixed(1)}% sul fatturato`;

  const netEl = document.getElementById("ins-econ-net-profit");
  netEl.textContent = formatEuro(econ.estimated_profit);
  netEl.className = "kpi-value " + (econ.estimated_profit >= 0 ? "emerald-val" : "rose-val");
  document.getElementById("ins-econ-net-profit-pct").textContent = `${econ.profit_margin_percentage.toFixed(1)}% netto finale`;
}

// ---------------------------------------------------------------------------
// 10. ORDERS VIEW (OPERATIVITÀ CLIENTI)
// ---------------------------------------------------------------------------
async function loadOrders() {
  try {
    let res = null;
    if (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured()) {
      try {
        res = await window.TavolaraSupabase.getOrders({
          status: state.ordersStatusFilter,
          search: state.ordersSearchQuery
        });
      } catch (sbErr) {
        console.warn("[Admin] Supabase getOrders error, fallback:", sbErr);
      }
    }

    if (!res) {
      let url = "/api/admin/orders";
      res = await apiRequest(url);
    }
    state.orders = res.orders || [];
    renderOrdersTable(state.orders);
  } catch (err) {
    showToast("Errore caricamento ordini: " + err.message, "error");
  }
}

function renderOrdersTable(orders) {
  const tbody = document.getElementById("orders-table-body");
  if (!tbody) return;
  tbody.innerHTML = "";

  // Filter by search & status
  const q = state.ordersSearchQuery.toLowerCase();
  const filtered = orders.filter(o => {
    if (state.ordersStatusFilter !== "all" && o.status !== state.ordersStatusFilter) return false;
    if (q) {
      const match = (o.order_number || "").toLowerCase().includes(q) ||
                    (o.customer_first_name || "").toLowerCase().includes(q) ||
                    (o.customer_last_name || "").toLowerCase().includes(q) ||
                    (o.customer_email || "").toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 30px; color: var(--text-muted);">Nessun ordine trovato.</td></tr>`;
    return;
  }

  filtered.forEach(o => {
    const tr = document.createElement("tr");

    // Product summary
    const itemsSummary = (o.items || []).map(i => `${i.quantity}x ${i.color_name || (i.color === 'white' ? 'Bianca' : 'Blu navy')} (${i.size})`).join(", ") || "T-shirt";

    tr.innerHTML = `
      <td class="fw-bold">#${escapeHtml(o.order_number)}</td>
      <td>${formatDate(o.created_at ? o.created_at.substring(0, 10) : "")}</td>
      <td>
        <div style="font-weight: 600;">${escapeHtml(o.customer_first_name)} ${escapeHtml(o.customer_last_name)}</div>
        <div style="font-size: 11.5px; color: var(--text-muted);">${escapeHtml(o.customer_email)}</div>
      </td>
      <td><span style="font-size: 12.5px;">${escapeHtml(itemsSummary)}</span></td>
      <td><span style="font-size: 12.5px; text-transform: capitalize;">${escapeHtml(o.delivery_method)}</span></td>
      <td style="text-align: right;" class="fw-bold">${formatEuro(o.total_amount)}</td>
      <td>
        <select class="apple-input order-status-select" data-id="${o.id}" style="padding: 4px 8px; font-size: 12px; width: auto;">
          ${[
            "Ordine ricevuto",
            "Ordine confermato",
            "Ordine da pagare",
            "Ordine pagato",
            "In preparazione",
            "Spedito / Consegnato",
            "Annullato"
          ].map(st => `<option value="${st}" ${o.status === st ? "selected" : ""}>${st}</option>`).join("")}
        </select>
      </td>
      <td style="text-align: center;">
        <button type="button" class="apple-btn apple-btn-secondary apple-btn-sm btn-quick-sync-order" data-id="${o.id}" title="Sincronizza nell'Attivo">
          ⚡ Sincronizza
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach status change events
  tbody.querySelectorAll(".order-status-select").forEach(sel => {
    sel.addEventListener("change", async (e) => {
      const orderId = sel.dataset.id;
      const newStatus = sel.value;
      try {
        if (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured()) {
          try {
            await window.TavolaraSupabase.updateOrderStatus(orderId, newStatus);
          } catch (sbErr) {
            console.warn("[Admin] Supabase updateOrderStatus fallback:", sbErr);
          }
        }
        await apiRequest(`/api/admin/orders/${orderId}/status`, "PATCH", { status: newStatus });
        showToast(`Stato ordine #${orderId} aggiornato a '${newStatus}'`);
        loadOverview();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  });

  // Attach quick sync
  tbody.querySelectorAll(".btn-quick-sync-order").forEach(btn => {
    btn.addEventListener("click", async () => {
      const orderId = btn.dataset.id;
      try {
        btn.disabled = true;
        if (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured()) {
          try {
            await window.TavolaraSupabase.syncOrderToIncome(orderId);
          } catch (sbErr) {
            console.warn("[Admin] Supabase syncOrderToIncome fallback:", sbErr);
          }
        }
        await apiRequest(`/api/admin/incomes/sync-order/${orderId}`, "POST");
        showToast(`Ordine #${orderId} sincronizzato nell'Attivo`);
        btn.textContent = "✓ Sincronizzato";
        loadOverview();
      } catch (err) {
        showToast(err.message, "error");
        btn.disabled = false;
      }
    });
  });
}

// ---------------------------------------------------------------------------
// 11. CONFIG & STOCK SECTION
// ---------------------------------------------------------------------------
async function loadConfig() {
  try {
    const cfgRes = await apiRequest("/api/admin/config");
    state.config = cfgRes.config || {};

    document.getElementById("cfg-shirt-price").value = state.config.shirt_price || "";
    document.getElementById("cfg-shipping-locker").value = state.config.shipping_locker || "";
    document.getElementById("cfg-shipping-home").value = state.config.shipping_home || "";
    document.getElementById("cfg-shipping-hand").value = state.config.shipping_hand || "0.00";

    document.getElementById("cfg-bank-holder").value = state.config.bank_holder || "";
    document.getElementById("cfg-bank-iban").value = state.config.bank_iban || "";
    document.getElementById("cfg-bank-name").value = state.config.bank_name || "";

    // Load variants
    const varRes = await apiRequest("/api/admin/variants");
    state.variants = varRes.variants || [];
    renderVariantsTable(state.variants);

  } catch (err) {
    showToast("Errore caricamento configurazione: " + err.message, "error");
  }
}

function renderVariantsTable(variants) {
  const tbody = document.getElementById("variants-table-body");
  if (!tbody) return;
  tbody.innerHTML = "";

  variants.forEach(v => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>
        <span class="category-chip ${v.color === 'navy' ? 'trasporto' : 'imballaggio'}">
          ${escapeHtml(v.color_name)}
        </span>
      </td>
      <td class="fw-bold">${escapeHtml(v.size)}</td>
      <td>
        <span class="status-pill ${v.is_available ? 'incassata' : 'in-attesa'}">
          ${v.is_available ? "Disponibile per ordini" : "Esaurita / Disattivata"}
        </span>
      </td>
      <td>
        <input type="number" class="apple-input variant-stock-input" data-id="${v.id}" value="${v.stock_qty || 50}" style="width: 80px; padding: 4px 8px; font-size: 13px;">
      </td>
      <td style="text-align: right;">
        <button type="button" class="apple-btn ${v.is_available ? 'apple-btn-secondary' : 'apple-btn-emerald'} apple-btn-sm btn-toggle-variant" data-id="${v.id}" data-avail="${v.is_available}">
          ${v.is_available ? "Disattiva" : "Attiva"}
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  tbody.querySelectorAll(".btn-toggle-variant").forEach(btn => {
    btn.addEventListener("click", async () => {
      const varId = btn.dataset.id;
      const currentAvail = btn.dataset.avail === "1";
      try {
        await apiRequest(`/api/admin/variants/${varId}`, "PATCH", { is_available: !currentAvail });
        showToast("Disponibilità taglia aggiornata");
        loadConfig();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  });

  tbody.querySelectorAll(".variant-stock-input").forEach(inp => {
    inp.addEventListener("change", async () => {
      const varId = inp.dataset.id;
      const newQty = parseInt(inp.value) || 0;
      try {
        await apiRequest(`/api/admin/variants/${varId}`, "PATCH", { stock_qty: newQty });
        showToast("Giacenza stock aggiornata");
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  });
}

// ---------------------------------------------------------------------------
// 12. INITIALIZATION & EVENT LISTENERS
// ---------------------------------------------------------------------------
async function loadExcelStatus() {
  try {
    const res = await apiRequest("/api/admin/excel/status");
    state.excelStatus = res;
    // Update sidebar card
    const sideFilename = document.getElementById("side-excel-filename");
    const sideStats = document.getElementById("side-excel-stats");
    const sideBadge = document.getElementById("side-excel-badge");
    if (sideFilename) sideFilename.textContent = res.file_name;
    if (sideStats) sideStats.textContent = `${res.orders_count} ordini · ${formatEuro(res.total_revenue)}`;
    if (sideBadge) {
      sideBadge.textContent = res.is_connected ? "Live" : "Offline";
      sideBadge.className = `status-pill ${res.is_connected ? "incassata" : "in-attesa"}`;
    }

    // Update top header button
    const headerLabel = document.getElementById("header-excel-label");
    const headerDot = document.getElementById("header-excel-dot");
    if (headerLabel) headerLabel.textContent = `Excel: ${res.orders_count} Ordini`;
    if (headerDot) headerDot.style.background = res.is_connected ? "#059669" : "#d97706";

    // Update modal
    const modOrders = document.getElementById("excel-modal-orders-pill");
    const modFile = document.getElementById("excel-modal-filepath");
    const modLast = document.getElementById("excel-modal-last-synced");
    const modRev = document.getElementById("excel-modal-rev");
    const modCosts = document.getElementById("excel-modal-costs");
    const modProfit = document.getElementById("excel-modal-profit");
    const modPala = document.getElementById("excel-modal-pala");
    const modBizz = document.getElementById("excel-modal-bizz");

    if (modOrders) modOrders.textContent = `${res.orders_count} Ordini`;
    if (modFile) modFile.innerHTML = `Percorso: <code>${escapeHtml(res.file_path || res.file_name)}</code>`;
    if (modLast) modLast.textContent = `Ultima sincronizzazione: ${formatDate(res.last_synced ? res.last_synced.substring(0, 10) : "")} ${res.last_synced ? res.last_synced.substring(11, 19) : ""}`;
    if (modRev) modRev.textContent = formatEuro(res.total_revenue);
    if (modCosts) modCosts.textContent = formatEuro(res.total_costs);
    if (modProfit) modProfit.textContent = formatEuro(res.total_profit);
    if (modPala) modPala.textContent = formatEuro(res.pala_profit);
    if (modBizz) modBizz.textContent = formatEuro(res.bizz_profit);

  } catch (err) {
    console.error("Error loading Excel status:", err);
  }
}

function openExcelSyncModal() {
  loadExcelStatus();
  document.getElementById("modal-excel-sync")?.classList.add("active");
}

async function triggerExcelSync() {
  const btn = document.getElementById("btn-trigger-excel-sync");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Sincronizzo...";
  }
  try {
    const res = await apiRequest("/api/admin/excel/sync", "POST");
    showToast(`✓ Sincronizzati ${res.orders_synced} ordini dal file Excel!`);
    loadExcelStatus();
    loadOverview();
    if (state.currentView !== "overview") refreshCurrentView();
  } catch (err) {
    showToast("Errore sincronizzazione Excel: " + err.message, "error");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Sincronizza Ora";
    }
  }
}

async function uploadExcelFile(file) {
  if (!file) return;
  if (!file.name.endsWith(".xlsx")) {
    showToast("Carica solo file in formato .xlsx", "error");
    return;
  }
  showToast(`Caricamento ${file.name} in corso...`);
  try {
    const buffer = await file.arrayBuffer();
    const res = await fetch("/api/admin/excel/upload", {
      method: "POST",
      headers: {
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Authorization": `Bearer ${state.token}`
      },
      body: buffer
    });
    const json = await res.json();
    if (json.success) {
      showToast(`✓ File ${file.name} caricato e sincronizzato! (${json.orders_synced} ordini)`);
      loadExcelStatus();
      loadOverview();
      refreshCurrentView();
    } else {
      showToast(json.message || "Errore durante il caricamento", "error");
    }
  } catch (err) {
    showToast("Errore upload file: " + err.message, "error");
  }
}

let _realtimeDebounceTimer = null;
function triggerRealtimeRefresh(message) {
  if (message) {
    showToast(message, "success");
  }
  if (_realtimeDebounceTimer) clearTimeout(_realtimeDebounceTimer);
  _realtimeDebounceTimer = setTimeout(() => {
    refreshCurrentView();
    loadExcelStatus();
  }, 300);
}

let _realtimeChannel = null;
function setupSupabaseRealtime() {
  if (!window.TavolaraSupabase || !window.TavolaraSupabase.isConfigured()) return;
  const client = window.TavolaraSupabase.client;
  if (!client || _realtimeChannel) return;

  try {
    _realtimeChannel = client.channel("tavolara_realtime_stream");

    // 1. Ascolto ordini (INSERT, UPDATE, DELETE)
    _realtimeChannel.on(
      "postgres_changes",
      { event: "*", schema: "public", table: "orders" },
      (payload) => {
        console.log("[Realtime Supabase] Ordine:", payload.eventType, payload.new || payload.old);
        const eventLabel = payload.eventType === "INSERT" ? "⚡ Nuovo ordine ricevuto dal modulo!" : "⚡ Ordine aggiornato!";
        triggerRealtimeRefresh(eventLabel);
      }
    );

    // 2. Ascolto transazioni / incassi effettivi (Attivo)
    _realtimeChannel.on(
      "postgres_changes",
      { event: "*", schema: "public", table: "transactions" },
      (payload) => {
        console.log("[Realtime Supabase] Movimento incasso:", payload.eventType);
        triggerRealtimeRefresh("⚡ Incasso registrato / aggiornato!");
      }
    );

    // 3. Ascolto spese (Passivo nelle 4 categorie)
    _realtimeChannel.on(
      "postgres_changes",
      { event: "*", schema: "public", table: "expenses" },
      (payload) => {
        console.log("[Realtime Supabase] Spesa registrata:", payload.eventType);
        triggerRealtimeRefresh("⚡ Spesa registrata / aggiornata!");
      }
    );

    _realtimeChannel.subscribe((status) => {
      console.log("[Realtime Supabase] Status connessione:", status);
      const statusText = document.getElementById("side-supabase-status");
      if (statusText && status === "SUBSCRIBED") {
        statusText.innerHTML = "Supabase DB · <span style='color:#10b981;font-weight:600;'>● Realtime attivo</span>";
      }
    });
  } catch (err) {
    console.warn("[Realtime Supabase] Errore inizializzazione:", err);
  }
}

let _periodicRefreshStarted = false;
function setupPeriodicRefresh() {
  if (_periodicRefreshStarted) return;
  _periodicRefreshStarted = true;

  // Auto-sync e verifica periodica ogni 10 secondi
  setInterval(async () => {
    if (state.token || (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured())) {
      const prevRows = state.excelStatus?.orders_count;
      const prevRev = state.excelStatus?.total_revenue;
      const prevLast = state.excelStatus?.last_synced;
      await loadExcelStatus();
      if (state.excelStatus && (state.excelStatus.orders_count !== prevRows || state.excelStatus.total_revenue !== prevRev || state.excelStatus.last_synced !== prevLast)) {
        refreshCurrentView();
      }
    }
  }, 10000);

  // Ricarica automatica al ritorno sulla scheda
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      loadExcelStatus();
      refreshCurrentView();
    }
  });
}

async function loadInitialData() {
  if (window.TavolaraSupabase) {
    await window.TavolaraSupabase.init();
    updateSupabaseStatusBadge();
    setupSupabaseRealtime();
  }
  setupPeriodicRefresh();
  loadExcelStatus();
  switchView("overview");
}

function updateSupabaseStatusBadge() {
  const badge = document.getElementById("side-supabase-badge");
  const proj = document.getElementById("side-supabase-project");
  const status = document.getElementById("side-supabase-status");
  if (!badge) return;

  if (window.TavolaraSupabase && window.TavolaraSupabase.isConfigured()) {
    badge.textContent = "Attivo";
    badge.className = "status-pill incassata";
    if (proj) proj.textContent = "Tavolara Wear (Cloud)";
    if (status) status.textContent = "Supabase DB · RLS Attivo";
  } else {
    badge.textContent = "Locale";
    badge.className = "status-pill in-attesa";
    if (proj) proj.textContent = "SQLite Fallback";
    if (status) status.textContent = "Verifica credenziali in .env";
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

document.addEventListener("DOMContentLoaded", () => {
  // 1. Check Authentication on start
  checkAuth();

  // 2. Login Form & Button
  const handleLoginSubmit = (e) => {
    if (e) e.preventDefault();
    const pwdInput = document.getElementById("admin-pwd");
    const pwd = pwdInput ? pwdInput.value.trim() : "";
    if (pwd) {
      login(pwd);
    }
  };
  document.getElementById("login-form")?.addEventListener("submit", handleLoginSubmit);
  document.getElementById("btn-login")?.addEventListener("click", handleLoginSubmit);
  document.getElementById("admin-pwd")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      handleLoginSubmit(e);
    }
  });

  // 3. Logout Button
  document.getElementById("btn-logout")?.addEventListener("click", logout);

  // 4. Sidebar View Switchers
  document.querySelectorAll(".sidebar-link").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const view = link.dataset.view;
      if (view) switchView(view);
      // Mobile drawer close
      document.getElementById("sidebar")?.classList.remove("open");
    });
  });

  // Mobile bottom navigation bar view switchers
  document.querySelectorAll(".mobile-nav-btn[data-view]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      const view = btn.dataset.view;
      if (view) switchView(view);
    });
  });

  // Mobile menu more button (opens sidebar drawer)
  document.getElementById("mobile-bottom-more")?.addEventListener("click", (e) => {
    e.preventDefault();
    toggleMobileSidebar();
  });

  // Mobile menu toggle in top header
  document.getElementById("mobile-toggle")?.addEventListener("click", (e) => {
    e.preventDefault();
    toggleMobileSidebar();
  });

  // Tap on backdrop closes drawer
  document.getElementById("sidebar-backdrop")?.addEventListener("click", () => {
    closeMobileSidebar();
  });

  // Mobile Floating Action Button (FAB)
  const fabContainer = document.getElementById("mobile-fab-container");
  const fabMain = document.getElementById("mobile-fab-main");
  fabMain?.addEventListener("click", (e) => {
    e.stopPropagation();
    fabContainer?.classList.toggle("active");
  });

  document.getElementById("fab-add-income")?.addEventListener("click", () => {
    fabContainer?.classList.remove("active");
    openAddIncomeModal();
  });

  document.getElementById("fab-add-expense")?.addEventListener("click", () => {
    fabContainer?.classList.remove("active");
    openAddExpenseModal();
  });

  document.addEventListener("click", (e) => {
    if (fabContainer && !fabContainer.contains(e.target)) {
      fabContainer.classList.remove("active");
    }
  });

  // Force Update App button (clears Service Worker & HTTP caches)
  document.getElementById("btn-force-update")?.addEventListener("click", async () => {
    showToast("Aggiornamento dell'app in corso...");
    if ("caches" in window) {
      try {
        const keys = await caches.keys();
        await Promise.all(keys.map(k => caches.delete(k)));
      } catch (err) {}
    }
    if ("serviceWorker" in navigator) {
      try {
        const regs = await navigator.serviceWorker.getRegistrations();
        for (const reg of regs) {
          await reg.unregister();
        }
      } catch (err) {}
    }
    setTimeout(() => {
      window.location.href = window.location.pathname + "?t=" + Date.now();
    }, 400);
  });

  // 5. Time Period Filters
  document.querySelectorAll("#time-filter-control .segment-item").forEach(btn => {
    btn.addEventListener("click", () => {
      const p = btn.dataset.period;
      setTimePeriod(p);
    });
  });

  document.getElementById("btn-apply-custom-date")?.addEventListener("click", () => {
    const s = document.getElementById("custom-date-start").value;
    const e = document.getElementById("custom-date-end").value;
    if (!s || !e) {
      showToast("Inserisci sia data inizio che data fine", "error");
      return;
    }
    state.customStartDate = s;
    state.customEndDate = e;
    refreshCurrentView();
  });

  // 6. Quick Action Header Buttons & Excel Sync
  document.getElementById("btn-quick-add-income")?.addEventListener("click", () => openIncomeModal());
  document.getElementById("btn-quick-add-expense")?.addEventListener("click", () => openExpenseModal());

  // Excel Modal Triggers
  document.getElementById("sidebar-excel-card")?.addEventListener("click", openExcelSyncModal);
  document.getElementById("btn-open-excel-modal")?.addEventListener("click", openExcelSyncModal);
  document.getElementById("btn-trigger-excel-sync")?.addEventListener("click", triggerExcelSync);

  // Drag & drop / file input for Excel upload
  const dropZone = document.getElementById("excel-drop-zone");
  const fileInput = document.getElementById("excel-file-input");
  if (dropZone && fileInput) {
    dropZone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        uploadExcelFile(e.target.files[0]);
      }
    });

    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropZone.style.borderColor = "#0284c7";
      dropZone.style.background = "rgba(224, 242, 254, 0.5)";
    });
    dropZone.addEventListener("dragleave", () => {
      dropZone.style.borderColor = "rgba(203, 213, 225, 0.9)";
      dropZone.style.background = "rgba(248, 250, 252, 0.6)";
    });
    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.style.borderColor = "rgba(203, 213, 225, 0.9)";
      dropZone.style.background = "rgba(248, 250, 252, 0.6)";
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        uploadExcelFile(e.dataTransfer.files[0]);
      }
    });
  }

  // 7. Incomes View Buttons
  document.getElementById("btn-add-income")?.addEventListener("click", () => openIncomeModal());
  document.getElementById("btn-sync-orders-income")?.addEventListener("click", openSyncOrdersModal);
  document.getElementById("form-income")?.addEventListener("submit", saveIncome);

  document.querySelectorAll("#incomes-status-filter .segment-item").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#incomes-status-filter .segment-item").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.incomeStatusFilter = btn.dataset.status;
      loadIncomes();
    });
  });

  document.getElementById("incomes-search")?.addEventListener("input", (e) => {
    state.incomeSearchQuery = e.target.value;
    loadIncomes();
  });

  document.getElementById("btn-export-incomes-csv")?.addEventListener("click", () => {
    window.location.href = "/api/admin/financial/export-csv?type=incomes";
  });

  // 8. Expenses View Buttons & Category Switcher
  document.querySelectorAll("#expenses-category-tabs .segment-item").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#expenses-category-tabs .segment-item").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.expenseCategoryTab = btn.dataset.cat;
      
      const addTxt = document.getElementById("btn-add-expense-text");
      if (addTxt) {
        addTxt.textContent = state.expenseCategoryTab === "all" ? "Registra Spesa" : `+ Spesa ${state.expenseCategoryTab.toUpperCase()}`;
      }
      loadExpenses();
    });
  });

  document.getElementById("btn-add-expense")?.addEventListener("click", () => {
    openExpenseModal(null, state.expenseCategoryTab);
  });

  document.getElementById("form-expense")?.addEventListener("submit", saveExpense);

  document.getElementById("exp-cat")?.addEventListener("change", (e) => {
    updateExpenseModalFields(e.target.value);
  });

  // Dynamic price recalculations in modal
  ["exp-shirt-qty", "exp-shirt-unit", "exp-shirt-extra", "exp-pack-qty", "exp-pack-unit"].forEach(id => {
    document.getElementById(id)?.addEventListener("input", calcExpenseModalAmount);
  });

  document.getElementById("expenses-search")?.addEventListener("input", (e) => {
    state.expenseSearchQuery = e.target.value;
    loadExpenses();
  });

  document.getElementById("btn-export-expenses-csv")?.addEventListener("click", () => {
    window.location.href = "/api/admin/financial/export-csv?type=expenses";
  });

  // 9. Insights Filter Switchers
  document.querySelectorAll("#insights-color-filter .segment-item").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#insights-color-filter .segment-item").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.insightsColorFilter = btn.dataset.color;
      loadInsights();
    });
  });

  document.querySelectorAll("#insights-size-filter .segment-item").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#insights-size-filter .segment-item").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.insightsSizeFilter = btn.dataset.size;
      loadInsights();
    });
  });

  document.getElementById("btn-export-matrix-csv")?.addEventListener("click", () => {
    window.location.href = "/api/admin/financial/export-csv?type=insights_matrix";
  });

  // 10. Orders Filters & Actions
  document.querySelectorAll("#orders-status-filter .segment-item").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#orders-status-filter .segment-item").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.ordersStatusFilter = btn.dataset.status;
      renderOrdersTable(state.orders);
    });
  });

  document.getElementById("orders-search")?.addEventListener("input", (e) => {
    state.ordersSearchQuery = e.target.value;
    renderOrdersTable(state.orders);
  });

  document.getElementById("btn-export-orders-csv")?.addEventListener("click", () => {
    window.location.href = "/api/admin/export-csv";
  });

  // 11. Config Forms
  document.getElementById("form-config-prices")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await apiRequest("/api/admin/config", "PUT", {
        shirt_price: document.getElementById("cfg-shirt-price").value,
        shipping_locker: document.getElementById("cfg-shipping-locker").value,
        shipping_home: document.getElementById("cfg-shipping-home").value,
        shipping_hand: document.getElementById("cfg-shipping-hand").value
      });
      showToast("Prezzi e tariffe salvati con successo");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.getElementById("form-config-bank")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await apiRequest("/api/admin/config", "PUT", {
        bank_holder: document.getElementById("cfg-bank-holder").value,
        bank_iban: document.getElementById("cfg-bank-iban").value,
        bank_name: document.getElementById("cfg-bank-name").value
      });
      showToast("Coordinate bancarie salvate con successo");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.getElementById("form-change-pwd")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const newPwd = document.getElementById("new-admin-pwd").value;
    try {
      await apiRequest("/api/admin/change-password", "POST", { new_password: newPwd });
      showToast("Password amministratore modificata con successo");
      document.getElementById("new-admin-pwd").value = "";
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // 12. Modal Close Buttons
  document.querySelectorAll("[data-close-modal]").forEach(btn => {
    btn.addEventListener("click", () => {
      const modalId = btn.dataset.closeModal;
      document.getElementById(modalId)?.classList.remove("active");
    });
  });

  // Close modals on clicking overlay backdrop
  document.querySelectorAll(".modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        overlay.classList.remove("active");
      }
    });
  });

  // 13. Register PWA Service Worker with Automatic Live Updates
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").then((reg) => {
        // Automatically check for new deployed versions
        reg.addEventListener("updatefound", () => {
          const newWorker = reg.installing;
          if (newWorker) {
            newWorker.addEventListener("statechange", () => {
              if (newWorker.state === "installed" && navigator.serviceWorker.controller) {
                console.log("[PWA] Nuova versione rilevata. Ricarico l'applicazione...");
                showToast("Nuovo aggiornamento installato! Ricarico...", "success");
                setTimeout(() => window.location.reload(), 800);
              }
            });
          }
        });
      }).catch((err) => {
        console.info("[PWA] Service Worker registration:", err);
      });
    });

    // Check for updates when user returns to the app
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        navigator.serviceWorker.getRegistration().then(reg => reg?.update());
      }
    });
  }
});
