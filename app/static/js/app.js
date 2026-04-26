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

  addLine(productId = '', productName = '', unitPrice = 0, qty = 1, discount = 0, sellingPrice = 0) {
    const tbody = document.getElementById('invoice-lines-body');
    if (!tbody) return;
    const idx = this.lineCount++;
    
    // Check if we should show selling price (usually only for purchases)
    const showSelling = !!document.querySelector('.invoice-lines-table th.col-selling');
    let sellingHtml = '';
    if (showSelling) {
      // Find the selling price if not provided
      if (!sellingPrice && productId) {
        const p = window.__products.find(p => p.id == productId);
        if (p) sellingPrice = p.selling_price || 0;
      }
      sellingHtml = `<td><input type="number" name="selling_price[]" class="form-control num" value="${sellingPrice}" min="0" step="any" style="width:100px" placeholder="سعر البيع"/></td>`;
    }

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>
        <select name="product_id[]" class="form-control searchable-product-select" style="min-width:140px">
          <option value="">-- اختر منتجاً --</option>
          ${window.__products?.map(p => `<option value="${p.id}" data-price="${p.unit_price}" data-selling="${p.selling_price||0}" ${p.id==productId?'selected':''}>${p.name_ar||p.name}</option>`).join('')||''}
        </select>
      </td>
      <td><input type="text" name="description[]" class="form-control" value="${productName}" placeholder="الوصف" required style="min-width:160px"/></td>
      <td><input type="number" name="qty[]" class="form-control num" value="${qty}" min="0.001" step="any" onchange="InvoiceForm.calcLine(${idx})" style="width:80px"/></td>
      <td><input type="number" name="unit_price[]" id="price_${idx}" class="form-control num" value="${unitPrice}" min="0" step="any" onchange="InvoiceForm.calcLine(${idx})" style="width:110px"/></td>
      ${sellingHtml}
      <td><input type="number" name="line_discount[]" class="form-control num" value="${discount}" min="0" max="100" step="any" onchange="InvoiceForm.calcLine(${idx})" style="width:70px"/></td>
      <td class="num line-total" id="linetotal_${idx}">0.00</td>
      <td><button type="button" class="btn btn-icon" style="color:var(--error)" onclick="this.closest('tr').remove();InvoiceForm.updateTotals()">
        <span class="material-symbols-outlined" style="font-size:18px">delete</span></button></td>`;
    tbody.appendChild(tr);
    
    // Initialize TomSelect for the new row
    const sel = tr.querySelector('.searchable-product-select');
    if (sel && typeof TomSelect !== 'undefined') {
      try {
        new TomSelect(sel, {
          create: false,
          maxOptions: 100,
          searchField: ['text'], // Searches the text of the options
          placeholder: '-- ابحث عن منتج --',
          allowEmptyOption: true,
          onChange: function(value) {
            InvoiceForm.onProductChange(sel, idx, value);
          },
          // Ensure dropdown is not clipped by table
          dropdownParent: 'body'
        });
      } catch (err) {
        console.error("Error initializing TomSelect:", err);
      }
    }

    this.calcLine(idx);
  },

  onProductChange(sel, idx, val = null) {
    const productId = val || sel.value;
    if (!productId) return;
    
    // Ensure we have the list
    if (!window.__products || window.__products.length === 0) {
      console.warn("Products list is empty or not loaded yet.");
      return;
    }

    const product = window.__products.find(p => p.id == productId);
    if (!product) return;

    const row = sel.closest('tr');
    if (row) {
      // --- MERGE LOGIC ---
      // Check if another row already has this product_id
      let existingRow = null;
      document.querySelectorAll('#invoice-lines-body tr').forEach(r => {
        if (r !== row) {
          const pId = r.querySelector('select[name="product_id[]"]')?.value;
          if (pId == productId) {
            existingRow = r;
          }
        }
      });

      if (existingRow) {
        // Increment quantity of existing row
        const qtyInput = existingRow.querySelector('input[name="qty[]"]');
        const currentQty = parseFloat(row.querySelector('input[name="qty[]"]').value) || 1;
        qtyInput.value = (parseFloat(qtyInput.value) || 0) + currentQty;
        
        // Find the index of the existing row to recalculate it
        // The index is usually in the ID of the total column: linetotal_{idx}
        const totalCell = existingRow.querySelector('.line-total');
        if (totalCell && totalCell.id) {
          const existingIdx = totalCell.id.replace('linetotal_', '');
          this.calcLine(existingIdx);
        }
        
        // Remove current row
        row.remove();
        this.updateTotals();
        showToast('تم دمج الصنف مع البند الموجود مسبقاً', 'info');
        return;
      }
      // --- END MERGE LOGIC ---

      row.querySelector('input[name="description[]"]').value = product.name_ar || product.name;
      const priceInput = document.getElementById(`price_${idx}`);
      if (priceInput) priceInput.value = parseFloat(product.unit_price.toFixed(2));
      
      const sellingInput = row.querySelector('input[name="selling_price[]"]');
      if (sellingInput) sellingInput.value = parseFloat((product.selling_price || product.unit_price || 0).toFixed(2));
    }
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
