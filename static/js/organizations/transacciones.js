function initTransacciones(config) {
    const bcvRate = config.bcvRate;
    let currentInputCurrency = 'USD';
    let currentFeeInputCurrency = 'USD';

    // Definir funciones globales inmediatamente
    window.resetForm = function () {
        if (window.userIsViewer) return;
        const form = document.getElementById('transactionForm');
        if (!form) return;
        form.reset();
        
        const categoriesSelect = form.querySelector('[name="categories"]');
        if (categoriesSelect && categoriesSelect.rebuildCustomDropdown) {
            categoriesSelect.rebuildCustomDropdown();
        }

        form.action = config.crearUrl;
        document.getElementById('modalTitle').innerText = 'Nueva Transacción';

        const nextFieldReset = form.querySelector('[name="next"]');
        if (nextFieldReset) nextFieldReset.value = window.location.pathname + window.location.search;

        document.getElementById('manualRateSwitch').checked = false;
        const rateField = document.querySelector('input[name="daily_rate"]');
        rateField.value = bcvRate;
        rateField.disabled = true;
        loadRateForDate(form.querySelector('[name="date"]').value);

        document.getElementById('type_egreso').checked = true;
        currentInputCurrency = 'USD';
        document.getElementById('id_amount_display').value = '';
        
        // Reset bank fee
        document.getElementById('has_bank_fee').checked = false;
        document.getElementById('bankFeeContainer').style.display = 'none';
        document.getElementById('bcvFeeInputGroup').style.display = 'block';
        document.getElementById('realFeeInputGroup').style.display = 'none';
        currentFeeInputCurrency = 'USD';
        document.getElementById('id_bank_fee_display').value = '';
        form.querySelector('[name="bank_fee_real_usd"]').value = '0.00';

        // Reset real dollars
        const realSwitch = document.getElementById('realDollarSwitch');
        realSwitch.checked = false;
        realSwitch.disabled = true; // Disabled until account selected
        document.getElementById('realDollarInputContainer').style.display = 'none';
        document.getElementById('dailyRateContainer').style.display = 'block';
        document.getElementById('id_amount_display').parentElement.parentElement.style.display = 'block';
        document.getElementById('currencyToggleBtn').style.display = 'inline-block';
        document.getElementById('id_amount_display').required = true;
        
        // Disable inputs until account selected
        document.getElementById('id_amount_display').disabled = true;
        form.querySelector('input[name="real_dollars"]').disabled = true;
        document.getElementById('has_bank_fee').disabled = true;

        // Reset cost center
        const costCenterSelect = form.querySelector('[name="cost_center"]');
        if (costCenterSelect) costCenterSelect.value = '';

        updateCurrencyUI();
        updateFeeCurrencyUI();
        updateValuationVisibility();
    };

    window.editTransaction = function (id, date, account, ref, desc, notes, cat, cost_center, project, valuation, status, bs, usd, rate, fee_bs, fee_usd, real_dollars, fee_real_usd) {
        if (window.userIsViewer) return;
        const form = document.getElementById('transactionForm');
        if (!form) return;
        form.action = '/transacciones/guardar/' + id + '/';
        document.getElementById('modalTitle').innerText = 'Editar Transacción';

        const nextFieldEdit = form.querySelector('[name="next"]');
        if (nextFieldEdit) nextFieldEdit.value = window.location.pathname + window.location.search;

        form.querySelector('[name="date"]').value = date;
        form.querySelector('[name="account"]').value = account;
        document.getElementById('id_reference_number_custom').value = ref;
        form.querySelector('[name="reference_number"]').value = ref;
        form.querySelector('[name="description"]').value = desc;
        form.querySelector('[name="notes"]').value = notes;
        
        const costCenterSelect = form.querySelector('[name="cost_center"]');
        if (costCenterSelect) costCenterSelect.value = cost_center || '';

        const categoriesSelect = form.querySelector('[name="categories"]');
        if (categoriesSelect) {
            Array.from(categoriesSelect.options).forEach(opt => opt.selected = false);
            if (cat) {
                const catIds = cat.toString().split(',');
                catIds.forEach(id => {
                    const opt = categoriesSelect.querySelector(`option[value="${id}"]`);
                    if (opt) opt.selected = true;
                });
            }
            if (categoriesSelect.rebuildCustomDropdown) {
                categoriesSelect.rebuildCustomDropdown();
            }
        }
        form.querySelector('[name="project"]').value = project;
        form.querySelector('[name="status"]').value = status;
        form.querySelector('[name="amount_bs"]').value = (parseFloat(bs.toString().replace(',', '.')) || 0).toString();
        form.querySelector('[name="amount_usd"]').value = (parseFloat(usd.toString().replace(',', '.')) || 0).toString();
        form.querySelector('[name="daily_rate"]').value = (parseFloat(rate.toString().replace(',', '.')) || 1).toString();

        const realDollarsNum = parseFloat((real_dollars || 0).toString().replace(',', '.')) || 0;
        const realSwitch = document.getElementById('realDollarSwitch');
        
        // Enable inputs for editing
        document.getElementById('id_amount_display').disabled = false;
        form.querySelector('input[name="real_dollars"]').disabled = false;
        document.getElementById('has_bank_fee').disabled = false;

        // Account-based switch state
        const accCurrency = config.accountsData[account];
        realSwitch.disabled = (accCurrency !== 'USD');

        if (realDollarsNum !== 0 || accCurrency === 'USD') {
            realSwitch.checked = true;
            // Si es cuenta USD pero real_dollars es 0, usamos el usdNum original
            if (realDollarsNum === 0 && accCurrency === 'USD') {
                form.querySelector('[name="real_dollars"]').value = Math.abs(parseFloat(usd.toString().replace(',', '.')) || 0);
            } else {
                form.querySelector('[name="real_dollars"]').value = Math.abs(realDollarsNum);
            }
            document.getElementById('realDollarInputContainer').style.display = 'block';
            document.getElementById('dailyRateContainer').style.display = 'none';
            document.getElementById('id_amount_display').parentElement.parentElement.style.display = 'none';
            document.getElementById('currencyToggleBtn').style.display = 'none';
            document.getElementById('id_amount_display').required = false;
            
            if (realDollarsNum < 0 || (realDollarsNum === 0 && parseFloat(usd.toString().replace(',', '.')) < 0)) {
                document.getElementById('type_egreso').checked = true;
            } else {
                document.getElementById('type_ingreso').checked = true;
            }
        } else {
            realSwitch.checked = false;
            document.getElementById('realDollarInputContainer').style.display = 'none';
            document.getElementById('dailyRateContainer').style.display = 'block';
            document.getElementById('id_amount_display').parentElement.parentElement.style.display = 'block';
            document.getElementById('currencyToggleBtn').style.display = 'inline-block';
            document.getElementById('id_amount_display').required = true;
            
            const usdNum = parseFloat(usd.toString().replace(',', '.')) || 0;
            const bsNum = parseFloat(bs.toString().replace(',', '.')) || 0;
            if (usdNum < 0 || bsNum < 0) {
                document.getElementById('type_egreso').checked = true;
            } else {
                document.getElementById('type_ingreso').checked = true;
            }
            // Prefer the account's currency for display
            if (accCurrency === 'USD') {
                currentInputCurrency = 'USD';
            } else if (accCurrency === 'BS') {
                currentInputCurrency = 'BS';
            } else {
                currentInputCurrency = (usdNum !== 0) ? 'USD' : 'BS';
            }

            document.getElementById('id_amount_display').value = Math.abs((currentInputCurrency === 'USD') ? usdNum : bsNum);
        }

        const feeBsNum = parseFloat((fee_bs || 0).toString().replace(',', '.')) || 0;
        const feeUsdNum = parseFloat((fee_usd || 0).toString().replace(',', '.')) || 0;
        const feeRealNum = parseFloat((fee_real_usd || 0).toString().replace(',', '.')) || 0;
        
        form.querySelector('[name="bank_fee_bs"]').value = feeBsNum;
        form.querySelector('[name="bank_fee_usd"]').value = feeUsdNum;
        form.querySelector('[name="bank_fee_real_usd"]').value = feeRealNum;

        if (feeBsNum > 0 || feeUsdNum > 0 || feeRealNum > 0) {
            document.getElementById('has_bank_fee').checked = true;
            document.getElementById('bankFeeContainer').style.display = 'block';
            
            if (realSwitch.checked) {
                document.getElementById('bcvFeeInputGroup').style.display = 'none';
                document.getElementById('realFeeInputGroup').style.display = 'block';
            } else {
                document.getElementById('bcvFeeInputGroup').style.display = 'block';
                document.getElementById('realFeeInputGroup').style.display = 'none';
                
                // Prefer the account's currency for fee display
                if (accCurrency === 'USD') {
                    currentFeeInputCurrency = 'USD';
                } else if (accCurrency === 'BS') {
                    currentFeeInputCurrency = 'BS';
                } else {
                    currentFeeInputCurrency = (feeUsdNum !== 0) ? 'USD' : 'BS';
                }

                document.getElementById('id_bank_fee_display').value = (currentFeeInputCurrency === 'USD') ? feeUsdNum : feeBsNum;
            }
        } else {
            document.getElementById('has_bank_fee').checked = false;
            document.getElementById('bankFeeContainer').style.display = 'none';
            document.getElementById('id_bank_fee_display').value = '';
        }

        const vSelect = document.querySelector('select[name="valuation"]');
        if (vSelect) vSelect.value = valuation;
        
        document.getElementById('manualRateSwitch').checked = true;
        document.querySelector('[name="daily_rate"]').disabled = false;

        updateCurrencyUI();
        updateFeeCurrencyUI();
        updateValuationVisibility();
        CFModal.open('transactionModal');
    };

    window.duplicateTransaction = function (date, account, ref, desc, notes, cat, cost_center, project, valuation, status, bs, usd, rate, fee_bs, fee_usd, real_dollars, fee_real_usd) {
        if (window.userIsViewer) return;
        window.resetForm();
        const form = document.getElementById('transactionForm');
        if (!form) return;
        form.action = config.crearUrl;
        document.getElementById('modalTitle').innerText = 'Duplicar Transacción (Nueva)';

        const nextFieldDup = form.querySelector('[name="next"]');
        if (nextFieldDup) nextFieldDup.value = window.location.pathname + window.location.search;

        form.querySelector('[name="date"]').value = date;
        form.querySelector('[name="account"]').value = account;
        document.getElementById('id_reference_number_custom').value = ref;
        form.querySelector('[name="reference_number"]').value = ref;
        form.querySelector('[name="description"]').value = desc;
        form.querySelector('[name="notes"]').value = notes;

        const costCenterSelect = form.querySelector('[name="cost_center"]');
        if (costCenterSelect) costCenterSelect.value = cost_center || '';

        const categoriesSelect = form.querySelector('[name="categories"]');
        if (categoriesSelect) {
            Array.from(categoriesSelect.options).forEach(opt => opt.selected = false);
            if (cat) {
                const catIds = cat.toString().split(',');
                catIds.forEach(id => {
                    const opt = categoriesSelect.querySelector(`option[value="${id}"]`);
                    if (opt) opt.selected = true;
                });
            }
            if (categoriesSelect.rebuildCustomDropdown) {
                categoriesSelect.rebuildCustomDropdown();
            }
        }
        form.querySelector('[name="project"]').value = project;
        form.querySelector('[name="status"]').value = status;
        form.querySelector('[name="daily_rate"]').value = (parseFloat(rate.toString().replace(',', '.')) || 1).toString();

        // Enable inputs for editing
        document.getElementById('id_amount_display').disabled = false;
        form.querySelector('input[name="real_dollars"]').disabled = false;
        document.getElementById('has_bank_fee').disabled = false;

        const realDollarsNum = parseFloat((real_dollars || 0).toString().replace(',', '.')) || 0;
        const realSwitch = document.getElementById('realDollarSwitch');

        // Account-based switch state
        const accCurrency = config.accountsData[account];
        realSwitch.disabled = (accCurrency !== 'USD');

        if (realDollarsNum !== 0 || accCurrency === 'USD') {
            realSwitch.checked = true;
            // Si es cuenta USD pero real_dollars es 0, usamos el usdNum original
            if (realDollarsNum === 0 && accCurrency === 'USD') {
                form.querySelector('[name="real_dollars"]').value = Math.abs(parseFloat(usd.toString().replace(',', '.')) || 0);
            } else {
                form.querySelector('[name="real_dollars"]').value = Math.abs(realDollarsNum);
            }
            document.getElementById('realDollarInputContainer').style.display = 'block';
            document.getElementById('dailyRateContainer').style.display = 'none';
            document.getElementById('id_amount_display').parentElement.parentElement.style.display = 'none';
            document.getElementById('currencyToggleBtn').style.display = 'none';
            document.getElementById('id_amount_display').required = false;

            if (realDollarsNum < 0 || (realDollarsNum === 0 && parseFloat(usd.toString().replace(',', '.')) < 0)) {
                document.getElementById('type_egreso').checked = true;
            } else {
                document.getElementById('type_ingreso').checked = true;
            }
        } else {
            realSwitch.checked = false;
            document.getElementById('realDollarInputContainer').style.display = 'none';
            document.getElementById('dailyRateContainer').style.display = 'block';
            document.getElementById('id_amount_display').parentElement.parentElement.style.display = 'block';
            document.getElementById('currencyToggleBtn').style.display = 'inline-block';
            document.getElementById('id_amount_display').required = true;

            const usdNum = parseFloat(usd.toString().replace(',', '.')) || 0;
            const bsNum = parseFloat(bs.toString().replace(',', '.')) || 0;
            if (usdNum < 0 || bsNum < 0) {
                document.getElementById('type_egreso').checked = true;
            } else {
                document.getElementById('type_ingreso').checked = true;
            }
            // Prefer the account's currency for display
            if (accCurrency === 'USD') {
                currentInputCurrency = 'USD';
            } else if (accCurrency === 'BS') {
                currentInputCurrency = 'BS';
            } else {
                currentInputCurrency = (usdNum !== 0) ? 'USD' : 'BS';
            }

            document.getElementById('id_amount_display').value = Math.abs((currentInputCurrency === 'USD') ? usdNum : bsNum);
        }

        const feeBsNum = parseFloat((fee_bs || 0).toString().replace(',', '.')) || 0;
        const feeUsdNum = parseFloat((fee_usd || 0).toString().replace(',', '.')) || 0;
        const feeRealNum = parseFloat((fee_real_usd || 0).toString().replace(',', '.')) || 0;
        
        form.querySelector('[name="bank_fee_bs"]').value = feeBsNum;
        form.querySelector('[name="bank_fee_usd"]').value = feeUsdNum;
        form.querySelector('[name="bank_fee_real_usd"]').value = feeRealNum;

        if (feeBsNum > 0 || feeUsdNum > 0 || feeRealNum > 0) {
            document.getElementById('has_bank_fee').checked = true;
            document.getElementById('bankFeeContainer').style.display = 'block';
            
            if (realSwitch.checked) {
                document.getElementById('bcvFeeInputGroup').style.display = 'none';
                document.getElementById('realFeeInputGroup').style.display = 'block';
            } else {
                document.getElementById('bcvFeeInputGroup').style.display = 'block';
                document.getElementById('realFeeInputGroup').style.display = 'none';
                
                // Prefer the account's currency for fee display
                if (accCurrency === 'USD') {
                    currentFeeInputCurrency = 'USD';
                } else if (accCurrency === 'BS') {
                    currentFeeInputCurrency = 'BS';
                } else {
                    currentFeeInputCurrency = (feeUsdNum !== 0) ? 'USD' : 'BS';
                }

                document.getElementById('id_bank_fee_display').value = (currentFeeInputCurrency === 'USD') ? feeUsdNum : feeBsNum;
            }
        }

        const vSelect = document.querySelector('select[name="valuation"]');
        if (vSelect) vSelect.value = valuation;
        
        document.getElementById('manualRateSwitch').checked = true;
        document.querySelector('[name="daily_rate"]').disabled = false;

        updateCurrencyUI();
        updateFeeCurrencyUI();
        updateValuationVisibility();
        CFModal.open('transactionModal');
    };

    // Auxiliares privados
    function loadRateForDate(dateValue) {
        const manualRateSwitch = document.getElementById('manualRateSwitch');
        const dailyRateField = document.querySelector('input[name="daily_rate"]');
        if (!dateValue || !manualRateSwitch || manualRateSwitch.checked) return;
        fetch(config.bcvRatesUrl + '?date=' + dateValue + '&currency=USD')
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (payload) {
                if (!payload || !payload.ok || typeof payload.rate !== 'number') return;
                if (dailyRateField) {
                    dailyRateField.value = payload.rate.toFixed(4);
                    syncHiddenFields();
                    syncFeeHiddenFields();
                }
            })
            .catch(function () {});
    }

    function updateCurrencyUI() {
        const currencyAddon = document.getElementById('currencyAddon');
        const nextCurrencyLabel = document.getElementById('nextCurrencyLabel');
        if (!currencyAddon || !nextCurrencyLabel) return;
        if (currentInputCurrency === 'USD') {
            currencyAddon.innerText = '$';
            nextCurrencyLabel.innerText = 'BS';
        } else {
            currencyAddon.innerText = 'Bs';
            nextCurrencyLabel.innerText = 'USD';
        }
        syncHiddenFields();
    }

    function updateFeeCurrencyUI() {
        const feeCurrencyAddon = document.getElementById('feeCurrencyAddon');
        const nextFeeCurrencyLabel = document.getElementById('nextFeeCurrencyLabel');
        if (!feeCurrencyAddon || !nextFeeCurrencyLabel) return;
        if (currentFeeInputCurrency === 'USD') {
            feeCurrencyAddon.innerText = '$';
            nextFeeCurrencyLabel.innerText = 'BS';
        } else {
            feeCurrencyAddon.innerText = 'Bs';
            nextFeeCurrencyLabel.innerText = 'USD';
        }
        syncFeeHiddenFields();
    }

    function syncHiddenFields() {
        const form = document.getElementById('transactionForm');
        if (!form) return;

        const amountDisplay = document.getElementById('id_amount_display');
        const amountUsdField = form.querySelector('input[name="amount_usd"]');
        const amountBsField = form.querySelector('input[name="amount_bs"]');
        const dailyRateField = form.querySelector('input[name="daily_rate"]');
        if (!amountDisplay || !amountUsdField || !amountBsField || !dailyRateField) return;
        let val = Math.abs(parseFloat(amountDisplay.value)) || 0;
        const rate = parseFloat(dailyRateField.value) || 1;
        const isEgreso = document.getElementById('type_egreso').checked;
        if (isEgreso && val > 0) val = -val;
        if (currentInputCurrency === 'USD') {
            amountUsdField.value = val.toFixed(2);
            amountBsField.value = (val * rate).toFixed(2);
        } else {
            amountBsField.value = val.toFixed(2);
            amountUsdField.value = (rate !== 0) ? (val / rate).toFixed(2) : 0;
        }
        updateTypeColors();
    }

    function syncFeeHiddenFields() {
        const form = document.getElementById('transactionForm');
        if (!form) return;

        const feeDisplay = document.getElementById('id_bank_fee_display');
        const feeUsdField = form.querySelector('input[name="bank_fee_usd"]');
        const feeBsField = form.querySelector('input[name="bank_fee_bs"]');
        const dailyRateField = form.querySelector('input[name="daily_rate"]');
        const hasFeeCheckbox = document.getElementById('has_bank_fee');

        if (!feeDisplay || !feeUsdField || !feeBsField || !dailyRateField) return;

        if (!hasFeeCheckbox.checked) {
            feeUsdField.value = '0.00';
            feeBsField.value = '0.00';
            return;
        }

        let val = Math.abs(parseFloat(feeDisplay.value)) || 0;
        const rate = parseFloat(dailyRateField.value) || 1;

        if (currentFeeInputCurrency === 'USD') {
            feeUsdField.value = val.toFixed(2);
            feeBsField.value = (val * rate).toFixed(2);
        } else {
            feeBsField.value = val.toFixed(2);
            feeUsdField.value = (rate !== 0) ? (val / rate).toFixed(2) : 0;
        }
    }

    function updateTypeColors() {
        const amountDisplay = document.getElementById('id_amount_display');
        const isEgreso = document.getElementById('type_egreso').checked;
        if (amountDisplay) {
            amountDisplay.classList.toggle('cf-text-danger', isEgreso);
            amountDisplay.classList.toggle('cf-text-success', !isEgreso);
            amountDisplay.classList.add('cf-fw-bold');
        }
    }

    function updateValuationVisibility() {
        const form = document.getElementById('transactionForm');
        if (!form) return;

        const amountUsdField = form.querySelector('input[name="amount_usd"]');
        const projectSelect = form.querySelector('select[name="project"]');
        const valuationContainer = document.getElementById('valuationContainer');
        const projectsData = config.projectsData || {};
        if (!amountUsdField || !projectSelect || !valuationContainer) return;

        const val = parseFloat(amountUsdField.value) || 0;
        const projectId = projectSelect.value;
        if (val > 0 && projectId && projectsData[projectId] && projectsData[projectId].length > 0) {
            valuationContainer.style.display = 'block';
            filterValuations(projectId);
        } else {
            valuationContainer.style.display = 'none';
            const vSelect = form.querySelector('select[name="valuation"]');
            if (vSelect) vSelect.value = '';
        }
    }

    function filterValuations(projectId) {
        const form = document.getElementById('transactionForm');
        if (!form) return;

        const valuationSelect = form.querySelector('select[name="valuation"]');
        const projectsData = config.projectsData || {};
        if (!valuationSelect) return;
        const valuations = projectsData[projectId] || [];
        const currentValuationId = valuationSelect.value;
        valuationSelect.innerHTML = '<option value="">---------</option>';
        valuations.forEach(function (v) {
            const option = document.createElement('option');
            option.value = v.id;
            option.text = v.name + ' (' + parseFloat(v.amount_usd).toFixed(2) + ' $)';
            if (v.id.toString() === currentValuationId) option.selected = true;
            valuationSelect.appendChild(option);
        });
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

    // Auxiliares para filtrado dinámico AJAX
    function updateDashboard() {
        updateExportUrls();
        const container = document.getElementById('transactions-container');
        if (!container) return;

        const kpiContainer = document.getElementById('kpi-container');

        // Mostrar estado de carga con clase (activa el spinner CSS)
        container.classList.add('is-loading');
        if (kpiContainer) kpiContainer.classList.add('is-loading');

        const form = document.querySelector('.cf-filter-form');
        const formData = new URLSearchParams(new FormData(form));

        // Obtener view_mode actual del toggle si existe
        const activeTab = document.querySelector('.cf-tab.is-active');
        if (activeTab) {
            const urlParams = new URLSearchParams(activeTab.getAttribute('href').split('?')[1]);
            if (urlParams.has('view_mode')) formData.set('view_mode', urlParams.get('view_mode'));
        }

        const url = window.location.pathname + '?' + formData.toString();

        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(r => r.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newContent = doc.getElementById('transactions-container');
                const newKpiContent = kpiContainer ? doc.getElementById('kpi-container') : null;
                if (newContent) {
                    container.innerHTML = newContent.innerHTML;
                    // Actualizar URL sin recargar
                    window.history.pushState({}, '', url);
                }
                if (kpiContainer && newKpiContent) {
                    kpiContainer.innerHTML = newKpiContent.innerHTML;
                }
            })
            .finally(() => {
                container.classList.remove('is-loading');
                if (kpiContainer) kpiContainer.classList.remove('is-loading');
                updateSelectedCategoriesText();
            });
    }

    function updateSelectedCategoriesText() {
        const dropdown = document.getElementById('categoryFilterDropdown');
        if (!dropdown) return;
        const toggleText = dropdown.querySelector('.cf-dropdown-multiselect__selected-text');
        if (!toggleText) return;
        
        const checkedCheckboxes = dropdown.querySelectorAll('input[type="checkbox"][name="category"]:checked');
        if (checkedCheckboxes.length === 0) {
            toggleText.textContent = "Todas";
        } else if (checkedCheckboxes.length === 1) {
            const labelEl = checkedCheckboxes[0].closest('label');
            const badge = labelEl ? labelEl.querySelector('.cf-badge') : null;
            toggleText.textContent = badge ? badge.textContent.trim() : "1 seleccionada";
        } else {
            toggleText.textContent = `${checkedCheckboxes.length} seleccionadas`;
        }
    }

    // Inicializar listeners solo cuando el DOM esté listo
    function setupListeners() {
        const form = document.getElementById('transactionForm');
        if (form) {
            const categoriesSelect = form.querySelector('select[name="categories"]');
            const categoriesDropdown = document.getElementById('categoryFormDropdown');
            if (categoriesSelect && categoriesDropdown) {
                window.initFormCategoriesDropdown(categoriesSelect, categoriesDropdown, config.categoriesColors);
            }
        }
        // Filtros dinámicos
        const filterForm = document.querySelector('.cf-filter-form');
        if (filterForm) {
            updateExportUrls();
            
            // Listeners for checkbox changes to update selected text
            const categoryDropdown = document.getElementById('categoryFilterDropdown');
            if (categoryDropdown) {
                categoryDropdown.querySelectorAll('input[type="checkbox"][name="category"]').forEach(cb => {
                    cb.addEventListener('change', updateSelectedCategoriesText);
                });
                updateSelectedCategoriesText();
            }

            filterForm.querySelectorAll('.dynamic-search').forEach(el => {
                const eventType = (el.tagName === 'SELECT' || el.type === 'date' || el.type === 'checkbox') ? 'change' : 'input';
                let debounceTimer;
                el.addEventListener(eventType, function() {
                    if (eventType === 'input') {
                        clearTimeout(debounceTimer);
                        debounceTimer = setTimeout(updateDashboard, 500);
                    } else {
                        updateDashboard();
                    }
                });
            });
            // Prevenir submit normal
            filterForm.addEventListener('submit', e => e.preventDefault());
        }

        // Toggle de vista AJAX
        document.querySelectorAll('.cf-tab-group .cf-tab').forEach(tab => {
            tab.addEventListener('click', function(e) {
                e.preventDefault();
                const url = this.getAttribute('href');
                // Actualizar clases activas localmente
                this.parentElement.querySelectorAll('.cf-tab').forEach(t => t.classList.remove('is-active'));
                this.classList.add('is-active');
                // Mantener sincronizado el input oculto view_mode del form de filtros,
                // para que cualquier envío del formulario (incl. el listener genérico de base.js) lo respete.
                const urlParams = new URLSearchParams(url.split('?')[1]);
                const viewModeInput = document.querySelector('.cf-filter-form input[name="view_mode"]');
                if (viewModeInput && urlParams.has('view_mode')) {
                    viewModeInput.value = urlParams.get('view_mode');
                }
                updateDashboard();
            });
        });

        if (!form) return;

        const amountDisplay = document.getElementById('id_amount_display');
        const dailyRateField = form.querySelector('input[name="daily_rate"]');
        const manualRateSwitch = document.getElementById('manualRateSwitch');
        const dateField = form.querySelector('input[name="date"]');
        const projectSelect = form.querySelector('select[name="project"]');
        const currencyToggleBtn = document.getElementById('currencyToggleBtn');
        const hasFeeCheckbox = document.getElementById('has_bank_fee');
        const feeDisplay = document.getElementById('id_bank_fee_display');
        const feeCurrencyToggleBtn = document.getElementById('feeCurrencyToggleBtn');
        const bankFeeContainer = document.getElementById('bankFeeContainer');
        const realDollarSwitch = document.getElementById('realDollarSwitch');
        const realDollarInputContainer = document.getElementById('realDollarInputContainer');
        const dailyRateContainer = document.getElementById('dailyRateContainer');
        const accountSelect = form.querySelector('select[name="account"]');

        if (accountSelect) {
            accountSelect.addEventListener('change', function() {
                const accId = this.value;
                const hasAccount = !!accId;
                
                // Enable/Disable amount inputs
                document.getElementById('id_amount_display').disabled = !hasAccount;
                form.querySelector('input[name="real_dollars"]').disabled = !hasAccount;
                document.getElementById('has_bank_fee').disabled = !hasAccount;

                if (hasAccount && config.accountsData && config.accountsData[accId]) {
                    const currency = config.accountsData[accId];
                    const isUSD = (currency === 'USD');
                    
                    if (realDollarSwitch) {
                        realDollarSwitch.checked = isUSD;
                        realDollarSwitch.disabled = !isUSD;
                        // Forzar el disparo del evento change para actualizar la UI
                        realDollarSwitch.dispatchEvent(new Event('change'));
                    }

                    // Sincronizar selectores de moneda con la cuenta
                    currentInputCurrency = currency;
                    currentFeeInputCurrency = currency;
                    updateCurrencyUI();
                    updateFeeCurrencyUI();
                } else {
                    if (realDollarSwitch) {
                        realDollarSwitch.checked = false;
                        realDollarSwitch.disabled = true;
                        realDollarSwitch.dispatchEvent(new Event('change'));
                    }
                }
            });
        }

        if (projectSelect) projectSelect.addEventListener('change', updateValuationVisibility);
        
        form.querySelectorAll('input[name="transaction_type"]').forEach(function (radio) {
            radio.addEventListener('change', function() {
                syncHiddenFields();
                syncRealDollarFields();
            });
        });

        if (realDollarSwitch) {
            realDollarSwitch.addEventListener('change', function() {
                const isReal = this.checked;
                realDollarInputContainer.style.display = isReal ? 'block' : 'none';
                dailyRateContainer.style.display = isReal ? 'none' : 'block';
                amountDisplay.parentElement.parentElement.style.display = isReal ? 'none' : 'block';
                document.getElementById('currencyToggleBtn').style.display = isReal ? 'none' : 'inline-block';
                amountDisplay.required = !isReal;
                
                // Toggle commission inputs based on mode
                if (hasFeeCheckbox.checked) {
                    document.getElementById('bcvFeeInputGroup').style.display = isReal ? 'none' : 'block';
                    document.getElementById('realFeeInputGroup').style.display = isReal ? 'block' : 'none';
                }

                if (isReal) {
                    syncRealDollarFields();
                } else {
                    syncHiddenFields();
                }
            });
        }

        const realDollarsInput = form.querySelector('input[name="real_dollars"]');
        if (realDollarsInput) {
            realDollarsInput.addEventListener('input', syncRealDollarFields);
        }

        function syncRealDollarFields() {
            const valInput = form.querySelector('input[name="real_dollars"]');
            const isEgreso = document.getElementById('type_egreso').checked;
            let val = Math.abs(parseFloat(valInput.value)) || 0;
            if (isEgreso && val > 0) val = -val;
            // No necesitamos asignar a un campo oculto diferente porque real_dollars ya es el campo del modelo
            // Pero podríamos asegurar que el valor guardado respeta el signo
            valInput.setAttribute('value', val); // Esto es más para visualización en el DOM
        }

        if (hasFeeCheckbox) {
            hasFeeCheckbox.addEventListener('change', function () {
                const isReal = realDollarSwitch.checked;
                bankFeeContainer.style.display = this.checked ? 'block' : 'none';
                
                if (this.checked) {
                    document.getElementById('bcvFeeInputGroup').style.display = isReal ? 'none' : 'block';
                    document.getElementById('realFeeInputGroup').style.display = isReal ? 'block' : 'none';
                }

                syncFeeHiddenFields();
            });
        }

        if (feeDisplay) {
            feeDisplay.addEventListener('input', syncFeeHiddenFields);
        }

        if (currencyToggleBtn) {
            currencyToggleBtn.addEventListener('click', function (e) {
                e.preventDefault();
                toggleAllCurrencies();
            });
        }

        if (feeCurrencyToggleBtn) {
            feeCurrencyToggleBtn.addEventListener('click', function (e) {
                e.preventDefault();
                toggleAllCurrencies();
            });
        }

        function toggleAllCurrencies() {
            const amountVal = parseFloat(amountDisplay.value) || 0;
            const feeVal = parseFloat(feeDisplay.value) || 0;
            const rate = parseFloat(dailyRateField.value) || 1;

            if (currentInputCurrency === 'USD') {
                // De USD a BS
                amountDisplay.value = (amountVal * rate).toFixed(2);
                feeDisplay.value = (feeVal * rate).toFixed(2);
                currentInputCurrency = 'BS';
                currentFeeInputCurrency = 'BS';
            } else {
                // De BS a USD
                amountDisplay.value = (rate !== 0) ? (amountVal / rate).toFixed(2) : 0;
                feeDisplay.value = (rate !== 0) ? (feeVal / rate).toFixed(2) : 0;
                currentInputCurrency = 'USD';
                currentFeeInputCurrency = 'USD';
            }
            updateCurrencyUI();
            updateFeeCurrencyUI();
        }

        if (amountDisplay) {
            amountDisplay.addEventListener('input', function () {
                syncHiddenFields();
                updateValuationVisibility();
            });
        }
        if (dailyRateField) dailyRateField.addEventListener('input', syncHiddenFields);

        if (manualRateSwitch) {
            manualRateSwitch.addEventListener('change', function (e) {
                dailyRateField.disabled = !e.target.checked;
                if (!e.target.checked) loadRateForDate(dateField.value);
            });
            dailyRateField.disabled = !manualRateSwitch.checked;
        }

        if (dateField) {
            dateField.addEventListener('change', function () { loadRateForDate(this.value); });
        }

        if (form) {
            form.addEventListener('submit', function (e) {
                const isReal = document.getElementById('realDollarSwitch').checked;
                const amount = isReal ? (parseFloat(realDollarsInput.value) || 0) : (parseFloat(amountDisplay.value) || 0);
                
                if (amount === 0) {
                    e.preventDefault();
                    alert('El monto de la transacción no puede ser cero.');
                    return;
                }

                if (isReal) {
                    const isEgreso = document.getElementById('type_egreso').checked;
                    let finalVal = Math.abs(parseFloat(realDollarsInput.value));
                    if (isEgreso) finalVal = -finalVal;
                    realDollarsInput.value = finalVal;
                }

                if (dailyRateField) dailyRateField.disabled = false;
            });
        }

        const refInput = document.getElementById('id_reference_number_custom');
        if (refInput) {
            refInput.addEventListener('input', function (e) {
                form.querySelector('[name="reference_number"]').value = e.target.value;
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupListeners);
    } else {
        setupListeners();
    }

    // Otras funciones globales que no dependen del DOM del formulario
    window.viewDetail = function (id) {
        const content = document.getElementById('detailContent');
        if (!content) return;
        content.innerHTML = '<div class="cf-text-center cf-py-4"><div class="cf-spinner"></div></div>';
        CFModal.open('detailModal');
        fetch('/transacciones/detalle/' + id + '/')
            .then(function (r) { return r.text(); })
            .then(function (html) { content.innerHTML = html; })
            .catch(function () {
                content.innerHTML = '<div class="cf-alert cf-alert--danger">Error al cargar los detalles.</div>';
            });
    };

    window.confirmDelete = function (id) {
        if (window.userIsViewer) return;
        const delForm = document.getElementById('deleteForm');
        if (delForm) {
            const next = encodeURIComponent(window.location.pathname + window.location.search);
            delForm.action = '/transacciones/eliminar/' + id + '/?next=' + next;
        }
        CFModal.open('deleteModal');
    };

    window.toggleCustomDates = function (value) {
        const customDiv = document.getElementById('custom_date_inputs');
        if (customDiv) customDiv.style.display = (value === 'custom') ? 'block' : 'none';
    };
}
