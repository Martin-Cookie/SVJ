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

// PDF preview modal (pdf.js)
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

function openPdfModal(url, title) {
    var modal = document.getElementById('pdf-modal');
    document.getElementById('pdf-modal-title').textContent = title || '';
    document.getElementById('pdf-modal-newtab').href = url;
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';

    var container = document.getElementById('pdf-modal-pages');
    container.innerHTML = '<div class="text-center py-8 text-gray-400">Načítání…</div>';

    // Compute available height: modal panel height minus header (~41px) minus padding
    var panel = container.parentElement;
    var availH = panel.clientHeight - 73;
    var availW = panel.clientWidth - 32;

    pdfjsLib.getDocument(url).promise.then(function(pdf) {
        container.innerHTML = '';
        var chain = Promise.resolve();
        for (var i = 1; i <= pdf.numPages; i++) {
            (function(pageNum) {
                chain = chain.then(function() {
                    return pdf.getPage(pageNum).then(function(page) {
                        var base = page.getViewport({scale: 1});
                        var scaleW = availW / base.width;
                        var scaleH = availH / base.height;
                        var viewport = page.getViewport({scale: Math.min(scaleW, scaleH)});
                        var canvas = document.createElement('canvas');
                        canvas.width = viewport.width;
                        canvas.height = viewport.height;
                        canvas.style.cssText = 'display:block;margin:0 auto 8px;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.15)';
                        container.appendChild(canvas);
                        return page.render({canvasContext: canvas.getContext('2d'), viewport: viewport}).promise;
                    });
                });
            })(i);
        }
    });
}

function closePdfModal() {
    var modal = document.getElementById('pdf-modal');
    if (!modal || modal.classList.contains('hidden')) return;
    modal.classList.add('hidden');
    document.getElementById('pdf-modal-pages').innerHTML = '';
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

