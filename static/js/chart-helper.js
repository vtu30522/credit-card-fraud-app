function createChart(canvasId, type, data, options = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    const defaultOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    color: '#cbd5e1',
                    font: { family: 'Segoe UI, sans-serif' },
                }
            }
        },
        scales: {
            x: { ticks: { color: '#cbd5e1' }, grid: { color: 'rgba(255,255,255,0.05)' } },
            y: { ticks: { color: '#cbd5e1' }, grid: { color: 'rgba(255,255,255,0.05)' }, beginAtZero: true }
        }
    };

    return new Chart(canvas, {
        type,
        data,
        options: Object.assign({}, defaultOptions, options)
    });
}

function createLineChart(canvasId, labels, values, labelText, color) {
    return createChart(canvasId, 'line', {
        labels,
        datasets: [{
            label: labelText,
            data: values,
            borderColor: color,
            backgroundColor: 'rgba(236,72,153,0.25)',
            tension: 0.35,
            fill: true,
            pointRadius: 4,
            pointBackgroundColor: color,
        }]
    }, { plugins: { legend: { display: false } } });
}

function createBarChart(canvasId, labels, values, labelText, color) {
    return createChart(canvasId, 'bar', {
        labels,
        datasets: [{
            label: labelText,
            data: values,
            backgroundColor: color,
            borderColor: color,
            borderWidth: 1,
        }]
    }, { plugins: { legend: { display: false } } });
}

function createDoughnutChart(canvasId, labels, values, colors) {
    return createChart(canvasId, 'doughnut', {
        labels,
        datasets: [{
            data: values,
            backgroundColor: colors,
            borderColor: '#0f172a',
            borderWidth: 2,
        }]
    }, { plugins: { legend: { position: 'bottom' } } });
}
