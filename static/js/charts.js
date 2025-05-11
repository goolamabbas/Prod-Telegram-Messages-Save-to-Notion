// Global chart instances
let messageChart = null;
let syncChart = null;

// Initialize charts when page loads
document.addEventListener('DOMContentLoaded', function() {
    const messageCtx = document.getElementById('messageChart').getContext('2d');
    const syncCtx = document.getElementById('syncChart').getContext('2d');
    
    // Initialize message chart
    messageChart = new Chart(messageCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Messages',
                data: [],
                backgroundColor: 'rgba(54, 162, 235, 0.5)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                }
            }
        }
    });
    
    // Initialize sync status chart
    syncChart = new Chart(syncCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Successful Syncs',
                    data: [],
                    backgroundColor: 'rgba(75, 192, 192, 0.5)',
                    borderColor: 'rgba(75, 192, 192, 1)',
                    borderWidth: 1
                },
                {
                    label: 'Failed Syncs',
                    data: [],
                    backgroundColor: 'rgba(255, 99, 132, 0.5)',
                    borderColor: 'rgba(255, 99, 132, 1)',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        precision: 0
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                }
            }
        }
    });
});

// Update message chart with new data
function updateMessageChart(data) {
    if (!messageChart) return;
    
    // Format dates for display
    const dates = Object.keys(data).sort();
    const formattedDates = dates.map(date => formatDate(date));
    const counts = dates.map(date => data[date]);
    
    // Update chart data
    messageChart.data.labels = formattedDates;
    messageChart.data.datasets[0].data = counts;
    messageChart.update();
}

// Update sync chart with new data
function updateSyncChart(data) {
    if (!syncChart) return;
    
    // Format dates for display
    const dates = Object.keys(data).sort();
    const formattedDates = dates.map(date => formatDate(date));
    const successCounts = dates.map(date => data[date].success);
    const failureCounts = dates.map(date => data[date].failure);
    
    // Update chart data
    syncChart.data.labels = formattedDates;
    syncChart.data.datasets[0].data = successCounts;
    syncChart.data.datasets[1].data = failureCounts;
    syncChart.update();
}

// Format date for display
function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
