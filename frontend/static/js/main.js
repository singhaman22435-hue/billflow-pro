// main.js — Global UI logic for BillFlow Pro

// Sidebar toggle
const sidebarToggle = document.getElementById('sidebarToggle');
const sidebar = document.getElementById('sidebar');
if (sidebarToggle && sidebar) {
  sidebarToggle.addEventListener('click', () => {
    if (window.innerWidth <= 900) {
      sidebar.classList.toggle('open');
    } else {
      document.querySelector('.app-layout').classList.toggle('sidebar-closed');
    }
  });
}

// Auto-dismiss flash messages after 4 seconds
setTimeout(() => {
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(a => {
    a.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
    a.style.opacity = '0';
    a.style.transform = 'translateY(100%)';
    setTimeout(() => a.remove(), 400);
  });
}, 4000);

// Add loading spinner to buttons on form submit
document.addEventListener('submit', (e) => {
  // Ignore forms with target="_blank"
  if (e.target.target === '_blank') return;
  const btn = e.target.querySelector('button[type="submit"], input[type="submit"]');
  if (btn) {
    btn.classList.add('btn-loading');
  }
});

// Set invoice due date automatically (30 days from invoice date)
const invoiceDateEl = document.getElementById('invoice_date');
const dueDateEl = document.getElementById('due_date');
if (invoiceDateEl && dueDateEl) {
  invoiceDateEl.addEventListener('change', () => {
    if (!dueDateEl.value) {
      const d = new Date(invoiceDateEl.value);
      d.setDate(d.getDate() + 30);
      dueDateEl.value = d.toISOString().split('T')[0];
    }
  });
  // Set initial due date
  if (invoiceDateEl.value && !dueDateEl.value) {
    const d = new Date(invoiceDateEl.value);
    d.setDate(d.getDate() + 30);
    dueDateEl.value = d.toISOString().split('T')[0];
  }
}

// Confirm delete
document.querySelectorAll('[data-confirm]').forEach(btn => {
  btn.addEventListener('click', e => {
    if (!confirm(btn.dataset.confirm || 'Are you sure?')) e.preventDefault();
  });
});

// Format currency helper (client side)
function formatCurrency(n) {
  return '₹' + parseFloat(n).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

// Print helper
function printPage() { window.print(); }
