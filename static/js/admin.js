document.addEventListener('DOMContentLoaded', function() {
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl, {
            html: true,
            trigger: 'focus'
        });
    });
    
    // Setup webhook button
    const webhookBtn = document.getElementById('setupWebhookBtn');
    if (webhookBtn) {
        webhookBtn.addEventListener('click', setupWebhook);
    }
    
    // Fetch stats for charts
    fetchStats();
});

// Function to fetch stats from API
function fetchStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            // Update charts with the received data
            updateMessageChart(data.message_stats);
            updateSyncChart(data.sync_stats);
        })
        .catch(error => {
            console.error('Error fetching stats:', error);
        });
}

// Function to set up Telegram webhook
function setupWebhook() {
    const statusDiv = document.getElementById('webhookStatus');
    statusDiv.innerHTML = '<div class="alert alert-info">Setting up webhook...</div>';
    
    fetch('/api/setup_webhook', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            statusDiv.innerHTML = `<div class="alert alert-success">${data.message}</div>`;
        } else {
            statusDiv.innerHTML = `<div class="alert alert-danger">${data.message}</div>`;
        }
    })
    .catch(error => {
        console.error('Error setting up webhook:', error);
        statusDiv.innerHTML = '<div class="alert alert-danger">Failed to set up webhook. Check the console for details.</div>';
    });
}
