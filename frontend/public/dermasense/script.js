/* ====== DermaSense AI — Script ====== */

// Backend URL resolution.
// When hosted behind the preview ingress, "/api" on same origin is routed to the backend.
// If the student opens this file via file://, edit API_BASE to point to their backend.
const API_BASE = (() => {
  try {
    if (window.location.protocol === "file:") return "http://localhost:8001";
    return window.location.origin;
  } catch (_) {
    return "";
  }
})();

// App state — collected across the 6-step quiz
let state = {
  skintype: null,
  fitz: null,
  concerns: [],
  severity: null,
  sun: "Moderate",
  sleep: 7,
  stress: null,
  diet: "Balanced (fruits, veggies, lean protein)",
  cleanser: "",
  currentActives: [],
  allergies: "",
  pregnancy: null,
  image: null,
  step: 1,
};

let analysisResult = null; // latest AI analysis payload
let amazonProducts = []; // latest Amazon products

/* ---------- Navigation ---------- */
function showPage(page) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.getElementById("page-" + page).classList.add("active");
  document.querySelectorAll(".nav-links a").forEach((a) => a.classList.remove("active"));
  const navEl = document.getElementById("nav-" + page);
  if (navEl) navEl.classList.add("active");
  window.scrollTo(0, 0);
}

function goStep(n) {
  document.querySelectorAll(".quiz-step").forEach((s) => s.classList.remove("active"));
  document.getElementById("step-" + n).classList.add("active");
  state.step = n;
  const pct = Math.round((n / 6) * 100);
  document.getElementById("progress-fill").style.width = pct + "%";
  document.getElementById("progress-label").textContent = "Step " + n + " of 6";
}

/* ---------- Quiz interactions ---------- */
function selectOption(el, key, val) {
  el.closest(".option-grid").querySelectorAll(".option-btn").forEach((b) => b.classList.remove("selected"));
  el.classList.add("selected");
  state[key] = val;
}

function toggleConcern(el, val) {
  el.classList.toggle("selected");
  if (el.classList.contains("selected")) {
    if (!state.concerns.includes(val)) state.concerns.push(val);
  } else {
    state.concerns = state.concerns.filter((c) => c !== val);
  }
}

function toggleActive(el, val) {
  el.classList.toggle("selected");
  if (el.classList.contains("selected")) {
    if (!state.currentActives.includes(val)) state.currentActives.push(val);
  } else {
    state.currentActives = state.currentActives.filter((c) => c !== val);
  }
}

function selectFitz(el, val) {
  document.querySelectorAll(".fitz-btn").forEach((b) => b.classList.remove("selected"));
  el.classList.add("selected");
  state.fitz = val;
}

function selectSeverity(el, val, group) {
  el.closest(".severity-row").querySelectorAll(".severity-btn").forEach((b) => b.classList.remove("selected"));
  el.classList.add("selected");
  if (!group || group === "main") state.severity = val;
  else if (group === "stress") state.stress = val;
  else if (group === "preg") state.pregnancy = val;
}

function updateSlider(outId, val, labels) {
  const label = labels[parseInt(val) - 1];
  document.getElementById(outId).textContent = label;
  state.sun = label;
}

function updateSleep(val) {
  document.getElementById("sleep-out").textContent = val + " hrs";
  state.sleep = parseFloat(val);
}

function updateDiet(val) {
  state.diet = val;
}

function updateCleanser(val) {
  state.cleanser = val;
}

function updateAllergies(val) {
  state.allergies = val;
}

/* ---------- Photo upload ---------- */
function previewPhoto(input) {
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target.result;
      document.getElementById("preview-img").src = dataUrl;
      document.getElementById("photo-preview").style.display = "block";
      state.image = dataUrl;
    };
    reader.readAsDataURL(input.files[0]);
  }
}

