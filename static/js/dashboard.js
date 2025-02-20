// Initialize performance chart
let performanceChart;

function initializeChart(data) {
    const ctx = document.getElementById('performanceChart').getContext('2d');
    const isDarkMode = document.documentElement.getAttribute('data-theme') === 'dark';
    
    // Set chart colors based on theme
    const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    const textColor = isDarkMode ? '#d1d5db' : '#4b5563';
    
    performanceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Win Rate',
                data: data.winRates,
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: isDarkMode ? '#1f2937' : 'white',
                    titleColor: textColor,
                    bodyColor: textColor,
                    borderColor: isDarkMode ? '#374151' : '#e5e7eb',
                    borderWidth: 1
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: gridColor
                    },
                    ticks: {
                        color: textColor,
                        callback: value => value + '%'
                    }
                },
                x: {
                    grid: {
                        color: gridColor
                    },
                    ticks: {
                        color: textColor
                    }
                }
            }
        }
    });
}

// Update chart data based on timeframe
async function updateChartData(days) {
    try {
        const response = await fetch(`/api/performance?days=${days}`);
        const data = await response.json();
        
        performanceChart.data.labels = data.labels;
        performanceChart.data.datasets[0].data = data.winRates;
        performanceChart.update();
    } catch (error) {
        console.error('Error fetching performance data:', error);
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    // Initialize chart with default timeframe (7 days)
    fetch('/api/performance?days=7')
        .then(response => response.json())
        .then(data => initializeChart(data))
        .catch(error => console.error('Error initializing chart:', error));
    
    // Add timeframe change listener
    const timeframeSelect = document.getElementById('chart-timeframe');
    if (timeframeSelect) {
        timeframeSelect.addEventListener('change', function() {
            updateChartData(this.value);
        });
    }
    
    // Update chart when theme changes
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.attributeName === 'data-theme') {
                updateChartData(timeframeSelect.value);
            }
        });
    });
    
    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-theme']
    });
}); 