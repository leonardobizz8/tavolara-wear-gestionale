/**
 * Tavolara Wear — Frontend Client Application
 * Order flow, live calculations, validation, photo switcher, and bank wire screen.
 */

// State
const state = {
  currentStep: 1,
  config: null,
  variants: [],
  selectedColor: "navy",
  selectedAngle: "front",
  selectedSize: "M",
  quantity: 1,
  deliveryMethod: "locker", // 'locker', 'home', 'hand'
  discountCode: null,
  discountAmount: 0.0,
  orderSubmitting: false,
  orderConfirmedData: null
};

// Image mappings
const photoMap = {
  navy: {
    front: "/assets/gallery/navy-front-v3.webp",
    back: "/assets/gallery/navy-back-v3.webp"
  },
  white: {
    front: "/assets/gallery/white-front-v3.webp",
    back: "/assets/gallery/white-back-v3.webp"
  }
};

// DOM references
const dom = {
  stepperProgress: document.getElementById("stepper-progress"),
  stepNodes: [
    document.getElementById("step-btn-1"),
    document.getElementById("step-btn-2"),
    document.getElementById("step-btn-3")
  ],
  steps: {
    1: document.getElementById("step-1"),
    2: document.getElementById("step-2"),
    3: document.getElementById("step-3"),
    conf: document.getElementById("step-confirmation")
  },
  unconfiguredAlert: document.getElementById("unconfigured-alert"),
  productImg: document.getElementById("product-view-img"),
  angleFrontBtn: document.getElementById("angle-front-btn"),
  angleBackBtn: document.getElementById("angle-back-btn"),
  colorCards: document.querySelectorAll(".color-card"),
  sizesContainer: document.getElementById("sizes-container"),
  unitPriceDisplay: document.getElementById("unit-price-display"),
  qtyMinus: document.getElementById("qty-minus"),
  qtyPlus: document.getElementById("qty-plus"),
  qtyValue: document.getElementById("qty-value"),
  
  // Step 2 elements
  custName: document.getElementById("cust-name"),
  custSurname: document.getElementById("cust-surname"),
  custEmail: document.getElementById("cust-email"),
  custPhone: document.getElementById("cust-phone"),
  deliveryCards: document.querySelectorAll(".delivery-card"),
  priceBadgeLocker: document.getElementById("price-badge-locker"),
  priceBadgeHome: document.getElementById("price-badge-home"),
  priceBadgeHand: document.getElementById("price-badge-hand"),
  fieldsLocker: document.getElementById("fields-locker"),
  fieldsHome: document.getElementById("fields-home"),
  fieldsHand: document.getElementById("fields-hand"),
  
  // Step 3 elements
  summaryProdThumb: document.getElementById("summary-prod-thumb"),
  summaryProdDetails: document.getElementById("summary-prod-details"),
  summaryProdSubtotal: document.getElementById("summary-prod-subtotal"),
  summaryDeliveryTitle: document.getElementById("summary-delivery-title"),
  summaryDeliveryDesc: document.getElementById("summary-delivery-desc"),
  discountInput: document.getElementById("discount-code-input"),
  btnApplyDiscount: document.getElementById("btn-apply-discount"),
  discountFeedback: document.getElementById("discount-feedback"),
  calcQty: document.getElementById("calc-qty"),
  calcUnitPrice: document.getElementById("calc-unit-price"),
  calcSubtotal: document.getElementById("calc-subtotal"),
  calcShipping: document.getElementById("calc-shipping"),
  rowDiscount: document.getElementById("row-discount"),
  appliedDiscountCode: document.getElementById("applied-discount-code"),
  calcDiscount: document.getElementById("calc-discount"),
  calcFinalTotal: document.getElementById("calc-final-total"),
  privacyConsent: document.getElementById("privacy-consent"),
  btnSubmitOrder: document.getElementById("btn-submit-order"),

  // Modal Size Guide
  sizeModal: document.getElementById("size-guide-modal"),
  openSizeModal: document.getElementById("open-size-modal"),
  closeSizeModal: document.getElementById("close-size-modal"),
  btnSizeDone: document.getElementById("btn-size-done"),

  // Toast
  toast: document.getElementById("toast"),
  toastText: document.getElementById("toast-text")
};