/* ---------- Analysis (calls backend) ---------- */
async function generateResults() {
  const overlay = document.getElementById("loading-overlay");
  const loadingTextEl = overlay.querySelector(".loading-text");
  const loadingSubEl = overlay.querySelector(".loading-sub");
  loadingTextEl.textContent = "Analyzing your skin profile…";
  loadingSubEl.textContent = "Applying dermatological algorithms · Matching cosmeceutical science";
  overlay.classList.add("active");

  try {
    const payload = {
      skintype: state.skintype,
      fitz: state.fitz,
      concerns: state.concerns,
      severity: state.severity,
      sun: state.sun,
      sleep: state.sleep,
      stress: state.stress,
      diet: state.diet,
      cleanser: state.cleanser,
      currentActives: state.currentActives,
      allergies: state.allergies,
      pregnancy: state.pregnancy,
      image: state.image,
    };
    const res = await fetch(`${API_BASE}/api/analyze-skin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("analysis_failed");
    analysisResult = await res.json();
  } catch (err) {
    console.error("Analysis failed:", err);
    analysisResult = null;
  }

  overlay.classList.remove("active");
  renderResults();
  showPage("results");

  // Kick off Amazon search in background
  if (analysisResult && analysisResult.productQueries && analysisResult.productQueries.length) {
    loadAmazonProducts(analysisResult.productQueries);
  }
}

/* ---------- Render results ---------- */
function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderResults() {
  const r = analysisResult;

  // Profile stats
  document.getElementById("res-skintype").textContent = (r && r.skinType) || "Combination";
  document.getElementById("res-fitz").textContent = (r && r.fitzpatrick) || "Type III";
  document.getElementById("res-concern").textContent = (r && r.primaryConcern) || "Acne + Pigmentation";
  document.getElementById("res-severity").textContent = (r && r.severity) || "Moderate";
  document.getElementById("res-uv").textContent = (r && r.uvRisk) || "Moderate";

  // Photo insights (optional)
  const insightsEl = document.getElementById("photo-insights-box");
  if (r && r.photoInsights) {
    insightsEl.style.display = "flex";
    insightsEl.querySelector("p").innerHTML =
      "<strong>AI photo observations:</strong> " + escapeHtml(r.photoInsights);
  } else {
    insightsEl.style.display = "none";
  }

  // Actives list
  const activesHost = document.getElementById("actives-list");
  const actives = (r && r.actives) || [];
  activesHost.innerHTML = actives
    .map(
      (a) => `
        <div class="ingredient-tag">
          <span class="ing-name">${escapeHtml(a.name)}</span>
          <span class="ing-conc">${escapeHtml(a.concentration || "")}${a.format ? " · " + escapeHtml(a.format) : ""}</span>
          <span class="ing-moa">${escapeHtml(a.moa || "")}</span>
        </div>`
    )
    .join("");

  // Contraindications
  const contraEl = document.getElementById("contra-box");
  if (r && r.contraindications) {
    contraEl.style.display = "flex";
    contraEl.querySelector("p").innerHTML =
      "<strong>Contraindications noted:</strong> " + escapeHtml(r.contraindications);
  } else {
    contraEl.style.display = "none";
  }

  // AM/PM routines
  function renderRoutine(list) {
    return (list || [])
      .map(
        (s) => `
          <div class="routine-step">
            <div class="step-card">
              <div class="step-name">${escapeHtml(s.step)}</div>
              <div class="step-product">${escapeHtml(s.product || "")}</div>
              <div class="step-note">${escapeHtml(s.note || "")}</div>
            </div>
          </div>`
      )
      .join("");
  }
  document.getElementById("am-routine").innerHTML = renderRoutine(r && r.amRoutine);
  document.getElementById("pm-routine").innerHTML = renderRoutine(r && r.pmRoutine);

  // Incompatibilities
  const incompHost = document.getElementById("incompatibilities");
  const incomp = (r && r.incompatibilities) || [];
  incompHost.innerHTML = incomp
    .map(
      (txt) => `
        <div class="incompatible-row">
          <span>⛔</span>
          <span>${escapeHtml(txt)}</span>
        </div>`
    )
    .join("");

  // Source tag
  const srcEl = document.getElementById("source-tag");
  if (srcEl && r && r._source) {
    let label = "AI analysis";
    if (r._source.includes("siliconflow")) label = "Powered by GPT OSS 120B";
    else if (r._source.includes("vision")) label = "Powered by Gemini 2.5 Flash (Vision)";
    else if (r._source.includes("openrouter")) label = "Powered by Gemini 2.5 Flash";
    else if (r._source === "fallback") label = "Default recommendations (add API keys to enable AI)";
    srcEl.textContent = label;
  }
}

/* ---------- Amazon product loading ---------- */
async function loadAmazonProducts(queries) {
  const grid = document.getElementById("product-grid");
  if (!grid) return;
  grid.innerHTML = renderSkeletonCards(Math.min(queries.length, 9));

  try {
    const res = await fetch(`${API_BASE}/api/products-search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ queries }),
    });
    const data = await res.json();
    amazonProducts = data.products || [];
  } catch (e) {
    console.error("Amazon search failed:", e);
    amazonProducts = [];
  }

  if (amazonProducts.length === 0) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">🔑</div>
        <h3>Live product data unavailable</h3>
        <p>Add your <code>OPENWEB_NINJA_API_KEY</code> to the backend <code>.env</code> file to fetch real-time prices from Amazon.in.</p>
      </div>`;
    return;
  }
  renderProducts(amazonProducts);
}

function renderSkeletonCards(n) {
  let out = "";
  for (let i = 0; i < n; i++) {
    out += `
      <div class="product-card skeleton-card">
        <div class="product-img-wrap skeleton-shine"></div>
        <div class="product-body">
          <div class="skel-line short"></div>
          <div class="skel-line"></div>
          <div class="skel-line"></div>
          <div class="skel-line short"></div>
        </div>
      </div>`;
  }
  return out;
}

function renderProducts(list) {
  const grid = document.getElementById("product-grid");
  if (!list.length) {
    grid.innerHTML = `<div class="empty-state"><p>No matching products found.</p></div>`;
    return;
  }
  grid.innerHTML = list
    .map((p) => {
      const imgContent = p.image
        ? `<img src="${escapeHtml(p.image)}" alt="${escapeHtml(p.name)}" loading="lazy">`
        : `<span class="img-fallback">${escapeHtml(p.icon || "✨")}</span>`;
      const rating = p.rating
        ? `<span class="product-rating">★ ${escapeHtml(p.rating)}${p.reviews ? ` · ${escapeHtml(p.reviews)} reviews` : ""}</span>`
        : "";
      const link = p.url
        ? `<a class="product-link" href="${escapeHtml(p.url)}" target="_blank" rel="noopener noreferrer">View on Amazon →</a>`
        : "";
      return `
        <div class="product-card" data-tier="${escapeHtml(p.tier)}">
          <div class="product-img-wrap">${imgContent}</div>
          <div class="product-body">
            <div class="product-tier ${escapeHtml(p.tier)}">${escapeHtml(p.tierlabel)}</div>
            <div class="product-name">${escapeHtml(p.name)}</div>
            <div class="product-brand">${escapeHtml(p.brand || "")}</div>
            ${rating}
          </div>
          <div class="product-footer">
            <span class="product-price">${escapeHtml(p.price)}</span>
            <span class="product-badge">${escapeHtml(p.badge || "Amazon.in")}</span>
          </div>
          ${link ? `<div class="product-cta-row">${link}</div>` : ""}
        </div>`;
    })
    .join("");
}

function filterProducts() {
  const selects = document.querySelectorAll(".filter-select");
  const budget = selects[1] ? selects[1].value : "all";
  let filtered = amazonProducts.slice();
  if (budget !== "all") {
    filtered = filtered.filter((p) => p.tier === budget);
  }
  renderProducts(filtered);
}

/* ---------- Education tabs ---------- */
function switchEduTab(el, id) {
  document.querySelectorAll(".edu-tab").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".edu-content").forEach((c) => c.classList.remove("active"));
  el.classList.add("active");
  document.getElementById("edu-" + id).classList.add("active");
}

/* ---------- Empty state on products page ---------- */
function renderEmptyProductsInitial() {
  const grid = document.getElementById("product-grid");
  if (!grid) return;
  grid.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">🔍</div>
      <h3>Complete your skin analysis first</h3>
      <p>Take the quick 6-step quiz to generate personalized product recommendations from Amazon India.</p>
      <button class="btn-primary" onclick="showPage('quiz')">Start Skin Analysis →</button>
    </div>`;
}

document.addEventListener("DOMContentLoaded", () => {
  renderEmptyProductsInitial();
});
