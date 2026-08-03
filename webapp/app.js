const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    tg.setHeaderColor('#17212b');
    tg.setBackgroundColor('#17212b');
}

const state = {
    period: 1,
    priceMin: 4000,
    priceMax: 20000,
    search: '',
    activeTab: 'top',
    chart: null,
};

function getInitData() {
    return tg?.initData || '';
}

async function apiFetch(endpoint) {
    const params = new URLSearchParams({
        period: state.period,
        price_min: state.priceMin,
        price_max: state.priceMax,
        search: state.search,
    });

    const res = await fetch(`${endpoint}?${params}`, {
        headers: {
            'X-Telegram-Init-Data': getInitData(),
        },
    });

    if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
    }
    return res.json();
}

function liquidityClass(value) {
    if (value >= 30) return 'liquid-high';
    if (value >= 10) return 'liquid-mid';
    return 'liquid-low';
}

function barClass(value) {
    if (value >= 30) return 'high';
    if (value >= 10) return 'mid';
    return 'low';
}

function renderCategoryCard(cat, index, mode) {
    const liqClass = liquidityClass(cat.liquidity);
    const mainMetric = mode === 'top'
        ? `<div class="metric"><div class="metric-value ${liqClass}">${cat.liquidity}%</div><div class="metric-label">Ліквідність</div></div>`
        : `<div class="metric"><div class="metric-value">${cat.active_count}</div><div class="metric-label">Активних</div></div>`;

    const barWidth = mode === 'top' ? Math.min(cat.liquidity, 100) : Math.min(cat.active_count / 5, 100);

    return `
        <div class="category-card" data-id="${cat.id}">
            <div class="card-header">
                <span class="card-name">${cat.name}</span>
                <span class="card-rank">#${index + 1}</span>
            </div>
            <div class="card-metrics">
                ${mainMetric}
                <div class="metric"><div class="metric-value">${cat.speed_days}</div><div class="metric-label">Днів</div></div>
                <div class="metric"><div class="metric-value">${cat.volume}</div><div class="metric-label">Продано</div></div>
                <div class="metric"><div class="metric-value">${cat.total_listed}</div><div class="metric-label">На ринку</div></div>
            </div>
            <div class="liquidity-bar">
                <div class="liquidity-bar-fill ${barClass(cat.liquidity)}" style="width: ${barWidth}%"></div>
            </div>
        </div>
    `;
}

function showLoading(show) {
    document.getElementById('loading').classList.toggle('hidden', !show);
}

