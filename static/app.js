(() => {
  // Light/Dark toggle
  const root = document.documentElement;
  const themeToggle = document.getElementById('themeToggle');

  function applyTheme(theme){
    // theme: 'dark' | 'light'
    if(theme === 'light'){
      document.documentElement.setAttribute('data-theme', 'light');
      localStorage.setItem('theme','light');
    }else{
      document.documentElement.removeAttribute('data-theme');
      localStorage.setItem('theme','dark');
    }
  }


  const savedTheme = localStorage.getItem('theme') || 'dark';
  applyTheme(savedTheme);

  if(themeToggle){
    themeToggle.addEventListener('click', ()=>{
      const cur = localStorage.getItem('theme') || 'dark';
      const next = cur === 'light' ? 'dark' : 'light';
      applyTheme(next);
    });
  }

  // Sidebar toggle
  const sidebar = document.getElementById('sidebar');

  const main = document.getElementById('main');
  const toggleBtn = document.getElementById('toggleSidebar');
  if (toggleBtn && sidebar && main) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
      main.classList.toggle('expanded');
    });
  }

  // Toast notifications
  const toastContainer = document.getElementById('toastContainer');

  function toast(message, type = 'success') {
    if (!toastContainer) return;
    const el = document.createElement('div');
    el.className = `toast toast-${type}`;
    el.innerHTML = `
      <div class="toast-icon">${type === 'success' ? '✅' : type === 'error' ? '❌' : type === 'warning' ? '⚠️' : 'ℹ️'}</div>
      <div class="toast-body">
        <div class="toast-title">${type.toUpperCase()}</div>
        <div class="toast-msg">${message}</div>
      </div>
      <button class="toast-close" aria-label="Close">✕</button>
    `;
    toastContainer.appendChild(el);

    requestAnimationFrame(() => el.classList.add('show'));

    const close = () => {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 220);
    };

    el.querySelector('.toast-close')?.addEventListener('click', close);
    setTimeout(close, 3600);
  }

  // Convert Flask flash messages into toasts
  const flashContainer = document.getElementById('flashContainer');
  if (flashContainer) {
    const flashes = flashContainer.querySelectorAll('.flash');
    flashes.forEach((node) => {
      const type = node.getAttribute('data-flash') || 'info';
      toast(node.textContent.trim(), type === 'error' ? 'error' : (type === 'success' ? 'success' : 'warning'));
    });
  }

  // Low stock toasts on dashboard
  const lowStock = (() => {
    // Backward-compatible: support both old window variable and new JSON script tag.
    if (window.__LOW_STOCK__) return window.__LOW_STOCK__;
    const node = document.getElementById('lowStockData');
    if (!node) return [];
    try {
      return JSON.parse(node.textContent || '[]');
    } catch (e) {
      return [];
    }
  })();

  if (Array.isArray(lowStock) && lowStock.length) {
    // Small delay so page feels smooth
    setTimeout(() => {
      lowStock.slice(0, 3).forEach((item, idx) => {
        setTimeout(() => {
          toast(`${item.name}: Only ${item.stock} units left.`, 'warning');
        }, idx * 450);
      });
    }, 600);
  }

  // Animate elements
  const animEls = document.querySelectorAll('[data-animate]');
  if (animEls.length) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add('in-view');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12 });

    animEls.forEach((el) => io.observe(el));
  }

  // Stock page features (filtering)
  const filterInput = document.getElementById('filterInput');
  const productsTable = document.getElementById('productsTable');
  if (filterInput && productsTable) {
    filterInput.addEventListener('input', () => {
      const q = filterInput.value.toLowerCase().trim();
      const rows = productsTable.querySelectorAll('tbody tr');
      rows.forEach((r) => {
        const text = r.textContent.toLowerCase();
        r.style.display = (!q || text.includes(q)) ? '' : 'none';
      });
    });
  }
  // Sales entry live price calculation
  const productSelect = document.getElementById('product_id');
  const quantityInput = document.getElementById('quantity');
  const unitPriceView = document.getElementById('unit_price_view');
  const totalPriceView = document.getElementById('total_price_view');
  const unitPriceHidden = document.getElementById('unit_price');
  const totalPriceHidden = document.getElementById('total_price');
  const stockNote = document.getElementById('stockNote');

  if (productSelect && quantityInput && unitPriceView && totalPriceView && unitPriceHidden && totalPriceHidden) {
    const fmtMoney = (n) => {
      const num = Number(n);
      return (Number.isFinite(num) ? num : 0).toFixed(2);
    };

    const readUnitPrice = () => {
      const opt = productSelect.options[productSelect.selectedIndex];
      if (!opt) return 0;
      const p = opt.getAttribute('data-price');
      const v = parseFloat(p);
      return Number.isFinite(v) ? v : 0;
    };

    const readStock = () => {
      const opt = productSelect.options[productSelect.selectedIndex];
      if (!opt) return null;
      const s = opt.getAttribute('data-stock');
      const v = parseInt(s, 10);
      return Number.isFinite(v) ? v : null;
    };

    const bump = (el) => {
      if (!el) return;
      el.classList.remove('price-updated');
      // force reflow
      // eslint-disable-next-line no-unused-expressions
      el.offsetHeight;
      el.classList.add('price-updated');
    };

    const recalc = () => {
      const unitPrice = readUnitPrice();
      const qty = Math.max(0, parseInt(quantityInput.value || '0', 10));

      const total = unitPrice * qty;

      unitPriceView.value = fmtMoney(unitPrice);
      totalPriceView.value = fmtMoney(total);

      unitPriceHidden.value = String(unitPrice);
      totalPriceHidden.value = String(total);

      bump(unitPriceView);
      bump(totalPriceView);

      const stock = readStock();
      if (stockNote) {
        if (stock === null) {
          stockNote.textContent = '';
        } else {
          stockNote.textContent = qty > stock
            ? `⚠️ Requested quantity (${qty}) exceeds available stock (${stock}).`
            : `Available stock: ${stock} units.`;
        }
      }
    };

    productSelect.addEventListener('change', recalc);
    quantityInput.addEventListener('input', () => {
      // Clamp to min 1 if user clears
      if (!quantityInput.value) {
        quantityInput.value = '';
      }
      recalc();
    });

    // initial paint
    recalc();
  }
})();











