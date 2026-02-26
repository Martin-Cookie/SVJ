// HTMX configuration
document.body.addEventListener('htmx:afterSwap', function(event) {
    // Auto-dismiss flash messages after 5 seconds
    const flashMessages = event.detail.target.querySelectorAll('[data-auto-dismiss]');
    flashMessages.forEach(function(msg) {
        setTimeout(function() {
            msg.style.transition = 'opacity 0.3s';
            msg.style.opacity = '0';
            setTimeout(function() { msg.remove(); }, 300);
        }, 5000);
    });
});

// Close modal on escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closePdfModal();
        const modal = document.getElementById('modal-container');
        if (modal) modal.innerHTML = '';
    }
});

// PDF preview modal
function openPdfModal(url, title) {
    var modal = document.getElementById('pdf-modal');
    document.getElementById('pdf-modal-title').textContent = title || '';
    document.getElementById('pdf-modal-newtab').href = url;
    document.getElementById('pdf-modal-iframe').src = url;
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closePdfModal() {
    var modal = document.getElementById('pdf-modal');
    if (!modal || modal.classList.contains('hidden')) return;
    modal.classList.add('hidden');
    document.getElementById('pdf-modal-iframe').src = '';
    document.body.style.overflow = '';
}

// Confirm before destructive actions
document.body.addEventListener('htmx:confirm', function(event) {
    if (event.detail.elt.hasAttribute('hx-confirm')) {
        event.preventDefault();
        if (confirm(event.detail.elt.getAttribute('hx-confirm'))) {
            event.detail.issueRequest();
        }
    }
});

// Generic client-side table column sorting
// Usage: <th data-col="0" data-type="num|text" onclick="sortTableCol(this)">Label <span class="sort-arrow"></span></th>
// For split-header tables: add data-sort-tbody="tbody-id" on th
function sortTableCol(th) {
    var col = parseInt(th.dataset.col);
    var type = th.dataset.type || 'text';
    var asc = th.dataset.dir !== 'asc';
    th.dataset.dir = asc ? 'asc' : 'desc';

    th.closest('tr').querySelectorAll('.sort-arrow').forEach(function(s) { s.textContent = ''; });
    var arrow = th.querySelector('.sort-arrow');
    if (arrow) arrow.textContent = asc ? ' \u25B2' : ' \u25BC';

    var tbody;
    if (th.dataset.sortTbody) {
        tbody = document.getElementById(th.dataset.sortTbody);
    } else {
        tbody = th.closest('table').querySelector('tbody');
    }
    if (!tbody) return;

    var rows = Array.from(tbody.querySelectorAll(':scope > tr'));
    rows.sort(function(a, b) {
        var cellA = a.children[col];
        var cellB = b.children[col];
        if (!cellA || !cellB) return 0;
        var va, vb;
        if (type === 'num') {
            va = parseFloat((cellA.dataset.v || cellA.textContent).replace(/\s/g, '').replace(',', '.')) || 0;
            vb = parseFloat((cellB.dataset.v || cellB.textContent).replace(/\s/g, '').replace(',', '.')) || 0;
            return asc ? va - vb : vb - va;
        }
        va = (cellA.dataset.v || cellA.textContent || '').trim().toLowerCase();
        vb = (cellB.dataset.v || cellB.textContent || '').trim().toLowerCase();
        if (va === vb) return 0;
        if (va === '\u2014' || va === '') return 1;
        if (vb === '\u2014' || vb === '') return -1;
        return asc ? va.localeCompare(vb, 'cs') : vb.localeCompare(va, 'cs');
    });
    rows.forEach(function(r) { tbody.appendChild(r); });
}