async function loadData() {
    showLoading(true);
    try {
        const endpoint = state.activeTab === 'top' ? '/api/metrics/top' : '/api/metrics/active';
        const data = await apiFetch(endpoint);
        const listId = state.activeTab === 'top' ? 'top-list' : 'active-list';
        const container = document.getElementById(listId);

        if (!data.categories || data.categories.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div style="font-size: 40px">📭</div>
                    <p>Немає даних для обраного періоду.<br>Дані з'являться після першого збору о 8:00.</p>
                </div>`;
        } else {
            container.innerHTML = data.categories.map((cat, i) =>
                renderCategoryCard(cat, i, state.activeTab === 'top' ? 'top' : 'active')
            ).join('');

            container.querySelectorAll('.category-card').forEach(card => {
                card.addEventListener('click', () => openDetail(parseInt(card.dataset.id)));
            });
        }
    } catch (err) {
        console.error(err);
        const listId = state.activeTab === 'top' ? 'top-list' : 'active-list';
        document.getElementById(listId).innerHTML = `
            <div class="empty-state">
                <div style="font-size: 40px">⚠️</div>
                <p>Помилка завантаження. Спробуйте пізніше.</p>
            </div>`;
    } finally {
        showLoading(false);
    }
}

async function openDetail(categoryId) {
    try {
        const params = new URLSearchParams({
            period: state.period,
            price_min: state.priceMin,
            price_max: state.priceMax,
        });

        const res = await fetch(`/api/metrics/category/${categoryId}?${params}`, {
            headers: { 'X-Telegram-Init-Data': getInitData() },
        });
        const data = await res.json();

        document.getElementById('detail-title').textContent = data.category.name;
        document.getElementById('detail-stats').innerHTML = `
            <div class="stat-box"><div class="value ${liquidityClass(data.liquidity)}">${data.liquidity}%</div><div class="label">Ліквідність</div></div>
            <div class="stat-box"><div class="value">${data.speed_days}</div><div class="label">Днів до продажу</div></div>
            <div class="stat-box"><div class="value">${data.volume}</div><div class="label">Продано</div></div>
            <div class="stat-box"><div class="value">${data.active_count}</div><div class="label">Активних</div></div>
            <div class="stat-box"><div class="value">${data.avg_price ? Math.round(data.avg_price).toLocaleString() + ' ₴' : '-'}</div><div class="label">Сер. ціна</div></div>
            <div class="stat-box"><div class="value">${data.margin_pct ? '+' + data.margin_pct + '%' : '0%'}</div><div class="label">Маржинальність</div></div>
        `;

        renderChart(data.liquidity_history);
        renderPriceDist(data.price_distribution);
        renderSoldExamples(data.sold_examples);

        document.getElementById('detail-modal').classList.remove('hidden');
        if (tg) tg.BackButton.show();
    } catch (err) {
        console.error(err);
    }
}

function renderChart(history) {
    const canvas = document.getElementById('liquidity-chart');
    if (state.chart) {
        state.chart.destroy();
    }

    if (!history || history.length === 0) {
        canvas.parentElement.innerHTML = '<p style="text-align:center;color:#708499;padding:20px">Недостатньо даних для графіка</p>';
        return;
    }

    state.chart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: history.map(h => h.metric_date),
            datasets: [{
                label: 'Ліквідність %',
                data: history.map(h => h.liquidity),
                borderColor: '#d63351',
                backgroundColor: 'rgba(214, 51, 81, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 3,
            }],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#708499' } },
                x: { grid: { display: false }, ticks: { color: '#708499', maxTicksLimit: 7 } },
            },
        },
    });
}

function renderPriceDist(dist) {
    const container = document.getElementById('price-dist');
    if (!dist || dist.length === 0) {
        container.innerHTML = '<p style="color:#708499;font-size:13px">Немає даних</p>';
        return;
    }
    const max = Math.max(...dist.map(d => d.count));
    container.innerHTML = dist.map(d => `
        <div class="price-bar-row">
            <span class="price-bar-label">${d.price_range}</span>
            <div class="price-bar-track"><div class="price-bar-fill" style="width:${(d.count / max) * 100}%"></div></div>
            <span class="price-bar-count">${d.count}</span>
        </div>
    `).join('');
}

function renderSoldExamples(examples) {
    const container = document.getElementById('sold-examples');
    if (!examples || examples.length === 0) {
        container.innerHTML = '<p style="color:#708499;font-size:13px">Немає проданих оголошень за період</p>';
        return;
    }
    container.innerHTML = examples.map(ex => `
        <div class="sold-item">
            <div class="sold-item-title">${ex.title}</div>
            <div class="sold-item-meta">
                <span class="sold-item-price">${Math.round(ex.price).toLocaleString()} ₴</span>
                <span>${ex.sold_date || ''}</span>
            </div>
        </div>
    `).join('');
}

function closeModal() {
    document.getElementById('detail-modal').classList.add('hidden');
    if (tg) tg.BackButton.hide();
}

document.querySelectorAll('.period-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.period = parseInt(btn.dataset.period);
        loadData();
    });
});

document.querySelectorAll('.price-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.price-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.priceMin = parseInt(btn.dataset.min);
        state.priceMax = parseInt(btn.dataset.max);
        loadData();
    });
});

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        state.activeTab = tab.dataset.tab;
        document.getElementById(`content-${state.activeTab}`).classList.add('active');
        loadData();
    });
});

let searchTimeout;
document.getElementById('search').addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        state.search = e.target.value;
        loadData();
    }, 300);
});

document.getElementById('modal-close').addEventListener('click', closeModal);

if (tg) {
    tg.BackButton.onClick(closeModal);
}

loadData();
