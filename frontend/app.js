const API_BASE = 'http://localhost:5000/api';
let growthChart = null;

function getCommonInputs() {
    return {
        N: parseFloat(document.getElementById('N').value),
        P: parseFloat(document.getElementById('P').value),
        K: parseFloat(document.getElementById('K').value),
        temp: parseFloat(document.getElementById('temp').value),
        temperature: parseFloat(document.getElementById('temp').value), // for recommend endpoint
        humidity: parseFloat(document.getElementById('humidity').value),
        ph: parseFloat(document.getElementById('ph').value),
        rainfall: parseFloat(document.getElementById('rainfall').value),
        fertilizer: parseFloat(document.getElementById('fertilizer').value)
    };
}

document.addEventListener('DOMContentLoaded', () => {
    // Attempt to load crops from API to verify connectivity
    fetch(`${API_BASE}/cropsim/crops`)
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                const select = document.getElementById('crop_type');
                select.innerHTML = '';
                data.supported_crops.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c;
                    opt.innerText = c.charAt(0).toUpperCase() + c.slice(1);
                    select.appendChild(opt);
                });
                document.getElementById('bc-text').innerText = 'Connected to Backend';
                document.querySelector('.status-dot').classList.add('active');
            }
        })
        .catch(err => {
            console.error('Failed to connect to backend', err);
            document.getElementById('bc-text').innerText = 'Backend Offline';
            document.getElementById('bc-text').style.color = 'var(--danger)';
        });

    // Manual Simulation Form
    document.getElementById('sim-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('btn-sim');
        btn.disabled = true;
        btn.innerText = 'Simulating...';

        const payload = getCommonInputs();
        payload.crop_type = document.getElementById('crop_type').value;
        payload.moisture = parseFloat(document.getElementById('moisture').value);

        try {
            const res = await fetch(`${API_BASE}/cropsim`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if(data.status === 'success') {
                updateDashboard(data);
            } else {
                alert('Simulation Error: ' + (data.message || JSON.stringify(data.errors)));
            }
        } catch(err) {
            console.error(err);
            alert('Network error connecting to backend.');
        } finally {
            btn.disabled = false;
            btn.innerText = 'Run CropSim (Manual)';
        }
    });

    // Recommend Crop Only
    document.getElementById('btn-recommend').addEventListener('click', async () => {
        const btn = document.getElementById('btn-recommend');
        btn.disabled = true;
        btn.innerText = 'Thinking...';

        try {
            const res = await fetch(`${API_BASE}/crop-recommendation`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(getCommonInputs())
            });
            const data = await res.json();
            if(data.status === 'success') {
                renderRecommendation(data);
            } else {
                alert('Recommendation Error: ' + JSON.stringify(data.errors));
            }
        } catch(err) {
            console.error(err);
            alert('Network error.');
        } finally {
            btn.disabled = false;
            btn.innerText = 'Recommend Crop Only';
        }
    });

    // Full Pipeline (Recommend -> Simulate)
    document.getElementById('btn-full-pipeline').addEventListener('click', async () => {
        const btn = document.getElementById('btn-full-pipeline');
        btn.disabled = true;
        btn.innerText = 'Running Pipeline...';

        try {
            const res = await fetch(`${API_BASE}/crop-recommendation/full-pipeline`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(getCommonInputs())
            });
            const data = await res.json();
            if(data.status === 'success') {
                renderRecommendation(data.recommendation);
                updateDashboard(data.simulation);
            } else {
                alert('Pipeline Error: ' + (data.message || JSON.stringify(data.errors)));
                if (data.recommendation) {
                    renderRecommendation(data.recommendation);
                }
            }
        } catch(err) {
            console.error(err);
            alert('Network error.');
        } finally {
            btn.disabled = false;
            btn.innerText = 'Run Full Pipeline (AI + CropSim)';
        }
    });

    // Auto Simulation (IoT)
    document.getElementById('btn-auto').addEventListener('click', async () => {
        const devId = document.getElementById('device_id').value.trim();
        if(!devId) { alert('Please enter a Device ID'); return; }

        const btn = document.getElementById('btn-auto');
        btn.disabled = true;
        btn.innerText = 'Fetching...';

        try {
            const res = await fetch(`${API_BASE}/cropsim/auto`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    device_id: devId,
                    crop_type: document.getElementById('crop_type').value
                })
            });
            const data = await res.json();
            if(data.status === 'success') {
                updateDashboard(data);
            } else {
                alert('Auto-Sim Error: ' + data.message);
            }
        } catch(err) {
            console.error(err);
            alert('Network error.');
        } finally {
            btn.disabled = false;
            btn.innerText = 'Auto Simulate from Sensor';
        }
    });
});

