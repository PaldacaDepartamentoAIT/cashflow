function initProyectoPublico(config) {

    function updateDashboard() {
        const container = document.getElementById('transactions-container');
        if (!container) return;
        container.classList.add('is-loading');

        const filterForm = document.querySelector('.cf-filter-form');
        const formData = new URLSearchParams(new FormData(filterForm));


        const url = window.location.pathname + '?' + formData.toString();
        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newContent = doc.getElementById('transactions-container');
                // Los KPIs viven ahora en #kpi-container, igual que en Transacciones.
                const newKpis = doc.getElementById('kpi-container');
                const kpiEl = document.getElementById('kpi-container');
                if (newContent) container.innerHTML = newContent.innerHTML;
                if (newKpis && kpiEl) kpiEl.innerHTML = newKpis.innerHTML;
                updateCharts(doc);
                window.history.pushState({}, '', url);
            })
            .finally(() => { container.classList.remove('is-loading'); });
    }

    function updateCharts(doc) {
        const newChartDataEl = doc.getElementById('chartDataJson');
        if (!newChartDataEl || !window.projectCharts) return;
        try {
            const chartData = JSON.parse(newChartDataEl.textContent);
            const charts = window.projectCharts;
            if (charts.category) {
                charts.category.updateOptions({
                    series: chartData.cat_series,
                    labels: chartData.cat_labels,
                    colors: chartData.cat_colors
                });
            }
            if (charts.totals) {
                charts.totals.updateSeries([{
                    name: 'Total',
                    data: [chartData.total_income, chartData.total_expense]
                }]);
            }
            if (charts.evolution) {
                charts.evolution.updateOptions({
                    xaxis: { categories: chartData.evo_labels },
                    series: [{ name: 'Saldo', data: chartData.evo_series }]
                });
            }
        } catch (e) {
            console.error('Error updating project charts:', e);
        }
    }

    function updateSelectedCategoriesText() {
        const dropdown = document.getElementById('categoryFilterDropdown');
        if (!dropdown) return;
        const toggleText = dropdown.querySelector('.cf-dropdown-multiselect__selected-text');
        if (!toggleText) return;

        const checkedCheckboxes = dropdown.querySelectorAll('input[type="checkbox"][name="category"]:checked');
        if (checkedCheckboxes.length === 0) {
            toggleText.textContent = 'Todas';
        } else if (checkedCheckboxes.length === 1) {
            const labelEl = checkedCheckboxes[0].closest('label');
            const badge = labelEl ? labelEl.querySelector('.cf-badge') : null;
            toggleText.textContent = badge ? badge.textContent.trim() : '1 seleccionada';
        } else {
            toggleText.textContent = `${checkedCheckboxes.length} seleccionadas`;
        }
    }

    function setupListeners() {
        const filterForm = document.querySelector('.cf-filter-form');
        if (filterForm) {
            const txFilterSelect = filterForm.querySelector('select[name="tx_filter"]');
            if (txFilterSelect) {
                txFilterSelect.addEventListener('change', function () {
                    updateDashboard();
                });
            }

            filterForm.querySelectorAll('.dynamic-search').forEach(el => {
                if (el.name === 'tx_filter') return; // Handled above
                el.addEventListener('change', updateDashboard);
                if (el.tagName === 'INPUT' && el.type === 'text') {
                    let timer;
                    el.addEventListener('input', () => {
                        clearTimeout(timer);
                        timer = setTimeout(updateDashboard, 500);
                    });
                }
            });
        }

        document.addEventListener('change', function (e) {
            if (e.target.matches && e.target.matches('#categoryFilterDropdown input[type="checkbox"][name="category"]')) {
                updateSelectedCategoriesText();
            }
        });

        updateSelectedCategoriesText();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupListeners);
    } else {
        setupListeners();
    }
}
