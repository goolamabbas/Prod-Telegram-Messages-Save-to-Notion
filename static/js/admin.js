document.addEventListener('DOMContentLoaded', function() {
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl, {
            html: true,
            trigger: 'focus'
        });
    });
    
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