// Toast message helper
function showToast(msg, duration = 3000) {
  dom.toastText.textContent = msg;
  dom.toast.classList.add("show");
  setTimeout(() => dom.toast.classList.remove("show"), duration);
}

// Copy to clipboard helper
function initCopyButtons() {
  document.querySelectorAll(".btn-copy").forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-copy-target");
      let text = "";
      if (targetId === "conf-wire-amount-raw") {
        text = state.orderConfirmedData?.total_amount ? state.orderConfirmedData.total_amount.toFixed(2) + " €" : "";
      } else {
        const el = document.getElementById(targetId);
        text = el ? el.innerText.trim() : "";
      }
      if (text) {
        navigator.clipboard.writeText(text).then(() => {
          const original = btn.textContent;
          btn.textContent = "Copiato!";
          btn.classList.add("copied");
          showToast("Copiato negli appunti: " + text);
          setTimeout(() => {
            btn.textContent = original;
            btn.classList.remove("copied");
          }, 2000);
        }).catch(() => {
          showToast("Impossibile copiare automaticamente.");
        });
      }
    });
  });
}

// Initialize Application
async function initApp() {
  try {
    // 1. Fetch public configuration
    const resCfg = await fetch("/api/config/public");
    state.config = await resCfg.json();

    // 2. Fetch variants & availability
    const resVar = await fetch("/api/variants");
    const dataVar = await resVar.json();
    state.variants = dataVar.variants || [];

    // Check if system is configured
    renderConfigStatus();

    // Render sizes for initially selected color
    renderSizesForColor(state.selectedColor);

    // Update prices & badges
    updatePricingBreakdown();

    // Check URL for token (confirmation screen reload / bookmark)
    checkUrlForOrderToken();

  } catch (err) {
    console.error("Errore caricamento configurazione:", err);
    showToast("Errore di caricamento dati. Riprova.");
  }
}

// Render config status (check if price and shipping configured)
function renderConfigStatus() {
  const isConfigured = state.config?.is_configured;
  if (!isConfigured) {
    dom.unconfiguredAlert.style.display = "block";
    dom.btnSubmitOrder.disabled = true;
    dom.btnSubmitOrder.textContent = "Ordini temporaneamente non disponibili (Prezzi in aggiornamento)";
  } else {
    dom.unconfiguredAlert.style.display = "none";
    dom.btnSubmitOrder.disabled = false;
    dom.btnSubmitOrder.textContent = "Conferma Ordine e Procedi al Bonifico";
  }

  // Update shipping badges
  if (state.config?.shipping_locker !== null && state.config?.shipping_locker !== undefined) {
    dom.priceBadgeLocker.textContent = state.config.shipping_locker === 0 ? "Gratis" : state.config.shipping_locker.toFixed(2) + " €";
  } else {
    dom.priceBadgeLocker.textContent = "-- €";
  }

  if (state.config?.shipping_home !== null && state.config?.shipping_home !== undefined) {
    dom.priceBadgeHome.textContent = state.config.shipping_home === 0 ? "Gratis" : state.config.shipping_home.toFixed(2) + " €";
  } else {
    dom.priceBadgeHome.textContent = "-- €";
  }

  if (state.config?.shipping_hand !== null && state.config?.shipping_hand !== undefined) {
    dom.priceBadgeHand.textContent = state.config.shipping_hand === 0 ? "Gratuita" : state.config.shipping_hand.toFixed(2) + " €";
  }

  if (state.config?.shirt_price) {
    dom.unitPriceDisplay.textContent = `Prezzo unitario: ${state.config.shirt_price.toFixed(2)} €`;
  } else {
    dom.unitPriceDisplay.textContent = "Prezzo unitario: in aggiornamento";
  }
}

