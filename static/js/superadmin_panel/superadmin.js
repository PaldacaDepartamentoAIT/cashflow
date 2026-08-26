function initSuperadminOrgs(config) {
    var wizardStep = 1;
    var totalSteps = 3;
    var track = document.getElementById('orgWizardTrack');
    var stepsBar = document.getElementById('orgWizardSteps');
    var prevBtn = document.getElementById('orgWizardPrevBtn');
    var nextBtn = document.getElementById('orgWizardNextBtn');
    var submitBtn = document.getElementById('orgWizardSubmitBtn');
    var wizardForm = document.getElementById('orgWizardForm');
    var accountsBsList = document.getElementById('wizardAccountsBsList');
    var accountsUsdList = document.getElementById('wizardAccountsUsdList');
    var addBsAccountBtn = document.getElementById('wizardAddBsAccountBtn');
    var addUsdAccountBtn = document.getElementById('wizardAddUsdAccountBtn');
    var accountsEurList = document.getElementById('wizardAccountsEurList');
    var addEurAccountBtn = document.getElementById('wizardAddEurAccountBtn');

    function showError(el, msg) {
        if (!el) return;
        if (msg) {
            el.textContent = msg;
            el.classList.remove('cf-hidden');
        } else {
            el.textContent = '';
            el.classList.add('cf-hidden');
        }
    }

    function switchAccountTab(tabName) {
        document.querySelectorAll('[data-account-tab]').forEach(function (btn) {
            var active = btn.getAttribute('data-account-tab') === tabName;
            btn.classList.toggle('is-active', active);
        });
        document.querySelectorAll('[data-account-panel]').forEach(function (panel) {
            panel.classList.toggle('is-active', panel.getAttribute('data-account-panel') === tabName);
        });
    }

    function buildAccountRow(currency) {
        var row = document.createElement('div');
        row.className = 'sa-wizard-account-row sa-wizard-account-row--full';
        var isBs = currency === 'BS';
        var BALANCE_LABELS = { BS: 'Saldo inicial (Bs.)', USD: 'Saldo inicial (USD)', EUR: 'Saldo inicial (EUR)' };
        var balanceLabel = BALANCE_LABELS[currency] || BALANCE_LABELS.BS;
        row.innerHTML =
            '<input type="hidden" name="account_currency" value="' + currency + '">' +
            '<input type="hidden" name="account_bank_name" class="sa-account-bank-name" value="">' +
            '<div class="sa-wizard-account-row__fields sa-wizard-account-row__fields--wide">' +
            '<div class="cf-form-group cf-mb-0">' +
            '<label class="cf-label cf-fs-sm">Banco</label>' +
            '<select class="cf-select cf-select--sm sa-account-bank-select" data-banks-url="' +
            (isBs ? config.bancosBsUrl : config.bancosUsdUrl) + '" data-currency="' + currency + '"></select>' +
            '</div>' +
            '<div class="cf-form-group cf-mb-0">' +
            '<label class="cf-label cf-fs-sm">RIF</label>' +
            '<input type="text" name="account_rif" class="cf-input cf-input--sm sa-account-rif" placeholder="J-12345678-9">' +
            '</div>' +
            '<div class="cf-form-group cf-mb-0">' +
            '<label class="cf-label cf-fs-sm">Nº cuenta</label>' +
            '<input type="text" name="account_number" class="cf-input cf-input--sm" placeholder="20 dígitos" inputmode="numeric">' +
            '</div>' +
            '<div class="cf-form-group cf-mb-0">' +
            '<label class="cf-label cf-fs-sm">Titular</label>' +
            '<input type="text" name="account_holder" class="cf-input cf-input--sm" placeholder="Nombre del titular">' +
            '</div>' +
            '<div class="cf-form-group cf-mb-0">' +
            '<label class="cf-label cf-fs-sm">' + balanceLabel + '</label>' +
            '<input type="number" name="account_balance" class="cf-input cf-input--sm" step="0.01" min="0" placeholder="0.00">' +
            '</div>' +
            (isBs ? '<input type="hidden" name="account_bank_code" class="sa-account-bank-code" value="">' :
                '<input type="hidden" name="account_bank_code" value="">') +
            '</div>' +
            '<button type="button" class="sa-wizard-account-remove" title="Quitar cuenta"><i class="fa-solid fa-xmark"></i></button>';

        var listEl = isBs ? accountsBsList : (currency === 'EUR' ? accountsEurList : accountsUsdList);
        var bankSelect = row.querySelector('.sa-account-bank-select');
        var bankNameInput = row.querySelector('.sa-account-bank-name');
        var bankCodeInput = row.querySelector('.sa-account-bank-code');
        var rifInput = row.querySelector('.sa-account-rif');

        if (isBs) {
            CFBanks.populateBsSelect(bankSelect).then(function () {
                CFBanks.bindBsSelect(bankSelect, bankNameInput);
            });
            bankSelect.addEventListener('change', function () {
                if (bankCodeInput) bankCodeInput.value = bankSelect.value;
            });
        } else {
            CFBanks.populateUsdSelect(bankSelect).then(function () {
                CFBanks.bindUsdSelect(bankSelect, bankNameInput);
            });
        }

        row.querySelector('.sa-wizard-account-remove').addEventListener('click', function () {
            if (listEl.querySelectorAll('.sa-wizard-account-row').length > 1) {
                row.remove();
            }
        });

        return row;
    }

    function resetAccountsLists() {
        accountsBsList.innerHTML = '';
        accountsUsdList.innerHTML = '';
        accountsBsList.appendChild(buildAccountRow('BS'));
        accountsUsdList.appendChild(buildAccountRow('USD'));
        if (accountsEurList) {
            accountsEurList.innerHTML = '';
            accountsEurList.appendChild(buildAccountRow('EUR'));
        }
        switchAccountTab('bs');
    }

    function accountRowIsFilled(row) {
        return row.querySelector('[name="account_rif"]').value.trim() ||
            row.querySelector('[name="account_number"]').value.trim() ||
            row.querySelector('[name="account_holder"]').value.trim() ||
            row.querySelector('.sa-account-bank-select').value;
    }

    function validateAccountRow(row, currencyLabel) {
        var bankSelect = row.querySelector('.sa-account-bank-select');
        var bankNameInput = row.querySelector('.sa-account-bank-name');
        if (bankSelect.value) {
            if (bankSelect.dataset.currency === 'BS') {
                var option = bankSelect.options[bankSelect.selectedIndex];
                bankNameInput.value = option.dataset.bankName || '';
                row.querySelector('.sa-account-bank-code').value = bankSelect.value;
            } else {
                bankNameInput.value = bankSelect.value;
            }
        }
        if (!bankSelect.value) return currencyLabel + ': seleccione un banco de la lista antes de continuar.';
        if (!row.querySelector('[name="account_rif"]').value.trim()) return currencyLabel + ': ingrese el RIF del titular de la cuenta.';
        if (!row.querySelector('[name="account_number"]').value.trim()) return currencyLabel + ': ingrese el número de cuenta bancaria.';
        if (!row.querySelector('[name="account_holder"]').value.trim()) return currencyLabel + ': ingrese el nombre del titular de la cuenta.';
        return '';
    }

    function updateWizardUI() {
        track.setAttribute('data-step', String(wizardStep));
        var viewport = track.parentElement;
        var slideOffset = viewport ? (wizardStep - 1) * viewport.offsetWidth : 0;
        track.style.transform = slideOffset ? 'translateX(-' + slideOffset + 'px)' : '';

        stepsBar.querySelectorAll('.sa-wizard-step').forEach(function (el) {
            var step = parseInt(el.getAttribute('data-step'), 10);
            el.classList.toggle('is-active', step === wizardStep);
            el.classList.toggle('is-done', step < wizardStep);
        });

        prevBtn.classList.toggle('cf-hidden', wizardStep === 1);
        nextBtn.classList.toggle('cf-hidden', wizardStep === totalSteps);
        submitBtn.classList.toggle('cf-hidden', wizardStep !== totalSteps);
    }

    function validateStep1() {
        var nameInput = wizardForm.querySelector('[name="name"]');
        var err = document.getElementById('wizardNameError');
        var value = nameInput.value.trim();
        if (value.length < 2) {
            showError(err, 'Ingrese un nombre de organización válido: debe tener al menos 2 caracteres.');
            nameInput.focus();
            return false;
        }
        showError(err, '');
        return true;
    }

    function validateStep2() {
        var err = document.getElementById('wizardAccountsError');
        var rows = []
            .concat(Array.from(accountsBsList.querySelectorAll('.sa-wizard-account-row')))
            .concat(Array.from(accountsUsdList.querySelectorAll('.sa-wizard-account-row')))
            .concat(accountsEurList ? Array.from(accountsEurList.querySelectorAll('.sa-wizard-account-row')) : []);
        var filledRows = rows.filter(accountRowIsFilled);

        if (filledRows.length === 0) {
            showError(err, 'Agregue al menos una cuenta en bolívares, dólares o euros antes de continuar al siguiente paso.');
            return false;
        }

        for (var i = 0; i < filledRows.length; i++) {
            var row = filledRows[i];
            var rowCurrency = row.querySelector('[name="account_currency"]').value;
            var ROW_LABELS = { BS: 'Cuenta Bs.', USD: 'Cuenta USD', EUR: 'Cuenta EUR' };
            var rowError = validateAccountRow(row, ROW_LABELS[rowCurrency] || ROW_LABELS.BS);
            if (rowError) {
                showError(err, rowError);
                switchAccountTab(rowCurrency.toLowerCase());
                return false;
            }
        }

        rows.forEach(function (row) {
            if (!accountRowIsFilled(row)) {
                row.remove();
            }
        });

        showError(err, '');
        return true;
    }

    function validateStep3() {
        var err = document.getElementById('wizardAdminError');
        var checked = wizardForm.querySelectorAll('[name="org_users"]:checked').length;
        var username = (wizardForm.querySelector('[name="new_user_username"]') || {}).value || '';
        username = username.trim();

        if (checked === 0 && !username) {
            showError(err, 'Asigne al menos un administrador a la organización: seleccione un usuario existente de la lista o complete el formulario de usuario nuevo.');
            return false;
        }

        if (username) {
            var email = (wizardForm.querySelector('[name="new_user_email"]') || {}).value || '';
            var p1 = (wizardForm.querySelector('[name="new_user_password1"]') || {}).value || '';
            var p2 = (wizardForm.querySelector('[name="new_user_password2"]') || {}).value || '';
            if (!email.trim() || !p1 || !p2) {
                showError(err, 'Complete el email y ambas contraseñas del nuevo usuario antes de continuar.');
                switchUserTab('create');
                return false;
            }
            if (p1 !== p2) {
                showError(err, 'Las contraseñas del nuevo usuario no coinciden: verifique que ambos campos contengan exactamente la misma contraseña.');
                switchUserTab('create');
                return false;
            }
        }

        showError(err, '');
        return true;
    }

    function showWizardFormErrors(errors) {
        var box = document.getElementById('wizardFormErrors');
        if (!box) return;
        if (!errors || !errors.length) {
            box.innerHTML = '';
            box.classList.add('cf-hidden');
            return;
        }
        box.innerHTML = errors.map(function (msg) {
            return '<p>' + msg + '</p>';
        }).join('');
        box.classList.remove('cf-hidden');
        box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function validateAllSteps() {
        if (!validateStep1()) return { valid: false, step: 1 };
        if (!validateStep2()) return { valid: false, step: 2 };
        if (!validateStep3()) return { valid: false, step: 3 };
        return { valid: true, step: totalSteps };
    }

    function openOrgWizardView() {
        var listView = document.getElementById('orgListView');
        var wizardView = document.getElementById('orgWizardView');
        if (listView) listView.classList.add('cf-hidden');
        if (wizardView) {
            wizardView.classList.remove('cf-hidden');
            wizardView.setAttribute('aria-hidden', 'false');
        }
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function closeOrgWizard() {
        window.resetOrgWizard();
        var listView = document.getElementById('orgListView');
        var wizardView = document.getElementById('orgWizardView');
        if (wizardView) {
            wizardView.classList.add('cf-hidden');
            wizardView.setAttribute('aria-hidden', 'true');
        }
        if (listView) listView.classList.remove('cf-hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    window.openOrgWizard = function () {
        window.resetOrgWizard();
        openOrgWizardView();
    };

    function switchUserTab(tabName) {
        document.querySelectorAll('.sa-wizard-user-tab').forEach(function (btn) {
            var active = btn.getAttribute('data-user-tab') === tabName;
            btn.classList.toggle('is-active', active);
            btn.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        document.querySelectorAll('.sa-wizard-user-panel').forEach(function (panel) {
            panel.classList.toggle('is-active', panel.getAttribute('data-user-panel') === tabName);
        });
    }

    window.resetOrgWizard = function () {
        wizardStep = 1;
        wizardForm.reset();
        resetAccountsLists();
        showError(document.getElementById('wizardNameError'), '');
        showError(document.getElementById('wizardAccountsError'), '');
        showError(document.getElementById('wizardAdminError'), '');
        showWizardFormErrors([]);
        switchUserTab('assign');
        updateWizardUI();
        if (submitBtn) submitBtn.disabled = false;
    };

    window.editOrg = function (id, name) {
        var form = document.getElementById('orgEditForm');
        form.action = config.editarUrlTemplate.replace('{id}', id);
        document.getElementById('orgEditModalTitle').innerText = 'Editar Organización';
        form.querySelector('[name="name"]').value = name;
        CFModal.open('orgEditModal');
    };

    window.openAccessModal = function (orgId, orgName, userIds) {
        document.getElementById('accessModalTitle').innerText = 'Accesos — ' + orgName;
        document.getElementById('accessForm').action = config.accesosUrlTemplate.replace('{id}', orgId);
        document.querySelectorAll('.sa-access-checkbox').forEach(function (cb) {
            cb.checked = userIds.indexOf(parseInt(cb.value, 10)) !== -1;
        });
        CFModal.open('accessModal');
    };

    window.confirmDeleteOrg = function (orgId, orgName) {
        document.getElementById('deleteOrgName').innerText = orgName;
        document.getElementById('deleteOrgForm').action = config.eliminarUrlTemplate.replace('{id}', orgId);
        CFModal.open('deleteOrgModal');
    };

    if (addBsAccountBtn) {
        addBsAccountBtn.addEventListener('click', function () {
            accountsBsList.appendChild(buildAccountRow('BS'));
        });
    }

    if (addUsdAccountBtn) {
        addUsdAccountBtn.addEventListener('click', function () {
            accountsUsdList.appendChild(buildAccountRow('USD'));
        });
    }

    if (addEurAccountBtn) {
        addEurAccountBtn.addEventListener('click', function () {
            accountsEurList.appendChild(buildAccountRow('EUR'));
        });
    }

    document.querySelectorAll('[data-account-tab]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            switchAccountTab(btn.getAttribute('data-account-tab'));
        });
    });

    document.querySelectorAll('.sa-wizard-user-tab').forEach(function (btn) {
        btn.addEventListener('click', function () {
            switchUserTab(btn.getAttribute('data-user-tab'));
        });
    });

    if (nextBtn) {
        nextBtn.addEventListener('click', function () {
            if (wizardStep === 1 && !validateStep1()) return;
            if (wizardStep === 2 && !validateStep2()) return;
            if (wizardStep < totalSteps) {
                wizardStep += 1;
                updateWizardUI();
            }
        });
    }

    if (prevBtn) {
        prevBtn.addEventListener('click', function () {
            if (wizardStep > 1) {
                wizardStep -= 1;
                updateWizardUI();
            }
        });
    }

    if (wizardForm) {
        wizardForm.addEventListener('submit', function (e) {
            e.preventDefault();
            showWizardFormErrors([]);

            var result = validateAllSteps();
            if (!result.valid) {
                wizardStep = result.step;
                updateWizardUI();
                return;
            }

            submitBtn.disabled = true;
            fetch(config.crearUrl, {
                method: 'POST',
                body: new FormData(wizardForm),
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            })
                .then(function (response) {
                    return response.json()
                        .then(function (data) {
                            return { ok: response.ok, data: data };
                        })
                        .catch(function () {
                            return {
                                ok: false,
                                data: { errors: ['No se pudo procesar la respuesta del servidor.'] },
                            };
                        });
                })
                .then(function (result) {
                    if (result.ok && result.data.ok) {
                        window.location.href = result.data.redirect;
                        return;
                    }
                    var errors = (result.data && result.data.errors) || ['No se pudo crear la organización. Verifique los datos ingresados en cada paso e intente de nuevo.'];
                    showWizardFormErrors(errors);
                    wizardStep = totalSteps;
                    updateWizardUI();
                })
                .catch(function () {
                    showWizardFormErrors(['Error de conexión. Intente de nuevo.']);
                    wizardStep = totalSteps;
                    updateWizardUI();
                })
                .finally(function () {
                    submitBtn.disabled = false;
                });
        });
    }

    var wizardCancelBtn = document.getElementById('orgWizardCancelBtn');
    var wizardBackBtn = document.getElementById('orgWizardBackBtn');
    if (wizardCancelBtn) {
        wizardCancelBtn.addEventListener('click', closeOrgWizard);
    }
    if (wizardBackBtn) {
        wizardBackBtn.addEventListener('click', closeOrgWizard);
    }

    resetAccountsLists();
    updateWizardUI();

    var wizardView = document.getElementById('orgWizardView');
    window.addEventListener('resize', function () {
        if (wizardView && !wizardView.classList.contains('cf-hidden')) {
            updateWizardUI();
        }
    });
}

function initSuperadminUsers(config) {
    window.resetUserCreateForm = function () {
        const form = document.getElementById('userCreateForm');
        form.reset();
        form.action = config.crearUrl;
    };

    window.editUser = function (id, username, firstName, lastName, email, isActive, isStaff, isSuperuser, role) {
        const form = document.getElementById('userEditForm');
        form.action = config.editarUrlTemplate.replace('{id}', id);
        document.getElementById('userEditModalTitle').innerText = 'Editar — ' + username;
        form.querySelector('[name="username"]').value = username;
        form.querySelector('[name="first_name"]').value = firstName;
        form.querySelector('[name="last_name"]').value = lastName;
        form.querySelector('[name="email"]').value = email;
        form.querySelector('[name="is_active"]').checked = isActive;
        form.querySelector('[name="is_staff"]').checked = isStaff;
        form.querySelector('[name="is_superuser"]').checked = isSuperuser;
        form.querySelector('[name="edit"]').value = role || 'Editor';
        form.querySelector('[name="new_password"]').value = '';
        form.querySelector('[name="new_password_confirm"]').value = '';

        const superFlag = document.getElementById('editSuperuserFlag');
        const superCheckbox = form.querySelector('[name="is_superuser"]');
        if (id === config.currentUserId) {
            superCheckbox.disabled = true;
            superFlag.title = 'No puede quitarse el rol de superadministrador a sí mismo.';
        } else {
            superCheckbox.disabled = false;
            superFlag.title = '';
        }

        CFModal.open('userEditModal');
    };

    window.confirmDeleteUser = function (userId, username) {
        document.getElementById('deleteUserName').innerText = username;
        document.getElementById('deleteUserForm').action = config.eliminarUrlTemplate.replace('{id}', userId);
        CFModal.open('deleteUserModal');
    };
}

function initSuperadminBcvRates(config) {
    var state = {
        year: config.calendarYear,
        month: config.calendarMonth,
        selectedDate: config.selectedDate,
        datesWithRates: new Set(config.datesWithRates || []),
        today: config.today,
    };

    var MONTHS = [
        'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
    ];
    var WEEKDAYS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];

    var gridEl = document.getElementById('bcvCalGrid');
    var titleEl = document.getElementById('bcvCalTitle');
    var dateTextEl = document.getElementById('bcvDateText');
    var formDateEl = document.getElementById('bcvFormDate');
    var usdBody = document.getElementById('bcvUsdBody');
    var eurBody = document.getElementById('bcvEurBody');
    var usdFoot = document.getElementById('bcvUsdFoot');
    var eurFoot = document.getElementById('bcvEurFoot');
    var usdTile = document.getElementById('bcvUsdTile');
    var eurTile = document.getElementById('bcvEurTile');

    function pad(n) {
        return n < 10 ? '0' + n : String(n);
    }

    function toIso(y, m, d) {
        return y + '-' + pad(m) + '-' + pad(d);
    }

    function parseIso(iso) {
        var p = iso.split('-');
        return { y: parseInt(p[0], 10), m: parseInt(p[1], 10), d: parseInt(p[2], 10) };
    }

    function formatDateLabel(iso) {
        var p = parseIso(iso);
        var dt = new Date(p.y, p.m - 1, p.d);
        return WEEKDAYS[dt.getDay()] + ', ' + p.d + ' de ' + MONTHS[p.m - 1] + ' de ' + p.y;
    }

    function updateUrl(iso) {
        var url = new URL(window.location.href);
        url.searchParams.set('date', iso);
        window.history.replaceState({}, '', url.toString());
    }

    function renderRateTile(bodyEl, footEl, tileEl, rate, currency) {
        tileEl.classList.remove('is-updating');
        tileEl.classList.add('is-loaded');
        setTimeout(function () { tileEl.classList.remove('is-loaded'); }, 300);

        if (rate) {
            bodyEl.innerHTML =
                '<div class="sa-bcv-rate-value">' + rate.rate + '</div>' +
                '<div class="sa-bcv-rate-unit">Bs.</div>' +
                '<p class="sa-bcv-rate-meta">Actualizado ' + rate.fetched_at + '</p>';
            footEl.hidden = false;
            footEl.innerHTML =
                '<form method="post" action="' + config.eliminarUrlTemplate.replace('{id}', rate.id) + '" class="sa-bcv-delete-form" data-currency="' + currency + '">' +
                '<input type="hidden" name="csrfmiddlewaretoken" value="' + config.csrfToken + '">' +
                '<button type="submit" class="sa-bcv-icon-btn sa-bcv-icon-btn--danger" title="Eliminar ' + currency + '" onclick="return confirm(\'¿Eliminar tasa ' + currency + ' de esta fecha?\')">' +
                '<i class="fa-solid fa-trash"></i></button></form>';
        } else {
            bodyEl.innerHTML =
                '<div class="sa-bcv-rate-empty">' +
                '<i class="fa-solid fa-circle-minus"></i><span>Sin tasa</span></div>';
            footEl.hidden = true;
            footEl.innerHTML = '';
        }
    }

    function applyRatesData(data) {
        state.selectedDate = data.date;
        dateTextEl.textContent = formatDateLabel(data.date);
        formDateEl.value = data.date;
        usdTile.classList.add('is-updating');
        eurTile.classList.add('is-updating');
        renderRateTile(usdBody, usdFoot, usdTile, data.usd, 'USD');
        renderRateTile(eurBody, eurFoot, eurTile, data.eur, 'EUR');
        updateUrl(data.date);
        renderCalendar();
    }

    function fetchRates(iso) {
        usdTile.classList.add('is-updating');
        eurTile.classList.add('is-updating');
        fetch(config.apiUrl + '?date=' + encodeURIComponent(iso), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
            .then(function (r) { return r.json(); })
            .then(applyRatesData)
            .catch(function () {
                usdTile.classList.remove('is-updating');
                eurTile.classList.remove('is-updating');
            });
    }

    function fetchMonthMarkers(year, month) {
        return fetch(config.apiUrl + '?year=' + year + '&month=' + month, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                state.datesWithRates = new Set(data.dates_with_rates || []);
            });
    }

    function renderCalendar() {
        titleEl.textContent = MONTHS[state.month - 1] + ' ' + state.year;

        var firstDay = new Date(state.year, state.month - 1, 1);
        var startOffset = (firstDay.getDay() + 6) % 7;
        var daysInMonth = new Date(state.year, state.month, 0).getDate();
        var prevMonthDays = new Date(state.year, state.month - 1, 0).getDate();

        gridEl.innerHTML = '';
        var cellCount = 0;

        for (var i = startOffset - 1; i >= 0; i--) {
            var pd = prevMonthDays - i;
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'sa-bcv-cal-day sa-bcv-cal-day--muted';
            btn.textContent = pd;
            btn.disabled = true;
            gridEl.appendChild(btn);
            cellCount++;
        }

        for (var d = 1; d <= daysInMonth; d++) {
            var iso = toIso(state.year, state.month, d);
            var dayBtn = document.createElement('button');
            dayBtn.type = 'button';
            dayBtn.className = 'sa-bcv-cal-day';
            dayBtn.textContent = d;
            dayBtn.dataset.date = iso;

            if (iso === state.today) dayBtn.classList.add('sa-bcv-cal-day--today');
            if (iso === state.selectedDate) dayBtn.classList.add('sa-bcv-cal-day--selected');
            if (state.datesWithRates.has(iso)) dayBtn.classList.add('sa-bcv-cal-day--has-rate');

            dayBtn.addEventListener('click', function () {
                fetchRates(this.dataset.date);
            });
            gridEl.appendChild(dayBtn);
            cellCount++;
        }

        while (cellCount % 7 !== 0) {
            var filler = document.createElement('button');
            filler.type = 'button';
            filler.className = 'sa-bcv-cal-day sa-bcv-cal-day--muted';
            filler.disabled = true;
            gridEl.appendChild(filler);
            cellCount++;
        }
    }

    document.getElementById('bcvCalPrev').addEventListener('click', function () {
        state.month -= 1;
        if (state.month < 1) {
            state.month = 12;
            state.year -= 1;
        }
        fetchMonthMarkers(state.year, state.month).then(renderCalendar);
    });

    document.getElementById('bcvCalNext').addEventListener('click', function () {
        state.month += 1;
        if (state.month > 12) {
            state.month = 1;
            state.year += 1;
        }
        fetchMonthMarkers(state.year, state.month).then(renderCalendar);
    });

    document.getElementById('bcvCalToday').addEventListener('click', function () {
        var p = parseIso(config.today);
        state.year = p.y;
        state.month = p.m;
        fetchMonthMarkers(state.year, state.month).then(function () {
            renderCalendar();
            fetchRates(config.today);
        });
    });

    document.querySelectorAll('.sa-bcv-history-item').forEach(function (item) {
        item.addEventListener('click', function () {
            var iso = this.dataset.bcvDate;
            var p = parseIso(iso);
            state.year = p.y;
            state.month = p.m;
            fetchMonthMarkers(state.year, state.month).then(function () {
                renderCalendar();
                fetchRates(iso);
            });
        });
    });

    dateTextEl.textContent = formatDateLabel(state.selectedDate);
    renderCalendar();
}
