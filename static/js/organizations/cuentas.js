function initCuentas(config) {
    var accountsData = [];
    var accountsDataEl = document.getElementById('accountsData');
    if (accountsDataEl) {
        try {
            accountsData = JSON.parse(accountsDataEl.textContent || '[]');
        } catch (e) {
            accountsData = [];
        }
    }

    var form = document.getElementById('accountForm');
    var currencyField = document.getElementById('id_account_currency');
    var rateFieldWrap = document.getElementById('rateFieldWrap');
    var dailyRateField = form.querySelector('[name="daily_rate"]');
    var initialBalanceLabel = document.getElementById('initialBalanceLabel');

    function currentCurrency() {
        return currencyField ? currencyField.value : 'BS';
    }

    var BALANCE_LABELS = {
        USD: 'Saldo inicial (USD)',
        EUR: 'Saldo inicial (€)',
        BS: 'Saldo inicial (Bs.)',
    };

    function updateCurrencyUI() {
        var currency = currentCurrency();
        if (initialBalanceLabel) {
            initialBalanceLabel.textContent = BALANCE_LABELS[currency] || BALANCE_LABELS.BS;
        }
        // Solo las cuentas en bolívares usan la tasa BCV: las de moneda
        // extranjera guardan su saldo directamente en su propia moneda.
        if (rateFieldWrap) {
            rateFieldWrap.classList.toggle('cf-hidden', currency !== 'BS');
        }
        if (dailyRateField) {
            dailyRateField.value = config.bcvRate;
            dailyRateField.readOnly = true;
        }
    }

    window.resetForm = function () {
        if (window.userIsViewer) return;
        form.reset();
        form.action = config.crearUrl;
        document.getElementById('modalTitle').innerText = 'Nueva Cuenta';
        document.getElementById('initialAmountFields').classList.remove('cf-hidden');
        if (currencyField) currencyField.disabled = false;
        if (dailyRateField) dailyRateField.value = config.bcvRate;
        updateCurrencyUI();
    };

    window.editAccount = function (id) {
        if (window.userIsViewer) return;
        var account = accountsData.find(function (item) { return item.id === id; });
        if (!account) return;

        form.action = '/cuentas/guardar/' + id + '/';
        document.getElementById('modalTitle').innerText = 'Editar Cuenta';
        // El saldo inicial solo se pide al crear la cuenta.
        document.getElementById('initialAmountFields').classList.add('cf-hidden');

        if (currencyField) {
            currencyField.value = account.currency;
            currencyField.disabled = true;
        }
        var nameField = form.querySelector('[name="name"]');
        if (nameField) nameField.value = account.name || '';

        updateCurrencyUI();
        CFModal.open('accountModal');
    };

    window.confirmDelete = function (id) {
        if (window.userIsViewer) return;
        document.getElementById('deleteForm').action = '/cuentas/eliminar/' + id + '/';
        CFModal.open('deleteModal');
    };

    if (currencyField) {
        currencyField.addEventListener('change', updateCurrencyUI);
    }

    if (form) {
        form.addEventListener('submit', function () {
            // El select deshabilitado no se envía: se rehabilita justo antes.
            if (currencyField && currencyField.disabled) {
                currencyField.disabled = false;
            }
        });
    }

    updateCurrencyUI();
}
