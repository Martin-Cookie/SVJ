// =========================================================================
// Dark mode toggle
// =========================================================================
function toggleTheme() {
    document.documentElement.classList.add('dark-transition');
    var isDark = document.documentElement.classList.toggle('dark');
    localStorage.setItem('svj-theme', isDark ? 'dark' : 'light');
    updateThemeUI(isDark);
    setTimeout(function() { document.documentElement.classList.remove('dark-transition'); }, 300);
}

function updateThemeUI(isDark) {
    var sun = document.getElementById('theme-icon-sun');
    var moon = document.getElementById('theme-icon-moon');
    var label = document.getElementById('theme-label');
    if (sun) sun.classList.toggle('hidden', !isDark);
    if (moon) moon.classList.toggle('hidden', isDark);
    if (label) label.textContent = isDark ? 'Světlý režim' : 'Tmavý režim';
}

function initThemeUI() {
    updateThemeUI(document.documentElement.classList.contains('dark'));
}

document.addEventListener('DOMContentLoaded', initThemeUI);

// OS preference listener (auto-switch when no manual choice)
matchMedia('(prefers-color-scheme:dark)').addEventListener('change', function(e) {
    if (!localStorage.getItem('svj-theme')) {
        document.documentElement.classList.toggle('dark', e.matches);
        updateThemeUI(e.matches);
    }
});

// Auto-dismiss flash messages after 5 seconds
function _autoDismiss(container) {
    var msgs = (container || document).querySelectorAll('[data-auto-dismiss]');
    msgs.forEach(function(msg) {
        setTimeout(function() {
            msg.style.transition = 'opacity 0.3s';
            msg.style.opacity = '0';
            setTimeout(function() { msg.remove(); }, 300);
        }, 5000);
    });
}

document.addEventListener('DOMContentLoaded', function() { _autoDismiss(); });

// HTMX configuration
document.body.addEventListener('htmx:afterSwap', function(event) {
    _autoDismiss(event.detail.target);
});

// HTMX error handling — show user-friendly message on server errors
function _showHtmxError(target, msg) {
    if (!target) return;
    var div = document.createElement('div');
    div.className = 'p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 my-2';
    div.textContent = msg + ' ';
    var link = document.createElement('a');
    link.href = 'javascript:location.reload()';
    link.className = 'underline font-medium';
    link.textContent = 'Obnovit stránku';
    div.appendChild(link);
    target.replaceChildren(div);
}
document.body.addEventListener('htmx:responseError', function(event) {
    var status = event.detail.xhr ? event.detail.xhr.status : '';
    _showHtmxError(event.detail.target, 'Chyba serveru' + (status ? ' (' + status + ')' : '') + '.');
});
document.body.addEventListener('htmx:sendError', function(event) {
    _showHtmxError(event.detail.target, 'Nepodařilo se spojit se serverem.');
});

// Close modal on escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        confirmCancel();
        closePdfModal();
        closeSendConfirmModal();
        var modalContainer = document.getElementById('modal-container');
        if (modalContainer) modalContainer.replaceChildren();
    }
});

// PDF preview modal (pdf.js) — only init when pdf.js is loaded
if (typeof pdfjsLib !== 'undefined') {
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
}

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

// =========================================================================
// Custom confirm modal (replaces browser confirm())
// =========================================================================
var _confirmCallback = null;

