/**
 * invoice_builder.js — Dynamic line items + GST calculation
 */

let rowIndex = 0;

function addLineItem(data = {}) {
  rowIndex++;
  const tbody = document.getElementById('lineItemsBody');
  const tr = document.createElement('tr');
  tr.id = `row_${rowIndex}`;
  tr.innerHTML = `
    <td style="text-align:center;color:var(--text-muted);font-size:0.8rem;">${rowIndex}</td>
    <td style="min-width:200px;">
      <div class="autocomplete-wrapper">
        <input type="text" class="line-input item-search" placeholder="Search or type item..."
               data-row="${rowIndex}" autocomplete="off" value="${data.description || ''}">
        <div class="autocomplete-dropdown item-dropdown" id="itemDrop_${rowIndex}"></div>
      </div>
    </td>
    <td><input type="text" class="line-input hsn" placeholder="HSN" style="width:80px;" value="${data.hsn_sac || ''}"></td>
    <td><input type="number" class="line-input qty" placeholder="1" min="0.001" step="any" style="width:70px;" value="${data.qty || 1}" oninput="recalcRow(${rowIndex})"></td>
    <td>
      <select class="line-input unit" style="width:70px;">
        ${['Nos','Kg','Ltr','Mtr','Box','Pcs','Set','Hrs','Day','Month'].map(u =>
          `<option ${u === (data.unit||'Nos') ? 'selected' : ''}>${u}</option>`).join('')}
      </select>
    </td>
    <td><input type="number" class="line-input rate" placeholder="0.00" min="0" step="0.01" style="width:100px;" value="${data.rate || ''}" oninput="recalcRow(${rowIndex})"></td>
    <td><input type="number" class="line-input disc" placeholder="0" min="0" max="100" step="0.01" style="width:65px;" value="${data.discount_pct || 0}" oninput="recalcRow(${rowIndex})"></td>
    <td>
      <select class="line-input gst" style="width:70px;" onchange="recalcRow(${rowIndex})">
        ${[0,5,12,18,28].map(r => `<option value="${r}" ${r == (data.gst_rate||18) ? 'selected' : ''}>${r}%</option>`).join('')}
      </select>
    </td>
    <td><input type="number" class="line-input amount" readonly style="width:100px;background:var(--bg-secondary);color:var(--accent);font-weight:600;" value="0.00" placeholder="0.00"></td>
    <td>
      <button type="button" onclick="removeRow(${rowIndex})" 
              style="background:none;border:none;color:var(--danger);cursor:pointer;font-size:1rem;padding:4px;">✕</button>
    </td>
    <input type="hidden" class="item-id-field" value="${data.item_id || ''}">
  `;
  tbody.appendChild(tr);

  // Item search autocomplete
  const searchInput = tr.querySelector('.item-search');
  const dropdown = tr.querySelector('.item-dropdown');

  let timer;
  searchInput.addEventListener('input', () => {
    clearTimeout(timer);
    const q = searchInput.value.trim();
    if (q.length < 1) { dropdown.style.display = 'none'; return; }
    timer = setTimeout(() => {
      fetch(`/api/items/search?q=${encodeURIComponent(q)}`)
        .then(r => r.json())
        .then(items => {
          dropdown.innerHTML = '';
          if (!items.length) {
            dropdown.innerHTML = '<div class="autocomplete-item" style="color:var(--text-muted);">No items found — type to use custom</div>';
          }
          items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'autocomplete-item';
            div.innerHTML = `<div>${item.name}</div><div class="item-sub">HSN: ${item.hsn_sac || '—'} | GST: ${item.gst_rate}% | ₹${item.selling_price}</div>`;
            div.onclick = () => {
              searchInput.value = item.name;
              tr.querySelector('.item-id-field').value = item.id;
              tr.querySelector('.hsn').value = item.hsn_sac || '';
              tr.querySelector('.rate').value = item.selling_price;
              tr.querySelector('.gst').value = item.gst_rate;
              const unitSel = tr.querySelector('.unit');
              for (let o of unitSel.options) { if (o.value === item.unit) { o.selected = true; break; } }
              dropdown.style.display = 'none';
              recalcRow(rowIndex);
            };
            dropdown.appendChild(div);
          });
          dropdown.style.display = 'block';
        });
    }, 250);
  });

  document.addEventListener('click', e => {
    if (!e.target.closest('.autocomplete-wrapper')) dropdown.style.display = 'none';
  });

  recalcRow(rowIndex);
}

