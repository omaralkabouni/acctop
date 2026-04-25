// ERP TOP — Global JavaScript
'use strict';

// Flash auto-dismiss
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.alert[data-auto-dismiss]').forEach(el => {
    setTimeout(() => el.style.opacity = '0', 3500);
    setTimeout(() => el.remove(), 4000);
  });

  // Mobile sidebar toggle
  const menuBtn = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (menuBtn && sidebar) {
    menuBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
      document.body.classList.toggle('sidebar-open');
    });
    document.addEventListener('click', e => {
      if (!sidebar.contains(e.target) && !menuBtn.contains(e.target)) {
        sidebar.classList.remove('open');
        document.body.classList.remove('sidebar-open');
      }
    });
  }

  // Confirm modals (using custom application modal)
  document.querySelectorAll('[data-confirm]').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      const message = el.dataset.confirm || 'هل أنت متأكد من هذا الإجراء؟';
      
      showConfirm(message, () => {
        // If it's a button inside a form, submit the form
        const form = el.closest('form');
        if (form) {
          form.submit();
        } else if (el.tagName === 'A') {
          // If it's a link, follow the link
          window.location.href = el.href;
        }
      });
    });
  });

  // Modal open/close
  document.querySelectorAll('[data-modal-open]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = document.getElementById(btn.dataset.modalOpen);
      if (modal) modal.classList.add('open');
    });
  });
  document.querySelectorAll('[data-modal-close], .modal-overlay').forEach(el => {
    el.addEventListener('click', e => {
      if (e.target === el) el.closest('.modal-overlay')?.classList.remove('open');
    });
  });

  // Number formatting on blur
  document.querySelectorAll('input[data-currency]').forEach(input => {
    input.addEventListener('blur', () => {
      const val = parseFloat(input.value.replace(/,/g, ''));
      if (!isNaN(val)) input.value = parseFloat(val.toFixed(2));
    });
  });

  // Initialize Tom Select for searchable dropdowns
  document.querySelectorAll('select.searchable-select').forEach(select => {
    new TomSelect(select, {
      create: false,
      sortField: { field: "text", direction: "asc" }
    });
  });
});

// Invoice line items
const InvoiceForm = {
  lineCount: 0,

  addLine(productId = '', productName = '', unitPrice = 0) {
    const tbody = document.getElementById('invoice-lines-body');
    if (!tbody) return;
    const idx = this.lineCount++;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>
        <select name="product_id[]" class="form-control" style="min-width:140px" onchange="InvoiceForm.onProductChange(this, ${idx})">
          <option value="">-- اختر منتجاً --</option>
          ${window.__products?.map(p => `<option value="${p.id}" data-price="${p.unit_price}" ${p.id==productId?'selected':''}>${p.name_ar||p.name}</option>`).join('')||''}
        </select>
      </td>
      <td><input type="text" name="description[]" class="form-control" value="${productName}" placeholder="الوصف" required style="min-width:160px"/></td>
      <td><input type="number" name="qty[]" class="form-control num" value="1" min="0.001" step="any" onchange="InvoiceForm.calcLine(${idx})" style="width:80px"/></td>
      <td><input type="number" name="unit_price[]" id="price_${idx}" class="form-control num" value="${unitPrice}" min="0" step="any" onchange="InvoiceForm.calcLine(${idx})" style="width:110px"/></td>
      <td><input type="number" name="line_discount[]" class="form-control num" value="0" min="0" max="100" step="any" onchange="InvoiceForm.calcLine(${idx})" style="width:70px"/></td>
      <td class="num line-total" id="linetotal_${idx}">0.00</td>
      <td><button type="button" class="btn btn-icon" style="color:var(--error)" onclick="this.closest('tr').remove();InvoiceForm.updateTotals()">
        <span class="material-symbols-outlined" style="font-size:18px">delete</span></button></td>`;
    tbody.appendChild(tr);
    this.calcLine(idx);
  },

  onProductChange(sel, idx) {
    const opt = sel.options[sel.selectedIndex];
    const price = parseFloat(opt.dataset.price || 0);
    const desc = opt.text !== '-- اختر منتجاً --' ? opt.text : '';
    const row = sel.closest('tr');
    row.querySelector('input[name="description[]"]').value = desc;
    document.getElementById(`price_${idx}`).value = parseFloat(price.toFixed(2));
    this.calcLine(idx);
  },

  calcLine(idx) {
    const row = document.getElementById(`linetotal_${idx}`)?.closest('tr');
    if (!row) return;
    const qty = parseFloat(row.querySelector('input[name="qty[]"]').value) || 0;
    const price = parseFloat(row.querySelector('input[name="unit_price[]"]').value) || 0;
    const disc = parseFloat(row.querySelector('input[name="line_discount[]"]').value) || 0;
    const total = qty * price * (1 - disc / 100);
    const el = document.getElementById(`linetotal_${idx}`);
    if (el) el.textContent = parseFloat(total.toFixed(2));
    this.updateTotals();
  },

  updateTotals() {
    let subtotal = 0;
    document.querySelectorAll('.line-total').forEach(el => {
      subtotal += parseFloat(el.textContent) || 0;
    });
    const discPct = parseFloat(document.getElementById('discount_pct')?.value) || 0;
    const taxRate = parseFloat(document.getElementById('tax_rate')?.value) || 0;
    const discAmt = subtotal * discPct / 100;
    const taxable = subtotal - discAmt;
    const taxAmt = taxable * taxRate / 100;
    const total = taxable + taxAmt;

    const set = (id, v) => { 
      const el = document.getElementById(id); 
      if (el) el.textContent = parseFloat(v.toFixed(2)).toLocaleString(); 
    };
    set('summary-subtotal', subtotal);
    set('summary-discount', discAmt);
    set('summary-tax', taxAmt);
    set('summary-total', total);
  }
};

// Charts helper
function createAreaChart(canvasId, labels, datasets) {
  const ctx = document.getElementById(canvasId)?.getContext('2d');
  if (!ctx) return;
  return new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { rtl: true, bodyFont: { family: 'Tajawal' }, titleFont: { family: 'Tajawal' } } },
      scales: {
        x: { grid: { display: false }, ticks: { font: { family: 'Tajawal', size: 12 }, color: '#76777d' } },
        y: { grid: { color: '#f1f5f9' }, ticks: { font: { family: 'Inter', size: 11 }, color: '#76777d', callback: v => v.toLocaleString() } }
      }
    }
  });
}

function createDoughnutChart(canvasId, labels, data, colors) {
  const ctx = document.getElementById(canvasId)?.getContext('2d');
  if (!ctx) return;
  return new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data, backgroundColor: colors, borderWidth: 0, hoverOffset: 6 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '70%',
      plugins: { legend: { display: false }, tooltip: { rtl: true, bodyFont: { family: 'Tajawal' } } }
    }
  });
}

function createBarChart(canvasId, labels, data, color = '#10b981') {
  const ctx = document.getElementById(canvasId)?.getContext('2d');
  if (!ctx) return;
  return new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets: [{ data, backgroundColor: color, borderRadius: 6 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { rtl: true, bodyFont: { family: 'Tajawal' } } },
      scales: { x: { grid: { display: false } }, y: { grid: { color: '#f1f5f9' } } }
    }
  });
}