function svjConfirm(message, onConfirm) {
    _confirmCallback = onConfirm;
    document.getElementById('confirm-message').textContent = message;
    document.getElementById('confirm-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    document.getElementById('confirm-ok-btn').focus();
}

function confirmOk() {
    var modal = document.getElementById('confirm-modal');
    if (!modal || modal.classList.contains('hidden')) return;
    modal.classList.add('hidden');
    document.body.style.overflow = '';
    if (_confirmCallback) {
        var cb = _confirmCallback;
        _confirmCallback = null;
        cb();
    }
}

function confirmCancel() {
    var modal = document.getElementById('confirm-modal');
    if (!modal || modal.classList.contains('hidden')) return;
    modal.classList.add('hidden');
    document.body.style.overflow = '';
    _confirmCallback = null;
}

// Global handler: intercept form submit with data-confirm
document.addEventListener('submit', function(e) {
    var form = e.target;
    var msg = form.getAttribute('data-confirm');
    if (!msg) return;
    if (form._svjConfirmed) {
        form._svjConfirmed = false;
        return;
    }
    e.preventDefault();
    svjConfirm(msg.replace(/\\n/g, '\n'), function() {
        form.submit();
    });
}, true);

// Global handler: intercept button/link click with data-confirm
document.addEventListener('click', function(e) {
    var el = e.target.closest('[data-confirm]');
    if (!el || el.tagName === 'FORM') return;
    if (el._svjConfirmed) {
        el._svjConfirmed = false;
        return;
    }
    e.preventDefault();
    e.stopPropagation();
    svjConfirm(el.getAttribute('data-confirm').replace(/\\n/g, '\n'), function() {
        el._svjConfirmed = true;
        el.click();
    });
}, true);

// Confirm before destructive HTMX actions (hx-confirm attribute)
document.body.addEventListener('htmx:confirm', function(event) {
    if (event.detail.elt.hasAttribute('hx-confirm')) {
        event.preventDefault();
        svjConfirm(event.detail.elt.getAttribute('hx-confirm').replace(/\\n/g, '\n'), function() {
            event.detail.issueRequest();
        });
    }
});

// Generic client-side table column sorting
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


// =========================================================================
// Send page: checkboxes, test email, confirmation modal
// =========================================================================

// --- Checkbox state in sessionStorage (survives hx-boost page swaps) ---
var _SS_KEY = 'svj_send_checked';
var _SS_SNAP = 'svj_send_snapshot';

function _getCheckedKeys() {
    try {
        var raw = sessionStorage.getItem(_SS_KEY);
        return raw ? JSON.parse(raw) : [];
    } catch(e) { return []; }
}

function _saveCheckedKeys() {
    var keys = [];
    document.querySelectorAll('.rcpt-cb:checked').forEach(function(cb) {
        keys.push(cb.value);
    });
    try { sessionStorage.setItem(_SS_KEY, JSON.stringify(keys)); } catch(e) {}
}

function _restoreCheckedKeys() {
    var tbody = document.getElementById('send-tbody');
    if (!tbody) return;
    var saved = _getCheckedKeys();
    if (saved.length === 0) return;
    var savedSet = new Set(saved);
    tbody.querySelectorAll('.rcpt-cb').forEach(function(cb) {
        if (!cb.disabled && savedSet.has(cb.value)) {
            cb.checked = true;
        }
    });
    _syncSelectAll();
    updateSendButtonCount();
}

function _syncSelectAll() {
    var all = document.querySelectorAll('.rcpt-cb:not(:disabled)').length;
    var checked = document.querySelectorAll('.rcpt-cb:checked').length;
    var master = document.getElementById('select-all-cb');
    if (master) master.checked = (all > 0 && all === checked);
}

// --- Tax assignment checkbox state (tax-cb) in sessionStorage ---
var _TAX_KEY = 'svj_tax_checked';
function _saveTaxChecked() {
    var keys = [];
    document.querySelectorAll('.tax-cb:checked').forEach(function(cb) {
        keys.push(cb.value);
    });
    try { sessionStorage.setItem(_TAX_KEY, JSON.stringify(keys)); } catch(e) {}
}

function _restoreTaxChecked() {
    var tbody = document.getElementById('tax-tbody');
    if (!tbody) return;
    var raw;
    try { raw = sessionStorage.getItem(_TAX_KEY); } catch(e) {}
    if (!raw) return;
    var saved = JSON.parse(raw);
    if (saved.length === 0) return;
    var savedSet = new Set(saved);
    tbody.querySelectorAll('.tax-cb').forEach(function(cb) {
        if (savedSet.has(cb.value)) cb.checked = true;
    });
    // Trigger updateSelectAll/updateButtons if they exist on the page
    if (typeof updateSelectAll === 'function') updateSelectAll();
}

// === Scroll position save/restore for HTMX boosted navigation ===
// Before navigating away via boosted link, save the scrollable container's scrollTop
// into sessionStorage keyed by current URL. On return, restore exact pixel position.

function _getScrollContainer() {
    // Find the actually scrollable container (not sidebar nav or hidden elements)
    var els = document.querySelectorAll('.overflow-y-auto');
    for (var i = 0; i < els.length; i++) {
        if (els[i].scrollHeight > els[i].clientHeight && els[i].clientHeight > 0) {
            return els[i];
        }
    }
    return null;
}

function _saveScrollPos() {
    var sc = _getScrollContainer();
    if (!sc) return;
    var key = 'svj_scroll_' + location.pathname + location.search;
    try { sessionStorage.setItem(key, String(Math.round(sc.scrollTop))); } catch(e) {}
}

function _restoreScrollPos() {
    var key = 'svj_scroll_' + location.pathname + location.search;
    var val;
    try { val = sessionStorage.getItem(key); } catch(e) {}
    if (val === null) return false;
    try { sessionStorage.removeItem(key); } catch(e) {}
    var top = parseInt(val, 10);
    if (isNaN(top) || top <= 0) return false;
    var sc = _getScrollContainer();
    if (!sc) return false;
    setTimeout(function() { sc.scrollTop = top; }, 50);
    return true;
}

// Save checked state before ANY htmx request (partial swap or boost)
document.body.addEventListener('htmx:beforeRequest', function(event) {
    if (document.getElementById('send-tbody')) {
        _saveCheckedKeys();
    }
    if (document.getElementById('tax-tbody')) {
        _saveTaxChecked();
    }
    // Save scroll position before boosted link navigation (not partial HTMX requests)
    var _elt = event.detail.elt;
    if (_elt && _elt.tagName === 'A' && !_elt.hasAttribute('hx-target') && !_elt.hasAttribute('hx-get')) {
        _saveScrollPos();
    }
});

// Restore after ANY htmx settle (partial swap into tbody OR full boost page swap)
document.body.addEventListener('htmx:afterSettle', function(event) {
    initThemeUI();
    _restoreCheckedKeys();
    _restoreTaxChecked();
    _loadTestEmail();
    updateSendButtonCount();

    // Save snapshot once on first entry to send page (not on filter/sort within it)
    if (document.getElementById('send-tbody')) {
        try {
            if (!sessionStorage.getItem(_SS_SNAP)) {
                sessionStorage.setItem(_SS_SNAP, sessionStorage.getItem(_SS_KEY) || '[]');
            }
        } catch(e) {}
    }
    // Restore exact scroll position when returning to a page
    _restoreScrollPos();
});

// Initial page load
document.addEventListener('DOMContentLoaded', function() {
    _restoreCheckedKeys();
    _restoreTaxChecked();
    _loadTestEmail();
    updateSendButtonCount();
    // Save snapshot once on first entry to send page (for "Zavřít" = discard unsaved changes)
    if (document.getElementById('send-tbody')) {
        try {
            if (!sessionStorage.getItem(_SS_SNAP)) {
                sessionStorage.setItem(_SS_SNAP, sessionStorage.getItem(_SS_KEY) || '[]');
            }
        } catch(e) {}
    }
    // Restore scroll for direct page loads (non-HTMX, e.g. full page refresh)
    setTimeout(_restoreScrollPos, 100);
});

// Individual checkbox change
document.addEventListener('change', function(e) {
    if (e.target.classList.contains('rcpt-cb')) {
        _saveCheckedKeys();
        _syncSelectAll();
        updateSendButtonCount();
    }
    if (e.target.classList.contains('tax-cb')) {
        _saveTaxChecked();
    }
});

function toggleAllRecipients(master) {
    document.querySelectorAll('.rcpt-cb:not(:disabled)').forEach(function(cb) {
        cb.checked = master.checked;
    });
    _saveCheckedKeys();
    updateSendButtonCount();
}

function _czPlural(n, one, few, many) {
    if (n === 1) return n + ' ' + one;
    if (n >= 2 && n <= 4) return n + ' ' + few;
    return n + ' ' + many;
}

function _countEmailsAndRecipients() {
    var cbs = document.querySelectorAll('.rcpt-cb:checked');
    var recipients = cbs.length;
    var emails = 0;
    cbs.forEach(function(cb) {
        emails += parseInt(cb.getAttribute('data-email-count') || '1', 10);
    });
    return {emails: emails, recipients: recipients};
}

function updateSendButtonCount() {
    var counts = _countEmailsAndRecipients();
    var span = document.getElementById('send-count');
    if (span) span.textContent = counts.emails;
    var bubble = document.getElementById('selected-count-bubble');
    if (bubble) bubble.textContent = counts.emails;
}

// --- Test email: persist via sessionStorage ---
var _TE_KEY = 'svj_test_email';

function sendTest(btn) {
    var email = document.getElementById('test-email-input').value;
    if (!email) return;
    try { sessionStorage.setItem(_TE_KEY, email); } catch(e) {}
    document.getElementById('test-email-hidden').value = email;
    var docSelect = document.getElementById('test-doc-select');
    if (docSelect) document.getElementById('test-doc-hidden').value = docSelect.value;
    // Copy subject and body so they get saved with the test
    var subj = document.querySelector('input[name="email_subject"]');
    var body = document.querySelector('textarea[name="email_body"]');
    if (subj) document.getElementById('test-subject-hidden').value = subj.value;
    if (body) document.getElementById('test-body-hidden').value = body.value;
    document.getElementById('test-email-form').submit();
}

function _loadTestEmail() {
    var input = document.getElementById('test-email-input');
    if (!input) return;
    if (input.value) {
        // Already has a value from server, save it
        try { sessionStorage.setItem(_TE_KEY, input.value); } catch(e) {}
        return;
    }
    try {
        var saved = sessionStorage.getItem(_TE_KEY);
        if (saved) input.value = saved;
    } catch(e) {}
}

function discardAndClose(url) {
    // Restore snapshot (state from when page was loaded) and navigate away
    try {
        var snap = sessionStorage.getItem(_SS_SNAP);
        if (snap !== null) {
            sessionStorage.setItem(_SS_KEY, snap);
        } else {
            sessionStorage.removeItem(_SS_KEY);
        }
        sessionStorage.removeItem(_SS_SNAP);
    } catch(e) {}
    window.location.href = url;
}

function toggleEmailSelect(checkbox, sessionId, distId, email, key) {
    var checked = checkbox.checked;
    var form = new FormData();
    form.append('email', email);
    form.append('checked', checked ? 'true' : 'false');
    fetch('/dane/' + sessionId + '/rozeslat/email-vyber/' + distId, {
        method: 'POST',
        body: form,
        headers: {'HX-Request': 'true'}
    }).then(function(resp) { return resp.text(); })
    .then(function(html) {
        var row = document.getElementById('rcpt-' + key);
        if (row) {
            row.outerHTML = html;
            _restoreCheckedKeys();
            updateSendButtonCount();
        }
    });
}

function toggleEmailEdit(key) {
    var cell = document.getElementById('email-cell-' + key);
    if (!cell) return;
    var display = cell.querySelector('.email-display');
    var edit = cell.querySelector('.email-edit');
    if (display) display.classList.toggle('hidden');
    if (edit) edit.classList.toggle('hidden');
}

// --- Send confirmation modal ---
function showSendConfirmModal() {
    var counts = _countEmailsAndRecipients();
    if (counts.recipients === 0) return;
    var emailText = _czPlural(counts.emails, 'email', 'emaily', 'emailů');
    var rcptText = _czPlural(counts.recipients, 'příjemci', 'příjemcům', 'příjemcům');
    var verb = counts.emails === 1 ? 'Bude odeslán ' : (counts.emails >= 2 && counts.emails <= 4 ? 'Budou odeslány ' : 'Bude odesláno ');
    document.getElementById('modal-count-emails').textContent = emailText;
    document.getElementById('modal-count-recipients').textContent = rcptText;
    document.getElementById('modal-count-verb').textContent = verb;
    var subj = document.querySelector('input[name="email_subject"]');
    document.getElementById('modal-subject').textContent = subj ? subj.value : '';
    document.getElementById('send-confirm-modal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeSendConfirmModal() {
    var modal = document.getElementById('send-confirm-modal');
    if (!modal) return;
    modal.classList.add('hidden');
    document.body.style.overflow = '';
}

function startBatchSend() {
    closeSendConfirmModal();
    // Build a dynamic form with selected keys (no outer <form> wrapping table)
    var form = document.createElement('form');
    form.method = 'POST';
    form.action = document.getElementById('send-tbody').dataset.sendUrl;
    document.querySelectorAll('.rcpt-cb:checked').forEach(function(cb) {
        var inp = document.createElement('input');
        inp.type = 'hidden';
        inp.name = 'selected_keys';
        inp.value = cb.value;
        form.appendChild(inp);
    });
    document.body.appendChild(form);
    // Clear selection after sending
    try { sessionStorage.removeItem(_SS_KEY); } catch(e) {}
    form.submit();
}
