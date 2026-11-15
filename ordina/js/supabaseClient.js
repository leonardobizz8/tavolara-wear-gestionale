/**
 * Tavolara Wear — Supabase Client Module
 * Provides unified, secure access to Supabase database for both
 * the customer order collection module and the partners admin dashboard.
 */

(function (window) {
  "use strict";

  const TavolaraSupabase = {
    client: null,
    config: null,
    isReady: false,
    initPromise: null,

    // Initialize client by safely loading config from server
    async init() {
      if (this.initPromise) return this.initPromise;

      this.initPromise = (async () => {
        try {
          const res = await fetch("/api/config");
          if (!res.ok) {
            console.warn("[Tavolara Supabase] Impossible caricare /api/config. Stato:", res.status);
            return false;
          }
          const data = await res.json();
          this.config = data;

          if (data.is_configured && data.supabase_url && data.supabase_anon_key && window.supabase) {
            this.client = window.supabase.createClient(data.supabase_url, data.supabase_anon_key, {
              auth: {
                persistSession: true,
                autoRefreshToken: true,
                detectSessionInUrl: false
              }
            });
            this.isReady = true;
            console.log("[Tavolara Supabase] Connessione attiva al database Tavolara Wear:", data.supabase_url);
            return true;
          } else {
            console.info("[Tavolara Supabase] Configurazione non completa o client CDN non disponibile. Modalità fallback attiva.");
            return false;
          }
        } catch (err) {
          console.warn("[Tavolara Supabase] Errore inizializzazione client:", err);
          return false;
        }
      })();

      return this.initPromise;
    },

    isConfigured() {
      return Boolean(this.isReady && this.client);
    },

    // -------------------------------------------------------------------------
    // AUTHENTICATION
    // -------------------------------------------------------------------------
    async adminLogin(password, email = "admin@tavolarawear.it") {
      await this.init();
      if (!this.isConfigured()) {
        throw new Error("Supabase non è configurato");
      }
      const { data, error } = await this.client.auth.signInWithPassword({
        email: email.trim(),
        password: password
      });
      if (error) {
        throw error;
      }
      return data;
    },

    async adminLogout() {
      if (this.isConfigured()) {
        try {
          await this.client.auth.signOut();
        } catch (e) {
          console.warn("[Tavolara Supabase] Errore signOut:", e);
        }
      }
    },

    async getSession() {
      await this.init();
      if (!this.isConfigured()) return null;
      const { data } = await this.client.auth.getSession();
      return data?.session || null;
    },

    // -------------------------------------------------------------------------
    // PUBLIC CONFIG & VARIANTS
    // -------------------------------------------------------------------------
    async getPublicConfig() {
      await this.init();
      if (!this.isConfigured()) return null;

      const { data, error } = await this.client.from("config").select("key, value");
      if (error) throw error;

      const map = {};
      data.forEach(r => { map[r.key] = r.value; });

      const shirtPrice = map.shirt_price ? parseFloat(map.shirt_price) : null;
      const lockerPrice = map.shipping_locker ? parseFloat(map.shipping_locker) : null;
      const homePrice = map.shipping_home ? parseFloat(map.shipping_home) : null;
      const handPrice = map.shipping_hand ? parseFloat(map.shipping_hand) : 0.0;

      return {
        shirt_price: shirtPrice,
        shipping_locker: lockerPrice,
        shipping_home: homePrice,
        shipping_hand: handPrice,
        is_configured: Boolean(shirtPrice && shirtPrice > 0),
        has_bank_info: Boolean(map.bank_iban && map.bank_holder),
        bank_holder: map.bank_holder || "",
        bank_iban: map.bank_iban || "",
        bank_name: map.bank_name || "",
        bank_notes: map.bank_notes || "",
        brand_name: "Tavolara Wear",
        brand_instagram: map.brand_instagram || "@tavolara.wear",
        brand_site: "https://tavolarawear.it/",
        brand_email: map.brand_email || "info@tavolarawear.it",
        brand_phone: map.brand_phone || ""
      };
    },

    async getVariants() {
      await this.init();
      if (!this.isConfigured()) return null;

      const { data, error } = await this.client
        .from("product_variants")
        .select("id, product_id, color, color_code, size, sku, is_available, stock_qty")
        .order("color_code", { ascending: false })
        .order("id", { ascending: true });

      if (error) throw error;

      return data.map(v => ({
        id: v.id,
        product: "T-shirt Tavolara Wear",
        color: v.color_code,
        color_name: v.color === "Blu" ? "Blu navy" : v.color,
        size: v.size,
        sku: v.sku,
        is_available: v.is_available,
        stock_qty: v.stock_qty
      }));
    },

    async validateDiscount(code) {
      await this.init();
      if (!this.isConfigured()) return null;

      const cleanCode = (code || "").trim().toUpperCase();
      const { data, error } = await this.client
        .from("discount_codes")
        .select("*")
        .eq("code", cleanCode)
        .eq("is_active", true)
        .maybeSingle();

      if (error) throw error;
      if (!data) return { valid: false, message: "Codice sconto non valido o inattivo." };

      if (data.max_uses && data.usage_count >= data.max_uses) {
        return { valid: false, message: "Questo codice sconto ha raggiunto il limite massimo di utilizzi." };
      }

      return {
        valid: true,
        code: data.code,
        discount_type: data.discount_type,
        discount_value: parseFloat(data.discount_value),
        message: `Sconto di ${parseFloat(data.discount_value).toFixed(2)} € applicato con successo!`
      };
    },

    // -------------------------------------------------------------------------
    // ORDER SUBMISSION (PUBLIC CHECKOUT)
    // -------------------------------------------------------------------------
    async submitOrder(formData) {
      await this.init();
      if (!this.isConfigured()) {
        throw new Error("Supabase non è attivo");
      }

      // 1. Fetch public config to compute exact pricing and wire causale
      const cfg = await this.getPublicConfig();
      if (!cfg || !cfg.is_configured) {
        throw new Error("I prezzi non sono ancora configurati dall'amministrazione.");
      }

      const shirtPrice = cfg.shirt_price;
      const qty = parseInt(formData.quantity, 10) || 1;
      const subtotal = shirtPrice * qty;

      let shippingCost = 0.0;
      if (formData.delivery_method === "locker") {
        shippingCost = cfg.shipping_locker || 0.0;
      } else if (formData.delivery_method === "home") {
        shippingCost = cfg.shipping_home || 0.0;
      } else if (formData.delivery_method === "hand") {
        shippingCost = cfg.shipping_hand || 0.0;
      }

      let discountAmount = 0.0;
      let appliedCode = null;
      if (formData.discount_code) {
        const disc = await this.validateDiscount(formData.discount_code);
        if (disc.valid) {
          appliedCode = disc.code;
          discountAmount = disc.discount_type === "percentage" ? (subtotal * disc.discount_value / 100) : disc.discount_value;
          discountAmount = Math.min(discountAmount, subtotal);
        }
      }

      const totalAmount = Math.max(0, subtotal + shippingCost - discountAmount);

      // Generate order number and token
      const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      const randHex = Math.random().toString(16).substring(2, 6).toUpperCase();
      const orderNumber = `TW-${dateStr}-${randHex}`;
      const orderToken = (crypto?.randomUUID ? crypto.randomUUID().replace(/-/g, "") : Math.random().toString(36).substring(2)) + Math.random().toString(36).substring(2);

      const custFirst = formData.customer_first_name.trim();
      const custLast = formData.customer_last_name.trim();
      const wireCausale = `TAVOLARA WEAR - ${custFirst.toUpperCase()} ${custLast.toUpperCase()} - ${orderNumber}`;

      const deliveryDetails = formData.delivery_details || {};

      const colorDb = formData.color === "white" ? "Bianca" : "Blu";
      const colorCode = formData.color === "white" ? "white" : "navy";

      // Prepare RPC payload
      const pCustomer = {
        first_name: custFirst,
        last_name: custLast,
        email: formData.customer_email.trim().toLowerCase(),
        phone: formData.customer_phone.trim(),
        delivery_address: deliveryDetails.address || "",
        delivery_zip: deliveryDetails.zip || "",
        delivery_city: deliveryDetails.city || "",
        delivery_province: deliveryDetails.province || ""
      };

      const pOrder = {
        order_number: orderNumber,
        order_token: orderToken,
        delivery_method: formData.delivery_method,
        locker_name: deliveryDetails.locker_name || "",
        delivery_address: deliveryDetails.address || "",
        delivery_zip: deliveryDetails.zip || "",
        delivery_city: deliveryDetails.city || "",
        delivery_province: deliveryDetails.province || "",
        delivery_notes: deliveryDetails.notes || "",
        hand_location: deliveryDetails.hand_location || "",
        hand_preferences: deliveryDetails.hand_preferences || "",
        shirt_price: shirtPrice,
        shipping_cost: shippingCost,
        discount_code: appliedCode,
        discount_amount: discountAmount,
        total_amount: totalAmount,
        payment_method: "bonifico",
        wire_causale: wireCausale,
        bank_holder: cfg.bank_holder,
        bank_iban: cfg.bank_iban,
        bank_name: cfg.bank_name
      };

      const pItems = [
        {
          product_name: "T-shirt Tavolara Wear",
          color: colorDb,
          color_code: colorCode,
          size: formData.size,
          quantity: qty,
          unit_price: shirtPrice,
          total_price: subtotal
        }
      ];

      const { data, error } = await this.client.rpc("create_tavolara_order", {
        p_customer: pCustomer,
        p_order: pOrder,
        p_items: pItems
      });

      if (error) {
        console.error("[Tavolara Supabase] Errore RPC create_tavolara_order:", error);
        throw error;
      }

      // Format response compatible with app.js confirmation screen
      return {
        success: true,
        order_number: orderNumber,
        order_token: orderToken,
        created_at: data.order.created_at,
        customer: {
          first_name: custFirst,
          last_name: custLast,
          email: formData.customer_email.trim(),
          phone: formData.customer_phone.trim()
        },
        delivery: {
          method: formData.delivery_method,
          details: deliveryDetails
        },
        product: {
          name: "T-shirt Tavolara Wear",
          color: colorCode,
          color_name: colorDb === "Blu" ? "Blu navy" : "Bianca",
          size: formData.size,
          quantity: qty
        },
        pricing: {
          unit_price: shirtPrice,
          subtotal: subtotal,
          shipping_cost: shippingCost,
          discount_code: appliedCode,
          discount_amount: discountAmount,
          total_amount: totalAmount
        },
        bank: {
          holder: cfg.bank_holder,
          iban: cfg.bank_iban,
          name: cfg.bank_name,
          causale: wireCausale,
          notes: cfg.bank_notes
        }
      };
    },

    async getOrderByToken(token) {
      await this.init();
      if (!this.isConfigured()) return null;

      const { data, error } = await this.client.rpc("get_order_by_token", { p_token: token });
      if (error) throw error;
      return data;
    },

    // -------------------------------------------------------------------------
    // ADMIN: ORDERS MANAGEMENT
    // -------------------------------------------------------------------------
    async getOrders(filters = {}) {
      await this.init();
      if (!this.isConfigured()) return null;

      let query = this.client
        .from("orders")
        .select("*, order_items(*)")
        .order("id", { ascending: false });

      if (filters.status && filters.status !== "all") {
        query = query.eq("status", filters.status);
      }

      if (filters.delivery && filters.delivery !== "all") {
        query = query.eq("delivery_method", filters.delivery);
      }

      if (filters.dateFrom) {
        query = query.gte("created_at", filters.dateFrom + "T00:00:00");
      }
      if (filters.dateTo) {
        query = query.lte("created_at", filters.dateTo + "T23:59:59");
      }

      const { data, error } = await query;
      if (error) throw error;

      // Map order items to match frontend structure
      let list = data.map(o => ({
        ...o,
        items: (o.order_items || []).map(i => ({
          ...i,
          color_name: i.color === "Blu" ? "Blu navy" : i.color
        }))
      }));

      if (filters.search && filters.search.trim()) {
        const term = filters.search.trim().toLowerCase();
        list = list.filter(o =>
          (o.order_number && o.order_number.toLowerCase().includes(term)) ||
          (o.customer_first_name && o.customer_first_name.toLowerCase().includes(term)) ||
          (o.customer_last_name && o.customer_last_name.toLowerCase().includes(term)) ||
          (o.customer_email && o.customer_email.toLowerCase().includes(term))
        );
      }

      return { orders: list, count: list.length };
    },

    async updateOrderStatus(orderId, newStatus) {
      await this.init();
      if (!this.isConfigured()) return null;

      let paymentStatus = "da_pagare";
      if (newStatus === "Ordine pagato" || newStatus === "Pagamento verificato") {
        paymentStatus = "pagato";
      } else if (newStatus === "Ordine da pagare") {
        paymentStatus = "in_attesa";
      }

      const { data, error } = await this.client
        .from("orders")
        .update({
          status: newStatus,
          payment_status: paymentStatus,
          updated_at: new Date().toISOString()
        })
        .eq("id", orderId)
        .select()
        .single();

      if (error) throw error;

      // If status changed to Ordine pagato, record transaction in Attivo if not existing
      if (paymentStatus === "pagato") {
        await this.syncOrderToIncome(orderId);
      }

      return data;
    },

    // -------------------------------------------------------------------------
    // ADMIN: ATTIVO (TRANSAZIONI / INCASSI EFFETTIVI)
    // -------------------------------------------------------------------------
    async getIncomes(filters = {}) {
      await this.init();
      if (!this.isConfigured()) return null;

      let query = this.client
        .from("transactions")
        .select("*")
        .order("date", { ascending: false })
        .order("id", { ascending: false });

      if (filters.status && filters.status !== "all") {
        query = query.eq("status", filters.status);
      }

      if (filters.startDate) {
        query = query.gte("date", filters.startDate);
      }
      if (filters.endDate) {
        query = query.lte("date", filters.endDate);
      }

      const { data, error } = await query;
      if (error) throw error;

      let list = data || [];
      if (filters.search && filters.search.trim()) {
        const term = filters.search.trim().toLowerCase();
        list = list.filter(i =>
          (i.description && i.description.toLowerCase().includes(term)) ||
          (i.reference && i.reference.toLowerCase().includes(term)) ||
          (i.notes && i.notes.toLowerCase().includes(term))
        );
      }

      const collected = list.filter(i => i.status === "Incassata").reduce((s, i) => s + parseFloat(i.amount), 0);
      const confirmed = list.filter(i => i.status === "Confermata").reduce((s, i) => s + parseFloat(i.amount), 0);
      const pending = list.filter(i => i.status === "In attesa").reduce((s, i) => s + parseFloat(i.amount), 0);
      const total = collected + confirmed + pending;

      return {
        incomes: list,
        total,
        count: list.length,
        collected,
        confirmed,
        pending,
        summary: {
          total: Math.round(total * 100) / 100,
          collected: Math.round(collected * 100) / 100,
          confirmed: Math.round(confirmed * 100) / 100,
          pending: Math.round(pending * 100) / 100,
          count: list.length
        }
      };
    },

    async createIncome(payload) {
      await this.init();
      if (!this.isConfigured()) return null;

      const record = {
        description: payload.description.trim(),
        amount: parseFloat(payload.amount),
        date: payload.date || new Date().toISOString().slice(0, 10),
        payment_method: payload.payment_method || "Bonifico bancario",
        reference: payload.order_reference || payload.reference || "",
        order_id: payload.order_id ? parseInt(payload.order_id, 10) : null,
        status: payload.status || "Confermata",
        notes: payload.notes || ""
      };

      const { data, error } = await this.client
        .from("transactions")
        .insert(record)
        .select()
        .single();

      if (error) throw error;
      return { income: data };
    },

    async updateIncome(id, payload) {
      await this.init();
      if (!this.isConfigured()) return null;

      const record = {
        updated_at: new Date().toISOString()
      };
      if (payload.description) record.description = payload.description.trim();
      if (payload.amount !== undefined) record.amount = parseFloat(payload.amount);
      if (payload.date) record.date = payload.date;
      if (payload.payment_method) record.payment_method = payload.payment_method;
      if (payload.order_reference !== undefined) record.reference = payload.order_reference;
      if (payload.status) record.status = payload.status;
      if (payload.notes !== undefined) record.notes = payload.notes;

      const { data, error } = await this.client
        .from("transactions")
        .update(record)
        .eq("id", id)
        .select()
        .single();

      if (error) throw error;
      return { income: data };
    },

    async deleteIncome(id) {
      await this.init();
      if (!this.isConfigured()) return null;

      const { error } = await this.client.from("transactions").delete().eq("id", id);
      if (error) throw error;
      return { success: true };
    },

    async syncOrderToIncome(orderId) {
      await this.init();
      if (!this.isConfigured()) return null;

      // Check if already synced
      const { data: existing } = await this.client
        .from("transactions")
        .select("id")
        .eq("order_id", orderId)
        .maybeSingle();

      if (existing) {
        return { success: true, message: "Ordine già registrato nelle entrate", id: existing.id };
      }

      // Fetch order
      const { data: ord, error: ordErr } = await this.client
        .from("orders")
        .select("*")
        .eq("id", orderId)
        .single();

      if (ordErr || !ord) throw new Error("Ordine non trovato");

      const incomePayload = {
        description: `Ordine #${ord.order_number} — ${ord.customer_first_name} ${ord.customer_last_name}`,
        amount: ord.total_amount,
        date: ord.created_at.slice(0, 10),
        payment_method: "Bonifico bancario",
        reference: ord.order_number,
        order_id: ord.id,
        status: (ord.status === "Ordine pagato" || ord.status === "Pagamento verificato") ? "Incassata" : "Confermata",
        notes: `Sincronizzato da modulo ordini. Consegna: ${ord.delivery_method}`
      };

      const { data: newInc, error: incErr } = await this.client
        .from("transactions")
        .insert(incomePayload)
        .select()
        .single();

      if (incErr) throw incErr;
      return { success: true, income: newInc };
    },

    // -------------------------------------------------------------------------
    // ADMIN: PASSIVO (USCITE & SPESE NELLE 4 CATEGORIE)
    // -------------------------------------------------------------------------
    async getExpenses(filters = {}) {
      await this.init();
      if (!this.isConfigured()) return null;

      let query = this.client
        .from("expenses")
        .select("*")
        .order("date", { ascending: false })
        .order("id", { ascending: false });

      if (filters.category && filters.category !== "all") {
        query = query.eq("category_code", filters.category);
      }
      if (filters.startDate) {
        query = query.gte("date", filters.startDate);
      }
      if (filters.endDate) {
        query = query.lte("date", filters.endDate);
      }

      const { data, error } = await query;
      if (error) throw error;

      let list = (data || []).map(e => ({
        ...e,
        category: e.category_code
      }));

      if (filters.search && filters.search.trim()) {
        const term = filters.search.trim().toLowerCase();
        list = list.filter(e =>
          (e.description && e.description.toLowerCase().includes(term)) ||
          (e.carrier && e.carrier.toLowerCase().includes(term)) ||
          (e.supplier && e.supplier.toLowerCase().includes(term)) ||
          (e.material_type && e.material_type.toLowerCase().includes(term))
        );
      }

      const breakdown = {
        trasporto: 0,
        imballaggio: 0,
        prove: 0,
        magliette: 0
      };
      let total = 0;
      let totalShipments = 0;
      let totalPackagingItems = 0;
      let totalShirtsPurchased = 0;

      list.forEach(e => {
        const amt = parseFloat(e.amount) || 0;
        total += amt;
        if (breakdown[e.category_code] !== undefined) {
          breakdown[e.category_code] += amt;
        }
        if (e.category_code === "trasporto") totalShipments += (parseInt(e.shipment_count, 10) || 1);
        if (e.category_code === "imballaggio") totalPackagingItems += (parseInt(e.quantity, 10) || 0);
        if (e.category_code === "magliette") totalShirtsPurchased += (parseInt(e.quantity, 10) || 0);
      });

      const avgUnitCost = totalShirtsPurchased > 0 ? (breakdown.magliette / totalShirtsPurchased) : 0.0;

      return {
        expenses: list,
        total: Math.round(total * 100) / 100,
        count: list.length,
        breakdown,
        summary: {
          total_amount: Math.round(total * 100) / 100,
          by_category: {
            trasporto: Math.round(breakdown.trasporto * 100) / 100,
            imballaggio: Math.round(breakdown.imballaggio * 100) / 100,
            prove: Math.round(breakdown.prove * 100) / 100,
            magliette: Math.round(breakdown.magliette * 100) / 100
          },
          category_metrics: {
            total_shipments: totalShipments,
            total_packaging_items: totalPackagingItems,
            total_shirts_purchased: totalShirtsPurchased,
            avg_unit_cost: Math.round(avgUnitCost * 100) / 100
          }
        }
      };
    },

    async createExpense(payload) {
      await this.init();
      if (!this.isConfigured()) return null;

      const record = {
        category_code: payload.category,
        description: payload.description.trim(),
        amount: parseFloat(payload.amount),
        date: payload.date || new Date().toISOString().slice(0, 10),
        carrier: payload.carrier || "",
        shipment_count: payload.shipment_count ? parseInt(payload.shipment_count, 10) : 1,
        shipment_type: payload.shipment_type || "singola",
        material_type: payload.material_type || "",
        quantity: payload.quantity ? parseInt(payload.quantity, 10) : 0,
        unit_cost: payload.unit_cost ? parseFloat(payload.unit_cost) : 0.0,
        proof_type: payload.proof_type || "",
        supplier: payload.supplier || "",
        extra_production_costs: payload.extra_production_costs ? parseFloat(payload.extra_production_costs) : 0.0,
        notes: payload.notes || ""
      };

      const { data, error } = await this.client
        .from("expenses")
        .insert(record)
        .select()
        .single();

      if (error) throw error;
      return { expense: { ...data, category: data.category_code } };
    },

    async updateExpense(id, payload) {
      await this.init();
      if (!this.isConfigured()) return null;

      const record = {
        updated_at: new Date().toISOString()
      };
      if (payload.category) record.category_code = payload.category;
      if (payload.description) record.description = payload.description.trim();
      if (payload.amount !== undefined) record.amount = parseFloat(payload.amount);
      if (payload.date) record.date = payload.date;
      if (payload.carrier !== undefined) record.carrier = payload.carrier;
      if (payload.shipment_count !== undefined) record.shipment_count = parseInt(payload.shipment_count, 10);
      if (payload.shipment_type !== undefined) record.shipment_type = payload.shipment_type;
      if (payload.material_type !== undefined) record.material_type = payload.material_type;
      if (payload.quantity !== undefined) record.quantity = parseInt(payload.quantity, 10);
      if (payload.unit_cost !== undefined) record.unit_cost = parseFloat(payload.unit_cost);
      if (payload.proof_type !== undefined) record.proof_type = payload.proof_type;
      if (payload.supplier !== undefined) record.supplier = payload.supplier;
      if (payload.extra_production_costs !== undefined) record.extra_production_costs = parseFloat(payload.extra_production_costs);
      if (payload.notes !== undefined) record.notes = payload.notes;

      const { data, error } = await this.client
        .from("expenses")
        .update(record)
        .eq("id", id)
        .select()
        .single();

      if (error) throw error;
      return { expense: { ...data, category: data.category_code } };
    },

    async deleteExpense(id) {
      await this.init();
      if (!this.isConfigured()) return null;

      const { error } = await this.client.from("expenses").delete().eq("id", id);
      if (error) throw error;
      return { success: true };
    },

    // -------------------------------------------------------------------------
    // ADMIN: OVERVIEW FINANCIAL METRICS
    // -------------------------------------------------------------------------
    async getOverviewData(period = "all", customStart = null, customEnd = null) {
      await this.init();
      if (!this.isConfigured()) return null;

      // Compute date filters
      let startDate = null;
      let endDate = null;
      const today = new Date();
      const todayStr = today.toISOString().slice(0, 10);

      if (period === "today") {
        startDate = todayStr;
        endDate = todayStr;
      } else if (period === "week") {
        const d = new Date(today);
        d.setDate(d.getDate() - 6);
        startDate = d.toISOString().slice(0, 10);
        endDate = todayStr;
      } else if (period === "month") {
        startDate = today.getFullYear() + "-" + String(today.getMonth() + 1).padStart(2, "0") + "-01";
        endDate = todayStr;
      } else if (period === "quarter") {
        const qMonth = Math.floor(today.getMonth() / 3) * 3 + 1;
        startDate = today.getFullYear() + "-" + String(qMonth).padStart(2, "0") + "-01";
        endDate = todayStr;
      } else if (period === "year") {
        startDate = today.getFullYear() + "-01-01";
        endDate = todayStr;
      } else if (period === "custom") {
        startDate = customStart;
        endDate = customEnd;
      }

      // 1. Fetch transactions (Attivo)
      const incRes = await this.getIncomes({ startDate, endDate });
      const totalIncomes = incRes?.total || 0;
      const collectedIncomes = (incRes?.collected || 0) + (incRes?.confirmed || 0);

      // 2. Fetch expenses (Passivo nelle 4 categorie)
      const expRes = await this.getExpenses({ startDate, endDate });
      const totalExpenses = expRes?.total || 0;

      // 3. Current balance & gross margin
      const currentBalance = totalIncomes - totalExpenses;
      const directProductionCost = (expRes?.breakdown?.magliette || 0) + (expRes?.breakdown?.prove || 0);
      const grossProfit = totalIncomes > 0 ? (totalIncomes - directProductionCost) : -totalExpenses;
      const grossProfitMargin = totalIncomes > 0 ? ((grossProfit / totalIncomes) * 100) : 0;

      // 4. Fetch orders & shirts sold
      let ordQuery = this.client
        .from("orders")
        .select("id, total_amount, status, created_at, order_items(quantity)")
        .neq("status", "Annullato");

      if (startDate) ordQuery = ordQuery.gte("created_at", startDate + "T00:00:00");
      if (endDate) ordQuery = ordQuery.lte("created_at", endDate + "T23:59:59");

      const { data: ordersData } = await ordQuery;
      const activeOrders = ordersData || [];
      const ordersCount = activeOrders.length;

      let shirtsSold = 0;
      let orderTurnover = 0;
      activeOrders.forEach(o => {
        orderTurnover += parseFloat(o.total_amount) || 0;
        (o.order_items || []).forEach(it => {
          shirtsSold += (it.quantity || 0);
        });
      });

      // Quantity from expenses
      const purchasedShirts = (expRes?.expenses || [])
        .filter(e => e.category === "magliette" || e.category_code === "magliette")
        .reduce((s, e) => s + (parseInt(e.quantity, 10) || 0), 0);

      const expMagliette = expRes?.breakdown?.magliette || 0;
      const avgShirtCost = purchasedShirts > 0
        ? (expMagliette / purchasedShirts)
        : (shirtsSold > 0 && expMagliette > 0 ? (expMagliette / shirtsSold) : 0);

      const avgOrderRev = ordersCount > 0 ? (orderTurnover / ordersCount) : 0;

      // 5. Generate daily time series for charts
      const timeSeries = this._buildTimeSeries(incRes?.incomes || [], expRes?.expenses || [], activeOrders, startDate, endDate);

      const cashflowTimeline = timeSeries.map(d => ({
        date: d.date,
        incomes: d.incomes,
        expenses: d.expenses
      }));

      const balanceTimeline = timeSeries.map(d => ({
        date: d.date,
        balance: d.balance
      }));

      const salesTimeline = timeSeries.map(d => ({
        date: d.date,
        orders: d.orders || (d.shirts > 0 ? 1 : 0),
        shirts: d.shirts || 0,
        revenue: d.incomes || 0
      }));

      const expensesByCategory = {
        labels: ["Trasporto", "Imballaggio", "Prove", "Magliette"],
        values: [
          expRes?.breakdown?.trasporto || 0,
          expRes?.breakdown?.imballaggio || 0,
          expRes?.breakdown?.prove || 0,
          expRes?.breakdown?.magliette || 0
        ],
        colors: ["#3B7A9E", "#A76B29", "#6E4973", "#1F364D"]
      };

      const kpis = {
        total_incomes: Math.round(totalIncomes * 100) / 100,
        total_expenses: Math.round(totalExpenses * 100) / 100,
        current_balance: Math.round(currentBalance * 100) / 100,
        gross_profit: Math.round(grossProfit * 100) / 100,
        gross_profit_margin: Math.round(grossProfitMargin * 10) / 10,
        total_shirts_sold: shirtsSold,
        shirts_sold: shirtsSold,
        total_orders_count: ordersCount,
        orders_count: ordersCount,
        avg_shirt_cost: Math.round(avgShirtCost * 100) / 100,
        average_shirt_cost: Math.round(avgShirtCost * 100) / 100,
        avg_order_revenue: Math.round(avgOrderRev * 100) / 100,
        average_order_revenue: Math.round(avgOrderRev * 100) / 100,
        incomes_breakdown: {
          total: incRes?.total || 0,
          collected: incRes?.collected || 0,
          confirmed: incRes?.confirmed || 0,
          pending: incRes?.pending || 0,
          count: incRes?.count || 0
        },
        expenses_breakdown: {
          trasporto: expRes?.breakdown?.trasporto || 0,
          imballaggio: expRes?.breakdown?.imballaggio || 0,
          prove: expRes?.breakdown?.prove || 0,
          magliette: expRes?.breakdown?.magliette || 0,
          count: expRes?.count || 0
        }
      };

      return {
        kpis,
        charts: {
          cashflow_timeline: cashflowTimeline,
          balance_timeline: balanceTimeline,
          expenses_by_category: expensesByCategory,
          sales_timeline: salesTimeline
        },
        time_series: timeSeries,
        date_range: {
          period: period,
          start: startDate,
          end: endDate
        }
      };
    },

    _buildTimeSeries(incomes, expenses, orders, startDate, endDate) {
      const dayMap = {};

      const getDayKey = (dStr) => (dStr || "").slice(0, 10);

      incomes.forEach(i => {
        const k = getDayKey(i.date);
        if (!k) return;
        if (!dayMap[k]) dayMap[k] = { date: k, income: 0, expense: 0, shirts: 0, orders: 0, balance: 0 };
        dayMap[k].income += parseFloat(i.amount) || 0;
      });

      expenses.forEach(e => {
        const k = getDayKey(e.date);
        if (!k) return;
        if (!dayMap[k]) dayMap[k] = { date: k, income: 0, expense: 0, shirts: 0, orders: 0, balance: 0 };
        dayMap[k].expense += parseFloat(e.amount) || 0;
      });

      orders.forEach(o => {
        const k = getDayKey(o.created_at);
        if (!k) return;
        if (!dayMap[k]) dayMap[k] = { date: k, income: 0, expense: 0, shirts: 0, orders: 0, balance: 0 };
        dayMap[k].orders += 1;
        (o.order_items || []).forEach(it => {
          dayMap[k].shirts += (it.quantity || 0);
        });
      });

      const sortedDays = Object.keys(dayMap).sort();
      let runningBalance = 0;
      return sortedDays.map(d => {
        const item = dayMap[d];
        runningBalance += (item.income - item.expense);
        return {
          date: d,
          incomes: item.income,
          expenses: item.expense,
          shirts: item.shirts,
          orders: item.orders,
          balance: runningBalance
        };
      });
    },

    // -------------------------------------------------------------------------
    // ADMIN: INSIGHTS & ANALYTICS (TAGLIE, COLORI, REDDITIVITÀ)
    // -------------------------------------------------------------------------
    async getInsightsData() {
      await this.init();
      if (!this.isConfigured()) return null;

      // 1. Fetch non-cancelled order items
      const { data: orders } = await this.client
        .from("orders")
        .select("id, total_amount, status, order_items(color, color_code, size, quantity, unit_price)")
        .neq("status", "Annullato");

      let totalShirts = 0;
      let navySold = 0;
      let whiteSold = 0;

      const sizeCounts = {
        S: { navy: 0, white: 0, total: 0 },
        M: { navy: 0, white: 0, total: 0 },
        L: { navy: 0, white: 0, total: 0 },
        XL: { navy: 0, white: 0, total: 0 },
        XXL: { navy: 0, white: 0, total: 0 },
        "3XL": { navy: 0, white: 0, total: 0 }
      };

      (orders || []).forEach(o => {
        (o.order_items || []).forEach(it => {
          const qty = it.quantity || 0;
          totalShirts += qty;

          const isWhite = it.color_code === "white" || (it.color && it.color.toLowerCase().includes("bianc"));
          if (isWhite) {
            whiteSold += qty;
          } else {
            navySold += qty;
          }

          let s = (it.size || "M").toUpperCase().trim();
          if (s === "2XL") s = "XXL";
          if (s === "XXXL") s = "3XL";
          if (!sizeCounts[s]) sizeCounts[s] = { navy: 0, white: 0, total: 0 };

          if (isWhite) {
            sizeCounts[s].white += qty;
          } else {
            sizeCounts[s].navy += qty;
          }
          sizeCounts[s].total += qty;
        });
      });

      const navyPct = totalShirts > 0 ? (navySold / totalShirts) * 100 : 0;
      const whitePct = totalShirts > 0 ? (whiteSold / totalShirts) * 100 : 0;

      const SIZES_ORDER = ["S", "M", "L", "XL", "XXL", "3XL"];
      const matrixRows = SIZES_ORDER.map(s => {
        const row = sizeCounts[s] || { navy: 0, white: 0, total: 0 };
        const pct = totalShirts > 0 ? (row.total / totalShirts) * 100 : 0;
        return {
          size: s,
          navy: row.navy,
          white: row.white,
          total: row.total,
          percentage: Math.round(pct * 10) / 10
        };
      });

      return {
        color_stats: {
          total_shirts: totalShirts,
          navy_sold: navySold,
          navy_percentage: Math.round(navyPct * 10) / 10,
          white_sold: whiteSold,
          white_percentage: Math.round(whitePct * 10) / 10
        },
        size_stats: {
          cross_matrix: {
            rows: matrixRows,
            total_row: {
              navy: navySold,
              white: whiteSold,
              total: totalShirts,
              percentage: totalShirts > 0 ? 100.0 : 0.0
            }
          }
        }
      };
    },

    // -------------------------------------------------------------------------
    // ADMIN: VARIANTS & CONFIG MANAGEMENT
    // -------------------------------------------------------------------------
    async updateVariantAvailability(id, isAvailable) {
      await this.init();
      if (!this.isConfigured()) return null;

      const { data, error } = await this.client
        .from("product_variants")
        .update({ is_available: isAvailable, updated_at: new Date().toISOString() })
        .eq("id", id)
        .select()
        .single();

      if (error) throw error;
      return data;
    },

    async updateVariantStock(id, stockQty) {
      await this.init();
      if (!this.isConfigured()) return null;

      const { data, error } = await this.client
        .from("product_variants")
        .update({ stock_qty: parseInt(stockQty, 10), updated_at: new Date().toISOString() })
        .eq("id", id)
        .select()
        .single();

      if (error) throw error;
      return data;
    },

    async updateConfig(keyValues) {
      await this.init();
      if (!this.isConfigured()) return null;

      const rows = Object.entries(keyValues).map(([k, v]) => ({
        key: k,
        value: String(v),
        updated_at: new Date().toISOString()
      }));

      const { error } = await this.client
        .from("config")
        .upsert(rows);

      if (error) throw error;
      return { success: true };
    }
  };

  // Expose to window
  window.TavolaraSupabase = TavolaraSupabase;

  // Auto-initialize on load
  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", () => {
      TavolaraSupabase.init();
    });
  }
})(window);