function removeRow(idx) {
  const row = document.getElementById(`row_${idx}`);
  if (row) row.remove();
  recalculate();
}

function recalcRow(idx) {
  const row = document.getElementById(`row_${idx}`);
  if (!row) return;
  const qty = parseFloat(row.querySelector('.qty').value) || 0;
  const rate = parseFloat(row.querySelector('.rate').value) || 0;
  const disc = parseFloat(row.querySelector('.disc').value) || 0;
  const amount = qty * rate;
  const discAmt = amount * disc / 100;
  const taxable = amount - discAmt;
  row.querySelector('.amount').value = taxable.toFixed(2);
  recalculate();
}

function recalculate() {
  const isIGST = document.getElementById('is_igst') && document.getElementById('is_igst').checked;
  const rows = document.querySelectorAll('#lineItemsBody tr');
  let subtotal = 0, totalDisc = 0, taxable = 0, cgst = 0, sgst = 0, igst = 0;

  rows.forEach(row => {
    const qty = parseFloat(row.querySelector('.qty')?.value) || 0;
    const rate = parseFloat(row.querySelector('.rate')?.value) || 0;
    const disc = parseFloat(row.querySelector('.disc')?.value) || 0;
    const gstRate = parseFloat(row.querySelector('.gst')?.value) || 0;
    const amt = qty * rate;
    const discAmt = amt * disc / 100;
    const tax = amt - discAmt;

    subtotal += amt;
    totalDisc += discAmt;
    taxable += tax;

    if (isIGST) {
      igst += tax * gstRate / 100;
    } else {
      cgst += tax * (gstRate / 2) / 100;
      sgst += tax * (gstRate / 2) / 100;
    }
  });

  const grand = Math.round(taxable + cgst + sgst + igst);

  const fmt = n => '₹' + n.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});

  document.getElementById('t_subtotal').textContent = fmt(subtotal);
  document.getElementById('t_discount').textContent = '-' + fmt(totalDisc);
  document.getElementById('t_taxable').textContent = fmt(taxable);
  document.getElementById('t_cgst').textContent = fmt(cgst);
  document.getElementById('t_sgst').textContent = fmt(sgst);
  document.getElementById('t_igst').textContent = fmt(igst);
  document.getElementById('t_grand').textContent = fmt(grand);
  document.getElementById('t_words').textContent = numberToWords(grand);
}

function collectLineItems() {
  const rows = document.querySelectorAll('#lineItemsBody tr');
  const items = [];
  rows.forEach(row => {
    const desc = row.querySelector('.item-search')?.value?.trim();
    const rate = parseFloat(row.querySelector('.rate')?.value) || 0;
    if (!desc && !rate) return;
    items.push({
      item_id: row.querySelector('.item-id-field')?.value || null,
      description: desc || '',
      hsn_sac: row.querySelector('.hsn')?.value || '',
      qty: parseFloat(row.querySelector('.qty')?.value) || 1,
      unit: row.querySelector('.unit')?.value || 'Nos',
      rate: rate,
      discount_pct: parseFloat(row.querySelector('.disc')?.value) || 0,
      gst_rate: parseFloat(row.querySelector('.gst')?.value) || 0,
      cess_rate: 0
    });
  });
  return items;
}

// Simple number to words (Indian format)
function numberToWords(num) {
  if (num === 0) return 'Zero Rupees Only';
  const ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine',
    'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen',
    'Seventeen', 'Eighteen', 'Nineteen'];
  const tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];

  function inWords(n) {
    if (n < 20) return ones[n];
    if (n < 100) return tens[Math.floor(n/10)] + (n%10 ? ' ' + ones[n%10] : '');
    if (n < 1000) return ones[Math.floor(n/100)] + ' Hundred' + (n%100 ? ' ' + inWords(n%100) : '');
    if (n < 100000) return inWords(Math.floor(n/1000)) + ' Thousand' + (n%1000 ? ' ' + inWords(n%1000) : '');
    if (n < 10000000) return inWords(Math.floor(n/100000)) + ' Lakh' + (n%100000 ? ' ' + inWords(n%100000) : '');
    return inWords(Math.floor(n/10000000)) + ' Crore' + (n%10000000 ? ' ' + inWords(n%10000000) : '');
  }

  return inWords(Math.round(num)) + ' Rupees Only';
}