// Render sizes grid and availability for selected color
function renderSizesForColor(color) {
  const colorVariants = state.variants.filter(v => v.color === color);
  dom.sizesContainer.innerHTML = "";

  const allowedOrder = ["S", "M", "L", "XL", "XXL", "XXXL"];
  
  // Sort according to allowedOrder
  colorVariants.sort((a, b) => allowedOrder.indexOf(a.size) - allowedOrder.indexOf(b.size));

  // If current selectedSize is not available in new color, pick first available
  let sizeAvailable = false;
  colorVariants.forEach(v => {
    if (v.size === state.selectedSize && v.is_available) {
      sizeAvailable = true;
    }
  });

  if (!sizeAvailable) {
    const firstAvail = colorVariants.find(v => v.is_available);
    if (firstAvail) {
      state.selectedSize = firstAvail.size;
    }
  }

  colorVariants.forEach(v => {
    const pill = document.createElement("div");
    pill.className = "size-pill";
    if (v.size === state.selectedSize && v.is_available) {
      pill.classList.add("active");
    }
    if (!v.is_available) {
      pill.classList.add("disabled");
      pill.setAttribute("aria-disabled", "true");
    }
    pill.dataset.size = v.size;
    pill.innerHTML = `<strong>${v.size === "XXXL" ? "3XL" : (v.size === "XXL" ? "2XL" : v.size)}</strong>`;

    if (v.is_available) {
      pill.addEventListener("click", () => {
        document.querySelectorAll(".size-pill").forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        state.selectedSize = v.size;
        updatePricingBreakdown();
      });
    }

    dom.sizesContainer.appendChild(pill);
  });
}

// Update product image according to color and angle
function updateProductImage() {
  const src = photoMap[state.selectedColor][state.selectedAngle];
  dom.productImg.style.opacity = "0.4";
  dom.productImg.src = src;
  dom.productImg.onload = () => {
    dom.productImg.style.opacity = "1";
  };
}

// Event Listeners: Color & Angle
dom.colorCards.forEach(card => {
  card.addEventListener("click", () => {
    dom.colorCards.forEach(c => {
      c.classList.remove("active");
      c.setAttribute("aria-checked", "false");
    });
    card.classList.add("active");
    card.setAttribute("aria-checked", "true");
    state.selectedColor = card.dataset.color;
    updateProductImage();
    renderSizesForColor(state.selectedColor);
  });
});

dom.angleFrontBtn.addEventListener("click", () => {
  dom.angleFrontBtn.classList.add("active");
  dom.angleBackBtn.classList.remove("active");
  state.selectedAngle = "front";
  updateProductImage();
});

dom.angleBackBtn.addEventListener("click", () => {
  dom.angleBackBtn.classList.add("active");
  dom.angleFrontBtn.classList.remove("active");
  state.selectedAngle = "back";
  updateProductImage();
});

// Quantity controls
dom.qtyPlus.addEventListener("click", () => {
  if (state.quantity < 20) {
    state.quantity++;
    dom.qtyValue.textContent = state.quantity;
    dom.qtyMinus.disabled = false;
    updatePricingBreakdown();
  }
});

dom.qtyMinus.addEventListener("click", () => {
  if (state.quantity > 1) {
    state.quantity--;
    dom.qtyValue.textContent = state.quantity;
    if (state.quantity === 1) dom.qtyMinus.disabled = true;
    updatePricingBreakdown();
  }
});

// Delivery mode selection
dom.deliveryCards.forEach(card => {
  card.addEventListener("click", () => {
    dom.deliveryCards.forEach(c => c.classList.remove("active"));
    card.classList.add("active");
    const radio = card.querySelector('input[type="radio"]');
    if (radio) radio.checked = true;
    state.deliveryMethod = card.dataset.delivery;

    // Show/hide subfields
    dom.fieldsLocker.style.display = state.deliveryMethod === "locker" ? "block" : "none";
    dom.fieldsHome.style.display = state.deliveryMethod === "home" ? "block" : "none";
    dom.fieldsHand.style.display = state.deliveryMethod === "hand" ? "block" : "none";

    updatePricingBreakdown();
  });
});