function renderRecommendation(data) {
    const panel = document.getElementById('rec-panel');
    panel.style.display = 'block';

    document.getElementById('rec-top-crop').innerText = data.top_recommendation;

    const listDiv = document.getElementById('rec-list-container');
    listDiv.innerHTML = '';
    data.recommendations.forEach(r => {
        const pct = (r.confidence * 100).toFixed(1) + '%';
        listDiv.insertAdjacentHTML('beforeend', `
            <div class="rec-item">
                <span class="c-name">${r.crop}</span>
                <span class="c-conf">${pct}</span>
            </div>
        `);
    });

    const msgEl = document.getElementById('rec-supported-msg');
    if (data.cropsim_supported) {
        msgEl.innerText = "This crop is supported by CropSim!";
        msgEl.style.color = "var(--accent)";
    } else {
        msgEl.innerText = "Note: This crop is not currently supported by the CropSim module.";
        msgEl.style.color = "var(--warning)";
    }
}

function updateDashboard(data) {
    if (!data) return; // safety

    document.getElementById('res-sim-crop').innerText = `Simulated Crop: ${data.crop_type}`;

    // 1. Update KPIs
    document.getElementById('res-yield').innerText = data.predicted_yield_kg.toLocaleString();
    document.getElementById('res-baseline').innerText = `Baseline: ${data.baseline_yield_kg.toLocaleString()} kg`;

    const stressEl = document.getElementById('res-stress');
    stressEl.innerText = data.overall_stress_pct;
    if(data.overall_stress_pct > 20) stressEl.style.color = 'var(--danger)';
    else if(data.overall_stress_pct > 5) stressEl.style.color = 'var(--warning)';
    else stressEl.style.color = 'var(--accent)';

    document.getElementById('res-id').innerText = `#${data.simulation_id || 'N/A'}`;
    const bc = data.blockchain || {};
    let txText = 'Tx: ' + (bc.tx_id || 'Failed');
    document.getElementById('res-tx').innerText = txText;
    document.getElementById('res-tx').title = `Status: ${bc.status} | CC: ${bc.chaincode}`;

    // 2. Render Chart
    renderChart(data.days, data.growth_curve, data.daily_stress_factor);

    // 3. Render Stress Breakdown
    renderStressBreakdown(data.stress_breakdown);
}

function renderChart(days, growthData, stressData) {
    const ctx = document.getElementById('growthChart').getContext('2d');

    if (growthChart) {
        growthChart.destroy();
    }

    // Prepare gradient for line
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, 'rgba(16, 185, 129, 0.5)'); // Emerald
    gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

    growthChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: days,
            datasets: [{
                label: 'Cumulative Yield (kg)',
                data: growthData,
                borderColor: '#10b981',
                backgroundColor: gradient,
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                fill: true,
                tension: 0.4,
                yAxisID: 'y'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.9)',
                    titleColor: '#f8fafc',
                    bodyColor: '#10b981',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1
                }
            },
            scales: {
                x: { 
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                y: { 
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' },
                    beginAtZero: true
                }
            }
        }
    });
}

function renderStressBreakdown(breakdown) {
    const container = document.getElementById('stress-bars');
    container.innerHTML = '';

    const paramNames = {
        'temp': 'Temp',
        'moisture': 'Moisture',
        'ph': 'Soil pH',
        'N': 'Nitrogen',
        'P': 'Phosphorus',
        'K': 'Potassium'
    };

    for (const [key, val] of Object.entries(breakdown)) {
        // val is 0.0 to 1.0
        const pct = (val * 100).toFixed(0);
        let color = '#10b981'; // Green (good)
        if (val > 0.5) color = '#ef4444'; // Red (bad)
        else if (val > 0.2) color = '#f59e0b'; // Orange (warning)

        const html = `
            <div class="stress-item">
                <div class="stress-label">${paramNames[key] || key}</div>
                <div class="stress-bar-bg">
                    <div class="stress-bar-fill" style="width: ${pct}%; background-color: ${color}"></div>
                </div>
                <div class="stress-val" style="color: ${color}">${pct}%</div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', html);
    }
}
