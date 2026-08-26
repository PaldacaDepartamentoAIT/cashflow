function initDetalleProyecto(config) {
    const bcvRate = config.bcvRate;
    const orgsData = config.orgsData;
    let tCurrentInputCurrency = 'USD';

    // Moneda de una cuenta dentro de la organización seleccionada.
    function accountCurrency(orgId, accId) {
        const orgData = orgsData[orgId];
        if (orgData && orgData.accounts) {
            const acc = orgData.accounts.find(a => a.id == accId);
            if (acc) return acc.currency;
        }
        return 'BS';
    }

    // Cada cuenta mueve una sola pista de dinero: bolívares (par Bs./USD-BCV con
    // tasa), dólares reales o euros. La moneda de la cuenta decide qué se ve.
    function applyTCurrencyMode(currency) {
        const form = document.getElementById('transactionForm');
        if (!form) return;

        const isReal = currency === 'USD';
        const isEur = currency === 'EUR';
        const isBcv = !isReal && !isEur;

        const realContainer = document.getElementById('realDollarInputContainer');
        const eurGroup = document.getElementById('eurInputGroup');
        const rateContainer = document.getElementById('dailyRateContainer');
        const tAmountDisplay = document.getElementById('id_t_amount_display');

        if (realContainer) realContainer.style.display = isReal ? 'block' : 'none';
        if (eurGroup) eurGroup.style.display = isEur ? 'block' : 'none';
        if (rateContainer) rateContainer.style.display = isBcv ? 'block' : 'none';
        if (tAmountDisplay && tAmountDisplay.parentElement.parentElement) {
            tAmountDisplay.parentElement.parentElement.style.display = isBcv ? 'block' : 'none';
        }

        if (document.getElementById('has_bank_fee').checked) {
            document.getElementById('bcvFeeInputGroup').style.display = isBcv ? 'block' : 'none';
            document.getElementById('realFeeInputGroup').style.display = isReal ? 'block' : 'none';
            const eurFeeGroup = document.getElementById('eurFeeInputGroup');
            if (eurFeeGroup) eurFeeGroup.style.display = isEur ? 'block' : 'none';
        }

        // Los campos ajenos a la moneda se limpian para que el backend no los
        // rechace por pertenecer a otra pista.
        const eurField = form.querySelector('[name="amount_eur"]');
        const eurFeeField = form.querySelector('[name="bank_fee_eur"]');
        const realField = form.querySelector('[name="real_dollars"]');
        if (!isEur) {
            if (eurField) eurField.value = '';
            if (eurFeeField) eurFeeField.value = '0.00';
        }
        if (!isReal && realField) realField.value = '';
    }

    // Funciones globales de transacción
    window.resetTransactionForm = function () {
        if (window.userIsViewer) return;
        const form = document.getElementById('transactionForm');
        if (!form) return;
        form.reset();
        form.action = config.crearTransUrl;
        document.getElementById('transactionModalTitle').innerText = 'Nueva Transacción';

        const nextFieldReset = form.querySelector('[name="next"]');
        if (nextFieldReset) nextFieldReset.value = window.location.pathname + window.location.search;

        const orgSelect = form.querySelector('[name="organization"]');
        if (orgSelect) {
            orgSelect.value = config.orgId;
            updateOrgFields(orgSelect.value);
        }
        
        const dateField = form.querySelector('[name="date"]');
        if (dateField) dateField.value = new Date().toISOString().split('T')[0];
        
        const tRate = form.querySelector('[name="daily_rate"]');
        if (tRate) {
            tRate.value = bcvRate;
            tRate.disabled = true;
        }
        
        const tManualRateSwitch = document.getElementById('t_manualRateSwitch');
        if (tManualRateSwitch) tManualRateSwitch.checked = false;
        
        if (dateField) loadTRateForDate(dateField.value);
        
        const egresoRadio = document.getElementById('type_egreso');
        if (egresoRadio) egresoRadio.checked = true;
        
        tCurrentInputCurrency = 'USD';
        const tAmountDisplay = document.getElementById('id_t_amount_display');
        if (tAmountDisplay) {
            tAmountDisplay.value = '';
            tAmountDisplay.disabled = true;
        }
        
        // Reset real dollars
        const realContainer = document.getElementById('realDollarInputContainer');
        if (realContainer) realContainer.style.display = 'none';

        const eurGroupReset = document.getElementById('eurInputGroup');
        if (eurGroupReset) eurGroupReset.style.display = 'none';
        const eurFieldReset = form.querySelector('[name="amount_eur"]');
        if (eurFieldReset) {
            eurFieldReset.value = '';
            eurFieldReset.disabled = true;
        }
        const eurFeeFieldReset = form.querySelector('[name="bank_fee_eur"]');
        if (eurFeeFieldReset) eurFeeFieldReset.value = '0.00';
        const eurFeeGroupReset = document.getElementById('eurFeeInputGroup');
        if (eurFeeGroupReset) eurFeeGroupReset.style.display = 'none';

        const dailyRateContainer = document.getElementById('dailyRateContainer');
        if (dailyRateContainer) dailyRateContainer.style.display = 'block';

        const tAmountUsd = form.querySelector('[name="amount_usd"]');
        if (tAmountUsd && tAmountUsd.parentElement.parentElement) {
            tAmountUsd.parentElement.parentElement.style.display = 'block';
        }
        
        // Reset bank fee
        const hasFee = document.getElementById('has_bank_fee');
        if (hasFee) {
            hasFee.checked = false;
            hasFee.disabled = true;
        }
        const feeContainer = document.getElementById('bankFeeContainer');
        if (feeContainer) feeContainer.style.display = 'none';

        updateTCurrencyUI();
    };

    window.editTransaction = function (id, orgId, accId, catId, costCenterId, date, desc, bs, usd, rate, ref, notes, status, valId, real_dollars, fee_bs, fee_usd, fee_real_usd, amount_eur, fee_eur) {
        if (window.userIsViewer) return;
        const form = document.getElementById('transactionForm');
        if (!form) return;
        form.action = '/transacciones/guardar/' + id + '/';
        document.getElementById('transactionModalTitle').innerText = 'Editar Transacción';

        const nextFieldEdit = form.querySelector('[name="next"]');
        if (nextFieldEdit) nextFieldEdit.value = window.location.pathname + window.location.search;

        const dateField = form.querySelector('[name="date"]');
        if (dateField) dateField.value = date;
        
        const orgSelect = form.querySelector('[name="organization"]');
        if (orgSelect) {
            orgSelect.value = orgId;
            updateOrgFields(orgId, accId, catId, costCenterId);
        }
        
        form.querySelector('[name="description"]').value = desc;
        form.querySelector('[name="reference_number"]').value = ref;
        form.querySelector('[name="notes"]').value = notes;
        form.querySelector('[name="status"]').value = status;
        
        const vSelect = form.querySelector('[name="valuation"]');
        if (vSelect) vSelect.value = valId;
        
        const tAmountBs = form.querySelector('[name="amount_bs"]');
        const tAmountUsd = form.querySelector('[name="amount_usd"]');
        const tRate = form.querySelector('[name="daily_rate"]');
        
        if (tAmountBs) tAmountBs.value = (parseFloat(bs.toString().replace(',', '.')) || 0).toString();
        if (tAmountUsd) tAmountUsd.value = (parseFloat(usd.toString().replace(',', '.')) || 0).toString();
        if (tRate) {
            tRate.value = (parseFloat(rate.toString().replace(',', '.')) || 1).toString();
            tRate.disabled = false;
        }
        
        const tManualRateSwitch = document.getElementById('t_manualRateSwitch');
        if (tManualRateSwitch) tManualRateSwitch.checked = true;
        
        // Real Dollars logic
        const realDollarsNum = parseFloat((real_dollars || 0).toString().replace(',', '.')) || 0;
        const realContainer = document.getElementById('realDollarInputContainer');
        const tAmountDisplay = document.getElementById('id_t_amount_display');
        
        if (tAmountDisplay) tAmountDisplay.disabled = false;
        
        const eurNum = parseFloat((amount_eur || 0).toString().replace(',', '.')) || 0;
        const accCurrency = accountCurrency(orgId, accId);
        const isEurTx = (eurNum !== 0 || accCurrency === 'EUR');

        if (isEurTx) {
            applyTCurrencyMode('EUR');
            const eurField = form.querySelector('[name="amount_eur"]');
            if (eurField) eurField.value = Math.abs(eurNum);
        } else if (realDollarsNum !== 0 || accCurrency === 'USD') {
            applyTCurrencyMode('USD');
            // Si es cuenta USD pero real_dollars es 0, usamos el usd original
            if (realDollarsNum === 0 && accCurrency === 'USD') {
                form.querySelector('[name="real_dollars"]').value = Math.abs(parseFloat(usd.toString().replace(',', '.')) || 0);
            } else {
                form.querySelector('[name="real_dollars"]').value = Math.abs(realDollarsNum);
            }
        } else {
            applyTCurrencyMode('BS');
        }

        const valNum = isEurTx
            ? eurNum
            : ((realDollarsNum !== 0 || accCurrency === 'USD')
                ? (realDollarsNum || parseFloat(usd.toString().replace(',', '.')) || 0)
                : parseFloat(usd.toString().replace(',', '.')) || 0);
            
        const egresoRadio = document.getElementById('type_egreso');
        const ingresoRadio = document.getElementById('type_ingreso');
        if (egresoRadio) egresoRadio.checked = valNum < 0;
        if (ingresoRadio) ingresoRadio.checked = valNum >= 0;
        
        const usdNum = parseFloat(usd.toString().replace(',', '.')) || 0;
        const bsNum = parseFloat(bs.toString().replace(',', '.')) || 0;

        if (accCurrency === 'USD') {
            tCurrentInputCurrency = 'USD';
        } else if (accCurrency === 'BS') {
            tCurrentInputCurrency = 'BS';
        } else {
            tCurrentInputCurrency = (usdNum !== 0) ? 'USD' : 'BS';
        }

        if (tAmountDisplay) tAmountDisplay.value = Math.abs((tCurrentInputCurrency === 'USD') ? usdNum : bsNum);
        
        // Bank Fee logic
        const fBs = parseFloat((fee_bs || 0).toString().replace(',', '.')) || 0;
        const fUsd = parseFloat((fee_usd || 0).toString().replace(',', '.')) || 0;
        const fReal = parseFloat((fee_real_usd || 0).toString().replace(',', '.')) || 0;
        const fEur = parseFloat((fee_eur || 0).toString().replace(',', '.')) || 0;

        form.querySelector('[name="bank_fee_bs"]').value = fBs;
        form.querySelector('[name="bank_fee_usd"]').value = fUsd;
        form.querySelector('[name="bank_fee_real_usd"]').value = fReal;
        const eurFeeFieldEdit = form.querySelector('[name="bank_fee_eur"]');
        if (eurFeeFieldEdit) eurFeeFieldEdit.value = fEur;

        const hasFee = document.getElementById('has_bank_fee');
        if (hasFee) {
            hasFee.disabled = false;
            if (fBs > 0 || fUsd > 0 || fReal > 0 || fEur > 0) {
                hasFee.checked = true;
                document.getElementById('bankFeeContainer').style.display = 'block';
                const eurFeeGroupEdit = document.getElementById('eurFeeInputGroup');
                if (eurFeeGroupEdit) eurFeeGroupEdit.style.display = isEurTx ? 'block' : 'none';
                if (isEurTx) {
                    document.getElementById('bcvFeeInputGroup').style.display = 'none';
                    document.getElementById('realFeeInputGroup').style.display = 'none';
                } else if (realDollarsNum !== 0) {
                    document.getElementById('bcvFeeInputGroup').style.display = 'none';
                    document.getElementById('realFeeInputGroup').style.display = 'block';
                } else {
                    document.getElementById('bcvFeeInputGroup').style.display = 'block';
                    document.getElementById('realFeeInputGroup').style.display = 'none';
                    // fee currency logic ...
                }
            } else {
                hasFee.checked = false;
                document.getElementById('bankFeeContainer').style.display = 'none';
            }
        }

        updateTCurrencyUI();
        CFModal.open('transactionModal');
    };

    window.duplicateTransaction = function (orgId, accId, catId, costCenterId, date, desc, bs, usd, rate, ref, notes, status, valId, real_dollars, fee_bs, fee_usd, fee_real_usd, amount_eur, fee_eur) {
        if (window.userIsViewer) return;
        window.resetTransactionForm();
        window.editTransaction(0, orgId, accId, catId, costCenterId, date, desc, bs, usd, rate, ref, notes, status, valId, real_dollars, fee_bs, fee_usd, fee_real_usd, amount_eur, fee_eur);
        const form = document.getElementById('transactionForm');
        form.action = config.crearTransUrl;
        document.getElementById('transactionModalTitle').innerText = 'Duplicar Transacción (Nueva)';
    };

    // Auxiliares internos
    function updateOrgFields(orgId, selectedAccountId, selectedCategoryId, selectedCostCenterId) {
        const data = orgsData[orgId];
        const form = document.getElementById('transactionForm');
        if (!form) return;
        const accountSelect = form.querySelector('select[name="account"]');
        const categoriesSelect = form.querySelector('select[name="categories"]');
        const costCenterSelect = form.querySelector('select[name="cost_center"]');
        if (!data || !accountSelect || !categoriesSelect) return;
        
        accountSelect.innerHTML = '<option value="">---------</option>';
        data.accounts.forEach(function (acc) {
            const opt = new Option(acc.name, acc.id);
            if (selectedAccountId && acc.id == selectedAccountId) opt.selected = true;
            accountSelect.add(opt);
        });
        categoriesSelect.innerHTML = '';
        const catIds = selectedCategoryId ? selectedCategoryId.toString().split(',') : [];
        data.categories.forEach(function (cat) {
            const opt = new Option(cat.name, cat.id);
            if (catIds.includes(cat.id.toString())) opt.selected = true;
            categoriesSelect.add(opt);
        });

        // Update custom dropdown
        const colorsMap = {};
        if (data.categories) {
            data.categories.forEach(cat => {
                colorsMap[cat.id] = cat.color;
            });
        }
        const categoriesDropdown = document.getElementById('categoryFormDropdown');
        if (categoriesSelect.rebuildCustomDropdown) {
            categoriesSelect.rebuildCustomDropdown(colorsMap);
        } else if (categoriesDropdown) {
            window.initFormCategoriesDropdown(categoriesSelect, categoriesDropdown, colorsMap);
        }

        if (costCenterSelect) {
            costCenterSelect.innerHTML = '<option value="">---------</option>';
            if (data.cost_centers) {
                data.cost_centers.forEach(function (cc) {
                    const opt = new Option(cc.code + ' - ' + cc.name, cc.id);
                    if (selectedCostCenterId && cc.id == selectedCostCenterId) opt.selected = true;
                    costCenterSelect.add(opt);
                });
            }
        }
    }

    function updateTCurrencyUI() {
        const tCurrencyAddon = document.getElementById('t_currencyAddon');
        const tNextCurrencyLabel = document.getElementById('t_nextCurrencyLabel');
        if (!tCurrencyAddon || !tNextCurrencyLabel) return;
        if (tCurrentInputCurrency === 'USD') {
            tCurrencyAddon.innerText = '$';
            tNextCurrencyLabel.innerText = 'BS';
        } else {
            tCurrencyAddon.innerText = 'Bs';
            tNextCurrencyLabel.innerText = 'USD';
        }
        syncTFields();
    }

    function syncTFields() {
        const transactionForm = document.getElementById('transactionForm');
        if (!transactionForm) return;

        const tAmountDisplay = document.getElementById('id_t_amount_display');
        const tAmountUsd = transactionForm.querySelector('input[name="amount_usd"]');
        const tAmountBs = transactionForm.querySelector('input[name="amount_bs"]');
        const tRate = transactionForm.querySelector('input[name="daily_rate"]');
        if (!tAmountDisplay || !tAmountUsd || !tAmountBs || !tRate) return;
        
        let val = Math.abs(parseFloat(tAmountDisplay.value)) || 0;
        const rate = parseFloat(tRate.value) || 1;
        const egresoRadio = document.getElementById('type_egreso');
        const isEgreso = egresoRadio ? egresoRadio.checked : true;
        
        if (isEgreso && val > 0) val = -val;
        if (tCurrentInputCurrency === 'USD') {
            tAmountUsd.value = val.toFixed(2);
            tAmountBs.value = (val * rate).toFixed(2);
        } else {
            tAmountBs.value = val.toFixed(2);
            tAmountUsd.value = (rate !== 0) ? (val / rate).toFixed(2) : 0;
        }
        
        // Ensure hidden fields are visible for form submission
        if (tAmountUsd.parentElement && tAmountUsd.parentElement.parentElement) {
            tAmountUsd.parentElement.parentElement.style.display = 'block';
        }
        if (tAmountBs.parentElement && tAmountBs.parentElement.parentElement) {
            tAmountBs.parentElement.parentElement.style.display = 'block';
        }
        
        updateTTypeColors();
    }

    function loadTRateForDate(dateValue) {
        const transactionForm = document.getElementById('transactionForm');
        if (!transactionForm) return;

        const tManualRateSwitch = document.getElementById('t_manualRateSwitch');
        const tRate = transactionForm.querySelector('input[name="daily_rate"]');
        if (!dateValue || !tManualRateSwitch || tManualRateSwitch.checked) return;
        fetch(config.bcvRatesUrl + '?date=' + dateValue + '&currency=USD')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (payload) {
                if (!payload || !payload.ok || typeof payload.rate !== 'number') return;
                if (tRate) {
                    tRate.value = payload.rate.toFixed(4);
                    syncTFields();
                }
            })
            .catch(function () {});
    }

    function updateTTypeColors() {
        const tAmountDisplay = document.getElementById('id_t_amount_display');
        const egresoRadio = document.getElementById('type_egreso');
        if (!tAmountDisplay || !egresoRadio) return;
        const isEgreso = egresoRadio.checked;
        tAmountDisplay.classList.toggle('cf-text-danger', isEgreso);
        tAmountDisplay.classList.toggle('cf-text-success', !isEgreso);
    }

    function syncRealDollarsFields() {
        const transactionForm = document.getElementById('transactionForm');
        if (!transactionForm) return;

        const realDollarsInput = transactionForm.querySelector('input[name="real_dollars"]');
        const tAmountUsd = transactionForm.querySelector('input[name="amount_usd"]');
        const tAmountBs = transactionForm.querySelector('input[name="amount_bs"]');
        
        if (!realDollarsInput || !tAmountUsd || !tAmountBs) return;

        const realVal = parseFloat(realDollarsInput.value) || 0;
        const egresoRadio = document.getElementById('type_egreso');
        const isEgreso = egresoRadio ? egresoRadio.checked : true;
        
        // Apply sign based on transaction type
        const signedVal = isEgreso && realVal > 0 ? -realVal : realVal;
        
        tAmountUsd.value = signedVal.toFixed(2);
        // For real dollars, amount_bs should also reflect the real dollar value
        tAmountBs.value = signedVal.toFixed(2);
        
        updateTTypeColors();
    }

    function updateExportUrls() {
        const filterForm = document.querySelector('.cf-filter-form');
        if (!filterForm) return;

        const formData = new FormData(filterForm);
        const exportLinks = document.querySelectorAll('a[href*="/transacciones/exportar-pdf/"], a[href*="/transacciones/exportar-xlsx/"]');
        
        exportLinks.forEach(link => {
            try {
                const originalUrl = new URL(link.href, window.location.origin);
                
                // Borrar claves primero para evitar duplicación
                for (const key of formData.keys()) {
                    originalUrl.searchParams.delete(key);
                }
                
                // Añadir todos los valores de FormData
                for (const [key, value] of formData.entries()) {
                    if (value !== null && value !== undefined && value !== '') {
                        originalUrl.searchParams.append(key, value);
                    }
                }
                
                link.href = originalUrl.pathname + originalUrl.search;
            } catch (e) {
                console.error("Error updating export link URL: ", e);
            }
        });
    }

    function updateDashboard() {
        updateExportUrls();
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
                const newKpis = doc.getElementById('projectSummaryCol');
                if (newContent) container.innerHTML = newContent.innerHTML;
                if (newKpis) document.getElementById('projectSummaryCol').innerHTML = newKpis.innerHTML;
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

    function setupTListeners() {
        const transactionForm = document.getElementById('transactionForm');
        if (!transactionForm) return;

        const orgSelect = transactionForm.querySelector('select[name="organization"]');
        const accountSelect = transactionForm.querySelector('select[name="account"]');
        const categoriesSelect = transactionForm.querySelector('select[name="categories"]');
        const categoriesDropdown = document.getElementById('categoryFormDropdown');
        const tAmountDisplay = document.getElementById('id_t_amount_display');
        const tRate = transactionForm.querySelector('input[name="daily_rate"]');
        const tDate = transactionForm.querySelector('input[name="date"]');
        const tCurrencyToggleBtn = document.getElementById('t_currencyToggleBtn');
        const tManualRateSwitch = document.getElementById('t_manualRateSwitch');
        const hasFeeCheck = document.getElementById('has_bank_fee');

        if (categoriesSelect && categoriesDropdown) {
            const initialOrgId = orgSelect ? orgSelect.value : null;
            const initialColorsMap = {};
            if (initialOrgId && orgsData[initialOrgId] && orgsData[initialOrgId].categories) {
                orgsData[initialOrgId].categories.forEach(cat => {
                    initialColorsMap[cat.id] = cat.color;
                });
            }
            window.initFormCategoriesDropdown(categoriesSelect, categoriesDropdown, initialColorsMap);
        }

        if (orgSelect) orgSelect.addEventListener('change', function () { updateOrgFields(this.value); });
        
        if (accountSelect) {
            accountSelect.addEventListener('change', function() {
                const accId = this.value;
                const hasAccount = !!accId;
                
                // Enable/Disable amount inputs
                if (tAmountDisplay) tAmountDisplay.disabled = !hasAccount;
                if (hasFeeCheck) hasFeeCheck.disabled = !hasAccount;

                const eurInput = transactionForm.querySelector('[name="amount_eur"]');
                if (eurInput) eurInput.disabled = !hasAccount;

                if (hasAccount) {
                    const currency = accountCurrency(orgSelect.value, accId);
                    // Sincronizar selectores de moneda con la cuenta
                    tCurrentInputCurrency = currency === 'BS' ? 'BS' : 'USD';
                    applyTCurrencyMode(currency);
                    if (currency !== 'EUR') updateTCurrencyUI();
                } else {
                    // Sin cuenta seleccionada: se vuelve a la vista BCV por defecto
                    applyTCurrencyMode('BS');
                }
            });
        }

        // Add listener for real_dollars input
        const realDollarsInput = transactionForm.querySelector('input[name="real_dollars"]');
        if (realDollarsInput) {
            realDollarsInput.addEventListener('input', syncRealDollarsFields);
        }

        if (hasFeeCheck) {
            hasFeeCheck.addEventListener('change', function() {
                document.getElementById('bankFeeContainer').style.display = this.checked ? 'block' : 'none';
            });
        }

        // Filtros dinámicos
        const filterForm = document.querySelector('.cf-filter-form');
        if (filterForm) {
            updateExportUrls();
            const txFilterSelect = filterForm.querySelector('select[name="tx_filter"]');
            if (txFilterSelect) {
                txFilterSelect.addEventListener('change', function() {
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

        if (tCurrencyToggleBtn) {
            tCurrencyToggleBtn.addEventListener('click', function (e) {
                e.preventDefault();
                const currentVal = parseFloat(tAmountDisplay.value) || 0;
                const rate = parseFloat(tRate.value) || 1;
                if (tCurrentInputCurrency === 'USD') {
                    tAmountDisplay.value = (currentVal * rate).toFixed(2);
                    tCurrentInputCurrency = 'BS';
                } else {
                    tAmountDisplay.value = (rate !== 0) ? (currentVal / rate).toFixed(2) : 0;
                    tCurrentInputCurrency = 'USD';
                }
                updateTCurrencyUI();
            });
        }

        if (tAmountDisplay) tAmountDisplay.addEventListener('input', syncTFields);
        if (tRate) tRate.addEventListener('input', syncTFields);
        
        transactionForm.querySelectorAll('input[name="transaction_type"]').forEach(function (r) {
            r.addEventListener('change', syncTFields);
        });

        if (tManualRateSwitch) {
            tManualRateSwitch.addEventListener('change', function (e) {
                if (tRate) tRate.disabled = !e.target.checked;
                if (!e.target.checked && tDate) loadTRateForDate(tDate.value);
            });
        }

        if (tDate) {
            tDate.addEventListener('change', function () { loadTRateForDate(this.value); });
        }

        if (transactionForm) {
            transactionForm.addEventListener('submit', function (e) {
                const orgSel = transactionForm.querySelector('[name="organization"]');
                const accSel = transactionForm.querySelector('select[name="account"]');
                const curr = accountCurrency(orgSel ? orgSel.value : null, accSel ? accSel.value : null);

                if (curr === 'USD') {
                    const realVal = parseFloat(transactionForm.querySelector('[name="real_dollars"]').value) || 0;
                    if (realVal === 0) {
                        e.preventDefault();
                        alert('El monto en dólares no puede ser cero.');
                        return;
                    }
                } else if (curr === 'EUR') {
                    const eurEl = transactionForm.querySelector('[name="amount_eur"]');
                    const eurVal = parseFloat(eurEl ? eurEl.value : '') || 0;
                    if (eurVal === 0) {
                        e.preventDefault();
                        alert('El monto en euros no puede ser cero.');
                        return;
                    }
                } else {
                    const amount = parseFloat(tAmountDisplay.value) || 0;
                    if (amount === 0) {
                        e.preventDefault();
                        alert('El monto de la transacción no puede ser cero.');
                        return;
                    }
                }
                if (tRate) tRate.disabled = false;
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupTListeners);
    } else {
        setupTListeners();
    }

    window.confirmDeleteTransaction = function (id) {
        if (window.userIsViewer) return;
        const delForm = document.getElementById('deleteForm');
        if (delForm) delForm.action = '/transacciones/eliminar/' + id + '/?next=' + encodeURIComponent(config.currentPath);
        CFModal.open('deleteModal');
    };

    window.viewTransaction = function (id) {
        const content = document.getElementById('detailContent');
        if (!content) return;
        CFModal.open('detailModal');
        fetch('/transacciones/detalle/' + id + '/')
            .then(function (r) { return r.text(); })
            .then(function (html) { content.innerHTML = html; });
    };

    // --- Lógica de Valuaciones ---
    window.toggleValuations = function () {
        const btn = document.getElementById('toggleValuationsBtn');
        const addBtn = document.getElementById('addValuationBtn');
        const container = document.getElementById('valuationsContainer');
        const summaryCol = document.getElementById('projectSummaryCol');
        if (!container || !btn || !summaryCol) return;
        
        if (container.classList.contains('cf-hidden')) {
            container.classList.remove('cf-hidden');
            container.style.display = 'flex';
            if (addBtn) addBtn.style.display = 'inline-flex';
            summaryCol.classList.add('project-summary-col--split');
            btn.innerHTML = '<i class="fa-solid fa-eye-slash cf-me-1"></i>Ocultar Valuaciones';
        } else {
            container.classList.add('cf-hidden');
            container.style.display = 'none';
            if (addBtn) addBtn.style.display = 'none';
            summaryCol.classList.remove('project-summary-col--split');
            btn.innerHTML = '<i class="fa-solid fa-gear cf-me-1"></i>Gestionar Valuaciones';
        }
    };

    window.resetValuationForm = function () {
        if (window.userIsViewer) return;
        const valForm = document.getElementById('valuationForm');
        if (!valForm) return;
        valForm.reset();
        valForm.action = config.crearValUrl;
        document.getElementById('valModalTitle').innerText = 'Nueva Valuación';
        
        const vManualRateSwitch = document.getElementById('manualRateSwitch');
        const vDailyRateField = valForm.querySelector('input[name="daily_rate"]');
        if (vManualRateSwitch) vManualRateSwitch.checked = false;
        if (vDailyRateField) {
            vDailyRateField.value = bcvRate;
            vDailyRateField.disabled = true;
        }
        
        const vAmountDisplay = document.getElementById('id_amount_display');
        if (vAmountDisplay) vAmountDisplay.value = '';
        // updateVCurrencyUI() ... se puede añadir si es necesario
    };

    window.editValuation = function (id, name, usd, bs, rate) {
        if (window.userIsViewer) return;
        const valForm = document.getElementById('valuationForm');
        if (!valForm) return;
        valForm.action = '/valuaciones/guardar/' + config.projectId + '/' + id + '/';
        document.getElementById('valModalTitle').innerText = 'Editar Valuación';
        valForm.querySelector('[name="name"]').value = name;
        
        const vAmountUsdField = valForm.querySelector('input[name="amount_usd"]');
        const vAmountBsField = valForm.querySelector('input[name="amount_bs"]');
        const vDailyRateField = valForm.querySelector('input[name="daily_rate"]');
        
        if (vAmountUsdField) vAmountUsdField.value = usd.toString().replace(',', '.');
        if (vAmountBsField) vAmountBsField.value = bs.toString().replace(',', '.');
        if (vDailyRateField) {
            vDailyRateField.value = rate.toString().replace(',', '.');
            vDailyRateField.disabled = false;
        }
        
        const vManualRateSwitch = document.getElementById('manualRateSwitch');
        if (vManualRateSwitch) vManualRateSwitch.checked = true;
        
        const vAmountDisplay = document.getElementById('id_amount_display');
        if (vAmountDisplay) vAmountDisplay.value = usd.toString().replace(',', '.');
        
        CFModal.open('valuationModal');
    };

    window.confirmDeleteValuation = function (id) {
        if (window.userIsViewer) return;
        const delValForm = document.getElementById('deleteValForm');
        if (delValForm) delValForm.action = '/valuaciones/eliminar/' + id + '/';
        CFModal.open('deleteValModal');
    };
    
    window.toggleCustomDates = function (value) {
        const div = document.getElementById('custom_date_inputs');
        if (div) div.style.display = (value === 'custom') ? 'block' : 'none';
    };

    // Texto del filtro de categorías (igual que en la vista de Transacciones)
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

    document.addEventListener('change', function (e) {
        if (e.target.matches && e.target.matches('#categoryFilterDropdown input[type="checkbox"][name="category"]')) {
            updateSelectedCategoriesText();
        }
    });

    updateSelectedCategoriesText();
}