// Step navigation
function goToStep(step) {
  if (step === 2) {
    // Validate Step 1
    if (!state.selectedColor || !state.selectedSize) {
      showToast("Seleziona colore e taglia prima di continuare.");
      return;
    }
  } else if (step === 3) {
    // Validate Step 2 inputs
    const name = dom.custName.value.trim();
    const surname = dom.custSurname.value.trim();
    const email = dom.custEmail.value.trim();
    const phone = dom.custPhone.value.trim();

    if (!name || !surname) {
      showToast("Inserisci nome e cognome.");
      dom.custName.focus();
      return;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      showToast("Inserisci un indirizzo email valido.");
      dom.custEmail.focus();
      return;
    }
    const cleanPhone = phone.replace(/[\s\-\+\(\)]/g, "");
    if (!cleanPhone || cleanPhone.length < 6) {
      showToast("Inserisci un recapito telefonico valido.");
      dom.custPhone.focus();
      return;
    }

    // Specific delivery checks
    if (state.deliveryMethod === "locker") {
      const lName = document.getElementById("locker-name").value.trim();
      const lAddr = document.getElementById("locker-address").value.trim();
      const lZip = document.getElementById("locker-zip").value.trim();
      const lCity = document.getElementById("locker-city").value.trim();
      if (!lName || !lAddr || !lZip || !lCity) {
        showToast("Compila tutti i dati del Locker/Punto di ritiro.");
        return;
      }
    } else if (state.deliveryMethod === "home") {
      const hAddr = document.getElementById("home-address").value.trim();
      const hZip = document.getElementById("home-zip").value.trim();
      const hCity = document.getElementById("home-city").value.trim();
      const hProv = document.getElementById("home-province").value.trim();
      if (!hAddr || !hZip || !hCity || !hProv) {
        showToast("Compila tutti i campi dell'indirizzo di spedizione.");
        return;
      }
    } else if (state.deliveryMethod === "hand") {
      const hLoc = document.getElementById("hand-location").value.trim();
      if (!hLoc) {
        showToast("Specifica la località proposta per la consegna a mano.");
        return;
      }
    }

    renderStep3Summary();
  }

  state.currentStep = step;
  
  // Update views
  dom.steps[1].style.display = step === 1 ? "block" : "none";
  dom.steps[2].style.display = step === 2 ? "block" : "none";
  dom.steps[3].style.display = step === 3 ? "block" : "none";
  dom.steps.conf.style.display = step === "conf" ? "block" : "none";

  // Stepper bar
  if (step === "conf") {
    document.getElementById("stepper-nav").style.display = "none";
  } else {
    document.getElementById("stepper-nav").style.display = "flex";
    dom.stepNodes.forEach((node, idx) => {
      const nStep = idx + 1;
      node.classList.remove("active", "completed");
      if (nStep === step) {
        node.classList.add("active");
      } else if (nStep < step) {
        node.classList.add("completed");
      }
    });
    const progressPct = step === 1 ? 0 : (step === 2 ? 50 : 100);
    dom.stepperProgress.style.width = `${progressPct}%`;
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

document.getElementById("go-to-step-2").addEventListener("click", () => goToStep(2));
document.getElementById("back-to-step-1").addEventListener("click", () => goToStep(1));
document.getElementById("go-to-step-3").addEventListener("click", () => goToStep(3));
document.getElementById("back-to-step-2").addEventListener("click", () => goToStep(2));

dom.stepNodes[0].addEventListener("click", () => goToStep(1));
dom.stepNodes[1].addEventListener("click", () => {
  if (state.currentStep > 1) goToStep(2);
});
dom.stepNodes[2].addEventListener("click", () => {
  if (state.currentStep === 2) goToStep(3);
});

// Step 3 Summary Builder & Live Pricing
function updatePricingBreakdown() {
  const shirtPrice = state.config?.shirt_price || 0.0;
  const subtotal = Math.round(shirtPrice * state.quantity * 100) / 100;

  let shippingCost = 0.0;
  if (state.deliveryMethod === "locker") {
    shippingCost = state.config?.shipping_locker || 0.0;
  } else if (state.deliveryMethod === "home") {
    shippingCost = state.config?.shipping_home || 0.0;
  } else if (state.deliveryMethod === "hand") {
    shippingCost = state.config?.shipping_hand || 0.0;
  }

  let discount = state.discountAmount || 0.0;
  discount = Math.min(subtotal, discount);

  const finalTotal = Math.max(0.0, Math.round((subtotal + shippingCost - discount) * 100) / 100);

  // Update DOM in Step 3
  dom.calcQty.textContent = state.quantity;
  dom.calcUnitPrice.textContent = shirtPrice > 0 ? shirtPrice.toFixed(2) : "--";
  dom.calcSubtotal.textContent = shirtPrice > 0 ? subtotal.toFixed(2) + " €" : "-- €";
  dom.calcShipping.textContent = (shippingCost === 0 && state.deliveryMethod === "hand") ? "Gratuita" : (shippingCost.toFixed(2) + " €");

  if (state.discountCode && discount > 0) {
    dom.rowDiscount.style.display = "flex";
    dom.appliedDiscountCode.textContent = state.discountCode;
    dom.calcDiscount.textContent = `- ${discount.toFixed(2)} €`;
  } else {
    dom.rowDiscount.style.display = "none";
  }

  dom.calcFinalTotal.textContent = shirtPrice > 0 ? finalTotal.toFixed(2) + " €" : "-- €";

  return { subtotal, shippingCost, discount, finalTotal, shirtPrice };
}

function renderStep3Summary() {
  const { subtotal } = updatePricingBreakdown();
  const colorLabel = state.selectedColor === "navy" ? "Blu navy" : "Bianca";
  const sizeLabel = state.selectedSize === "XXXL" ? "3XL" : (state.selectedSize === "XXL" ? "2XL" : state.selectedSize);

  dom.summaryProdThumb.src = photoMap[state.selectedColor].front;
  dom.summaryProdDetails.textContent = `${colorLabel} · Taglia ${sizeLabel} · Quantità: ${state.quantity}`;
  dom.summaryProdSubtotal.textContent = state.config?.shirt_price ? `${subtotal.toFixed(2)} €` : "-- €";

  if (state.deliveryMethod === "locker") {
    const lName = document.getElementById("locker-name").value.trim();
    const lAddr = document.getElementById("locker-address").value.trim();
    const lCity = document.getElementById("locker-city").value.trim();
    dom.summaryDeliveryTitle.textContent = "Locker / Punto di ritiro";
    dom.summaryDeliveryDesc.textContent = `${lName} - ${lAddr}, ${lCity}`;
  } else if (state.deliveryMethod === "home") {
    const hAddr = document.getElementById("home-address").value.trim();
    const hCity = document.getElementById("home-city").value.trim();
    const hProv = document.getElementById("home-province").value.trim();
    dom.summaryDeliveryTitle.textContent = "Spedizione a domicilio";
    dom.summaryDeliveryDesc.textContent = `${hAddr}, ${hCity} (${hProv})`;
  } else {
    const hLoc = document.getElementById("hand-location").value.trim();
    dom.summaryDeliveryTitle.textContent = "Consegna a mano";
    dom.summaryDeliveryDesc.textContent = `Località concordata: ${hLoc}`;
  }
}

// Discount Code Validation
dom.btnApplyDiscount.addEventListener("click", async () => {
  const code = dom.discountInput.value.trim().toUpperCase();
  if (!code) {
    showToast("Inserisci un codice promozionale.");
    return;
  }

  if (state.discountCode === code) {
    showToast("Codice già applicato a questo ordine.");
    return;
  }

  dom.btnApplyDiscount.disabled = true;
  dom.btnApplyDiscount.textContent = "Verifica...";

  try {
    const res = await fetch("/api/discounts/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code })
    });
    const data = await res.json();

    if (res.ok && data.valid) {
      state.discountCode = data.code;
      state.discountAmount = data.discount_value;
      dom.discountFeedback.className = "discount-feedback success";
      dom.discountFeedback.textContent = data.message || `Codice applicato! Sconto di ${data.discount_value.toFixed(2)} €`;
      updatePricingBreakdown();
      showToast("Codice sconto attivato!");
    } else {
      state.discountCode = null;
      state.discountAmount = 0.0;
      dom.discountFeedback.className = "discount-feedback error";
      dom.discountFeedback.textContent = data.message || "Codice non valido o scaduto.";
      updatePricingBreakdown();
    }
  } catch (err) {
    dom.discountFeedback.className = "discount-feedback error";
    dom.discountFeedback.textContent = "Errore durante la verifica del codice.";
  } finally {
    dom.btnApplyDiscount.disabled = false;
    dom.btnApplyDiscount.textContent = "Applica";
  }
});

// Order Submission
dom.btnSubmitOrder.addEventListener("click", async () => {
  if (state.orderSubmitting) return;

  // Check config prices
  if (!state.config?.is_configured) {
    showToast("Impossibile procedere: i prezzi ufficiali non sono ancora stati configurati.");
    return;
  }

  // Check privacy consent
  if (!dom.privacyConsent.checked) {
    showToast("Devi accettare l'informativa sulla privacy per procedere.");
    dom.privacyConsent.focus();
    return;
  }

  // Build payload
  const deliveryDetails = {};
  if (state.deliveryMethod === "locker") {
    deliveryDetails.locker_name = document.getElementById("locker-name").value.trim();
    deliveryDetails.address = document.getElementById("locker-address").value.trim();
    deliveryDetails.zip = document.getElementById("locker-zip").value.trim();
    deliveryDetails.city = document.getElementById("locker-city").value.trim();
    deliveryDetails.notes = document.getElementById("locker-notes").value.trim();
  } else if (state.deliveryMethod === "home") {
    deliveryDetails.address = document.getElementById("home-address").value.trim();
    deliveryDetails.zip = document.getElementById("home-zip").value.trim();
    deliveryDetails.city = document.getElementById("home-city").value.trim();
    deliveryDetails.province = document.getElementById("home-province").value.trim();
    deliveryDetails.notes = document.getElementById("home-notes").value.trim();
  } else if (state.deliveryMethod === "hand") {
    deliveryDetails.hand_location = document.getElementById("hand-location").value.trim();
    deliveryDetails.hand_preferences = document.getElementById("hand-preferences").value.trim();
  }

  const payload = {
    customer_first_name: dom.custName.value.trim(),
    customer_last_name: dom.custSurname.value.trim(),
    customer_email: dom.custEmail.value.trim(),
    customer_phone: dom.custPhone.value.trim(),
    color: state.selectedColor,
    size: state.selectedSize,
    quantity: state.quantity,
    delivery_method: state.deliveryMethod,
    delivery_details: deliveryDetails,
    discount_code: state.discountCode,
    privacy_accepted: true
  };

  // Anti-double submission lock
  state.orderSubmitting = true;
  dom.btnSubmitOrder.disabled = true;
  dom.btnSubmitOrder.innerHTML = `Registrazione ordine in corso...`;

  try {
    const res = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (res.ok && data.success) {
      state.orderConfirmedData = data;
      // Update browser URL without reload so user can refresh/bookmark
      const newUrl = `${window.location.origin}/ordine/${data.order_token}`;
      window.history.pushState({ order_token: data.order_token }, "", newUrl);

      renderConfirmationScreen(data);
      goToStep("conf");
      showToast("Ordine registrato con successo!");
    } else {
      showToast(data.message || "Si è verificato un errore durante l'ordine.");
      dom.btnSubmitOrder.disabled = false;
      dom.btnSubmitOrder.textContent = "Conferma Ordine e Procedi al Bonifico";
    }
  } catch (err) {
    console.error(err);
    showToast("Errore di connessione. Controlla la rete e riprova.");
    dom.btnSubmitOrder.disabled = false;
    dom.btnSubmitOrder.textContent = "Conferma Ordine e Procedi al Bonifico";
  } finally {
    state.orderSubmitting = false;
  }
});

// Render Step 4 Confirmation Screen
function renderConfirmationScreen(data) {
  document.getElementById("conf-order-num").textContent = `Ordine ${data.order_number}`;
  document.getElementById("conf-cust-name").textContent = data.customer?.first_name || "";
  
  // Wire instructions
  const amountStr = data.pricing?.total_amount !== undefined ? data.pricing.total_amount.toFixed(2) + " €" : (data.total_amount ? data.total_amount.toFixed(2) + " €" : "-- €");
  document.getElementById("conf-wire-amount").textContent = amountStr;
  
  const holder = data.bank?.holder || "In aggiornamento";
  const iban = data.bank?.iban || "In aggiornamento";
  const bankName = data.bank?.name || "";
  const causale = data.bank?.causale || data.wire_causale || "";

  document.getElementById("conf-wire-holder").textContent = holder;
  document.getElementById("conf-wire-iban").textContent = iban;
  document.getElementById("conf-wire-causale").textContent = causale;

  if (bankName) {
    document.getElementById("conf-wire-bank-row").style.display = "flex";
    document.getElementById("conf-wire-bank").textContent = bankName;
  } else {
    document.getElementById("conf-wire-bank-row").style.display = "none";
  }

  // Summary box
  const colorName = data.product?.color_name || (data.items && data.items[0]?.color_name) || "";
  const size = data.product?.size || (data.items && data.items[0]?.size) || "";
  const qty = data.product?.quantity || (data.items && data.items[0]?.quantity) || 1;

  document.getElementById("conf-color").textContent = colorName;
  document.getElementById("conf-size").textContent = size === "XXXL" ? "3XL" : (size === "XXL" ? "2XL" : size);
  document.getElementById("conf-qty").textContent = qty;
  
  let deliveryStr = "";
  if (data.delivery?.method === "locker") {
    deliveryStr = `Locker: ${data.delivery.locker_name} (${data.delivery.address}, ${data.delivery.city})`;
  } else if (data.delivery?.method === "home") {
    deliveryStr = `Domicilio: ${data.delivery.address}, ${data.delivery.city} (${data.delivery.province})`;
  } else {
    deliveryStr = `A mano: ${data.delivery?.hand_location || ""}`;
  }
  document.getElementById("conf-delivery").textContent = deliveryStr;
  document.getElementById("conf-customer").textContent = `${data.customer?.first_name} ${data.customer?.last_name}`;
  document.getElementById("conf-contacts").textContent = `${data.customer?.email} · ${data.customer?.phone}`;

  initCopyButtons();
}

// Deep linking: check if path is /ordine/{token} or query has ?token=...
async function checkUrlForOrderToken() {
  let token = null;
  const pathParts = window.location.pathname.split("/ordine/");
  if (pathParts.length > 1 && pathParts[1].trim()) {
    token = pathParts[1].trim();
  } else {
    const params = new URLSearchParams(window.location.search);
    if (params.get("token")) {
      token = params.get("token");
    }
  }

  if (token) {
    try {
      const res = await fetch(`/api/orders/token/${token}`);
      const data = await res.json();
      if (res.ok && data.order) {
        state.orderConfirmedData = data.order;
        renderConfirmationScreen({
          order_number: data.order.order_number,
          wire_causale: data.order.wire_causale,
          pricing: { total_amount: data.order.total_amount },
          bank: {
            holder: data.order.bank_holder,
            iban: data.order.bank_iban,
            name: data.order.bank_name,
            causale: data.order.wire_causale
          },
          customer: {
            first_name: data.order.customer_first_name,
            last_name: data.order.customer_last_name,
            email: data.order.customer_email,
            phone: data.order.customer_phone
          },
          items: data.order.items,
          delivery: {
            method: data.order.delivery_method,
            locker_name: data.order.locker_name,
            address: data.order.delivery_address,
            city: data.order.delivery_city,
            province: data.order.delivery_province,
            hand_location: data.order.hand_location
          }
        });
        goToStep("conf");
      }
    } catch (e) {
      console.warn("Could not load token order:", e);
    }
  }
}

// Size guide modal controls
dom.openSizeModal.addEventListener("click", () => dom.sizeModal.showModal());
dom.closeSizeModal.addEventListener("click", () => dom.sizeModal.close());
dom.btnSizeDone.addEventListener("click", () => dom.sizeModal.close());
dom.sizeModal.addEventListener("click", (e) => {
  if (e.target === dom.sizeModal) dom.sizeModal.close();
});

// Boot
window.addEventListener("DOMContentLoaded", () => {
  initApp();
  initCopyButtons();
});
