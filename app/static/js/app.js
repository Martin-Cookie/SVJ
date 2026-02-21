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
        const modal = document.getElementById('modal-container');
        if (modal) modal.innerHTML = '';
    }
});

// Confirm before destructive actions
document.body.addEventListener('htmx:confirm', function(event) {
    if (event.detail.elt.hasAttribute('hx-confirm')) {
        event.preventDefault();
        if (confirm(event.detail.elt.getAttribute('hx-confirm'))) {
            event.detail.issueRequest();
        }
    }
});

