/* ====== DermaSense AI — Script ====== */

// App state
let state = {
  skintype: null,
  fitz: null,
  concerns: [],
  severity: null,
  step: 1
};

// Navigation between main pages
function showPage(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + page).classList.add('active');
  document.querySelectorAll('.nav-links a').forEach(a => a.classList.remove('active'));
  const navEl = document.getElementById('nav-' + page);
  if (navEl) navEl.classList.add('active');
  window.scrollTo(0, 0);
}

// Quiz step navigation
function goStep(n) {
  document.querySelectorAll('.quiz-step').forEach(s => s.classList.remove('active'));
  document.getElementById('step-' + n).classList.add('active');
  state.step = n;
  const pct = Math.round((n / 6) * 100);
  document.getElementById('progress-fill').style.width = pct + '%';
  document.getElementById('progress-label').textContent = 'Step ' + n + ' of 6';
}

// Single-select option button
function selectOption(el, key, val) {
  el.closest('.option-grid').querySelectorAll('.option-btn').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  state[key] = val;
}

// Multi-select concerns
function toggleConcern(el, val) {
  el.classList.toggle('selected');
  if (el.classList.contains('selected')) {
    if (!state.concerns.includes(val)) state.concerns.push(val);
  } else {
    state.concerns = state.concerns.filter(c => c !== val);
  }
}

// Fitzpatrick skin type
function selectFitz(el, val) {
  document.querySelectorAll('.fitz-btn').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  state.fitz = val;
}

// Severity / grouped radio buttons
function selectSeverity(el, val, group) {
  el.closest('.severity-row').querySelectorAll('.severity-btn').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  if (!group || group === 'main') state.severity = val;
}

// Slider labels
function updateSlider(outId, val, labels) {
  document.getElementById(outId).textContent = labels[parseInt(val) - 1];
}

function updateSleep(val) {
  document.getElementById('sleep-out').textContent = val + ' hrs';
}

// Photo preview
function previewPhoto(input) {
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = e => {
      document.getElementById('preview-img').src = e.target.result;
      document.getElementById('photo-preview').style.display = 'block';
    };
    reader.readAsDataURL(input.files[0]);
  }
}

// Generate results with loading animation
function generateResults() {
  const overlay = document.getElementById('loading-overlay');
  overlay.classList.add('active');
  setTimeout(() => {
    overlay.classList.remove('active');
    populateResults();
    showPage('results');
  }, 2200);
}

function populateResults() {
  const skintypeMap = {
    oily: 'Oily', dry: 'Dry', combination: 'Combination',
    sensitive: 'Sensitive', normal: 'Normal', acne: 'Acne-prone'
  };
  document.getElementById('res-skintype').textContent = skintypeMap[state.skintype] || 'Combination';
  document.getElementById('res-fitz').textContent = state.fitz ? 'Type ' + state.fitz : 'Type III';
  document.getElementById('res-concern').textContent = state.concerns.length > 0
    ? state.concerns.slice(0, 2).map(c => c.charAt(0).toUpperCase() + c.slice(1)).join(' + ')
    : 'Acne + Pigmentation';
  document.getElementById('res-severity').textContent = state.severity
    ? state.severity.charAt(0).toUpperCase() + state.severity.slice(1)
    : 'Moderate';
}

// Products data
const products = [
  { name: 'The Ordinary Niacinamide 10% + Zinc 1%', brand: 'The Ordinary', tier: 'affordable', tierlabel: 'Affordable', icon: '🧴', actives: ['Niacinamide 10%', 'Zinc 1%'], price: '$6', badge: 'Best Seller', concern: ['acne','pigmentation'] },
  { name: "Paula's Choice BHA 2% Liquid", brand: "Paula's Choice", tier: 'mid', tierlabel: 'Mid-range', icon: '🫙', actives: ['Salicylic Acid 2%'], price: '$34', badge: "Editor's Pick", concern: ['acne'] },
  { name: 'SkinCeuticals C E Ferulic', brand: 'SkinCeuticals', tier: 'luxury', tierlabel: 'Luxury', icon: '💛', actives: ['Vitamin C 15%', 'Vitamin E', 'Ferulic Acid'], price: '$182', badge: 'Clinical Grade', concern: ['pigmentation','aging'] },
  { name: 'CeraVe Moisturising Cream', brand: 'CeraVe', tier: 'affordable', tierlabel: 'Affordable', icon: '🤍', actives: ['Ceramides', 'Hyaluronic Acid', 'Niacinamide'], price: '$18', badge: 'Dermatologist Rec.', concern: ['hydration'] },
  { name: 'Differin Adapalene Gel 0.1%', brand: 'Differin', tier: 'affordable', tierlabel: 'Affordable', icon: '💊', actives: ['Adapalene 0.1%'], price: '$15', badge: 'OTC Retinoid', concern: ['acne','aging'] },
  { name: 'La Roche-Posay Effaclar Serum', brand: 'La Roche-Posay', tier: 'mid', tierlabel: 'Mid-range', icon: '🔵', actives: ['Glycolic Acid', 'Salicylic Acid', 'LHA'], price: '$40', badge: 'Dermatologist Rec.', concern: ['acne','pigmentation'] },
  { name: 'The INKEY List Retinol Serum', brand: 'The INKEY List', tier: 'affordable', tierlabel: 'Affordable', icon: '🟡', actives: ['Retinol 1%', 'Granactive Retinoid 0.5%'], price: '$11', badge: 'Beginner Friendly', concern: ['aging','acne'] },
  { name: 'Skinceuticals Phyto Corrective', brand: 'SkinCeuticals', tier: 'luxury', tierlabel: 'Luxury', icon: '🌿', actives: ['Thymol', 'Turmeric', 'Hyaluronic Acid'], price: '$98', badge: 'Calming', concern: ['hydration','pigmentation'] },
  { name: 'EltaMD UV Clear SPF 46', brand: 'EltaMD', tier: 'mid', tierlabel: 'Mid-range', icon: '🌤️', actives: ['Zinc Oxide 9%', 'Niacinamide'], price: '$45', badge: 'Non-comedogenic', concern: ['acne'] }
];

function renderProducts(list) {
  const grid = document.getElementById('product-grid');
  grid.innerHTML = list.map(p => `
    <div class="product-card">
      <div class="product-img-wrap" style="background:var(--cream);">${p.icon}</div>
      <div class="product-body">
        <div class="product-tier ${p.tier}">${p.tierlabel}</div>
        <div class="product-name">${p.name}</div>
        <div class="product-brand">${p.brand}</div>
        <div class="product-actives">
          ${p.actives.map(a => `<span class="active-pill">${a}</span>`).join('')}
        </div>
      </div>
      <div class="product-footer">
        <span class="product-price">${p.price}</span>
        <span class="product-badge">${p.badge}</span>
      </div>
    </div>
  `).join('');
}

function filterProducts() {
  const selects = document.querySelectorAll('.filter-select');
  const concern = selects[0] ? selects[0].value : 'all';
  const budget = selects[1] ? selects[1].value : 'all';

  let filtered = products.slice();
  if (concern !== 'all') {
    filtered = filtered.filter(p => p.concern.includes(concern));
  }
  if (budget !== 'all') {
    filtered = filtered.filter(p => p.tier === budget);
  }
  renderProducts(filtered);
}

// Education tabs
function switchEduTab(el, id) {
  document.querySelectorAll('.edu-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.edu-content').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('edu-' + id).classList.add('active');
}

// Init on page load
document.addEventListener('DOMContentLoaded', () => {
  renderProducts(products);
});
