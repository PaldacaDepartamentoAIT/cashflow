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
    var bankSelect = document.getElementById('id_bank_select');
    var bankCodeField = document.getElementById('id_bank_code');
    var bankNameField = document.getElementById('id_bank_name');
    var rifField = form.querySelector('[name="rif"]');
    var rateFieldWrap = document.getElementById('rateFieldWrap');
    var dailyRateField = form.querySelector('[name="daily_rate"]');
    var initialBalanceLabel = document.getElementById('initialBalanceLabel');

    function currentCurrency() {
        return currencyField ? currencyField.value : 'BS';
    }

    function updateBankSelectUrls() {
        if (!bankSelect) return;
        bankSelect.dataset.banksUrl = currentCurrency() === 'BS' ? config.bancosBsUrl : config.bancosUsdUrl;
    }

    function refreshBankSelect(selectedCode, selectedName) {
        updateBankSelectUrls();
        if (currentCurrency() === 'BS') {
            return CFBanks.populateBsSelect(bankSelect, selectedCode || '').then(function () {
                CFBanks.bindBsSelect(bankSelect, bankNameField);
            });
        }
        return CFBanks.populateUsdSelect(bankSelect, selectedName || bankNameField.value || '').then(function () {
            CFBanks.bindUsdSelect(bankSelect, bankNameField);
        });
    }

    function syncBankHiddenFields() {
        if (!bankSelect) return;
        if (currentCurrency() === 'BS') {
            var option = bankSelect.options[bankSelect.selectedIndex];
            if (bankCodeField) bankCodeField.value = bankSelect.value;
            if (bankNameField) bankNameField.value = option ? (option.dataset.bankName || '') : '';
        } else {
            if (bankCodeField) bankCodeField.value = '';
            if (bankNameField) bankNameField.value = bankSelect.value;
        }
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
        refreshBankSelect(bankCodeField ? bankCodeField.value : '', bankNameField ? bankNameField.value : '');
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
        document.getElementById('initialAmountFields').classList.add('cf-hidden');

        if (currencyField) {
            currencyField.value = account.currency;
            currencyField.disabled = true;
        }
        if (bankCodeField) bankCodeField.value = account.bank_code || '';
        if (bankNameField) bankNameField.value = account.bank_name || '';
        form.querySelector('[name="rif"]').value = account.rif || '';
        form.querySelector('[name="account_number"]').value = account.account_number || '';
        form.querySelector('[name="holder"]').value = account.holder || '';
        if (form.querySelector('[name="name"]')) {
            form.querySelector('[name="name"]').value = account.name || '';
        }

        refreshBankSelect(account.bank_code, account.bank_name).then(function () {
            if (account.currency === 'BS' && bankSelect) bankSelect.value = account.bank_code || '';
            if (account.currency === 'USD' && bankSelect) bankSelect.value = account.bank_name || '';
            syncBankHiddenFields();
        });

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

    if (bankSelect) {
        bankSelect.addEventListener('change', syncBankHiddenFields);
    }

    if (form) {
        form.addEventListener('submit', function () {
            syncBankHiddenFields();
            if (currencyField && currencyField.disabled) {
                currencyField.disabled = false;
            }
        });
    }

    updateCurrencyUI();
}
