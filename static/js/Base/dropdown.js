/**
 * CashFlow Dropdown — reemplazo de bootstrap dropdown
 */
(function () {
    function resetMultiselectSearch(dropdownEl) {
        const searchInput = dropdownEl.querySelector('.cf-dropdown-multiselect__search input');
        if (searchInput && searchInput.value) {
            searchInput.value = '';
            searchInput.dispatchEvent(new Event('input'));
        }
    }

    function closeAll(except) {
        document.querySelectorAll('.cf-dropdown.is-open').forEach(function (el) {
            if (el !== except) {
                el.classList.remove('is-open');
                resetMultiselectSearch(el);
            }
        });
    }

    // Filtra las opciones de un menú cf-dropdown-multiselect según lo escrito en su buscador.
    function attachMultiselectSearch(menuEl) {
        const searchInput = menuEl.querySelector('.cf-dropdown-multiselect__search input');
        if (!searchInput) return;
        searchInput.addEventListener('click', function (e) { e.stopPropagation(); });
        searchInput.addEventListener('input', function () {
            const term = searchInput.value.trim().toLowerCase();
            menuEl.querySelectorAll('.cf-dropdown-multiselect__item:not(.cf-dropdown-multiselect__select-all)').forEach(function (item) {
                const text = item.textContent.trim().toLowerCase();
                item.classList.toggle('cf-hidden', term !== '' && !text.includes(term));
            });
        });
    }

    // Checkbox "Seleccionar todas": solo se activa si el menú incluye ese control (filtros de transacciones).
    function attachSelectAll(menuEl) {
        const selectAll = menuEl.querySelector('.cf-dropdown-multiselect__select-all-checkbox');
        if (!selectAll || selectAll._cfBound) return;
        selectAll._cfBound = true;

        function itemCheckboxes() {
            return Array.from(menuEl.querySelectorAll('.cf-dropdown-multiselect__item:not(.cf-dropdown-multiselect__select-all) input[type="checkbox"]'));
        }

        function syncState() {
            const boxes = itemCheckboxes();
            const checkedCount = boxes.filter(function (cb) { return cb.checked; }).length;
            selectAll.checked = boxes.length > 0 && checkedCount === boxes.length;
            selectAll.indeterminate = checkedCount > 0 && checkedCount < boxes.length;
        }

        itemCheckboxes().forEach(function (cb) { cb.addEventListener('change', syncState); });
        syncState();

        selectAll.addEventListener('change', function () {
            const shouldCheck = selectAll.checked;
            selectAll.indeterminate = false;
            let lastChanged = null;
            itemCheckboxes().forEach(function (cb) {
                if (cb.checked !== shouldCheck) {
                    cb.checked = shouldCheck;
                    lastChanged = cb;
                }
            });
            // Un solo evento sintético (en la última casilla tocada) basta para disparar
            // los listeners existentes, que ya leen el formulario completo.
            if (lastChanged) {
                lastChanged.dispatchEvent(new Event('input', { bubbles: true }));
                lastChanged.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });
    }

    function init() {
        document.addEventListener('click', function (e) {
            const toggle = e.target.closest('[data-cf-dropdown]');
            if (toggle) {
                e.preventDefault();
                e.stopPropagation();
                const dropdown = toggle.closest('.cf-dropdown');
                if (dropdown) {
                    const isOpen = dropdown.classList.contains('is-open');
                    closeAll();
                    if (!isOpen) {
                        dropdown.classList.add('is-open');
                        const searchInput = dropdown.querySelector('.cf-dropdown-multiselect__search input');
                        if (searchInput) setTimeout(function () { searchInput.focus(); }, 0);
                    }
                }
                return;
            }

            if (!e.target.closest('.cf-dropdown')) {
                closeAll();
            }
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeAll();
        });

        // Dropdowns de filtro (renderizados por el servidor): buscador + "seleccionar todas".
        document.querySelectorAll('#categoryFilterDropdown .cf-dropdown-multiselect__menu').forEach(function (menuEl) {
            attachMultiselectSearch(menuEl);
            attachSelectAll(menuEl);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.attachDropdownMultiselectSearch = attachMultiselectSearch;
})();

window.initFormCategoriesDropdown = function(selectElement, dropdownEl, initialColorsMap) {
    if (!selectElement || !dropdownEl) return;
    const toggleBtn = dropdownEl.querySelector('.cf-dropdown-multiselect__toggle');
    const menuEl = dropdownEl.querySelector('.cf-dropdown-multiselect__menu');
    if (!toggleBtn || !menuEl) return;

    const toggleText = toggleBtn.querySelector('.cf-dropdown-multiselect__selected-text');
    let colorsMap = initialColorsMap || {};

    function updateText() {
        const checked = [];
        menuEl.querySelectorAll('input[type="checkbox"]:checked').forEach(cb => {
            const badge = cb.nextElementSibling;
            checked.push(badge ? badge.textContent.trim() : '');
        });
        if (checked.length === 0) {
            toggleText.textContent = "Seleccionar categorías";
        } else if (checked.length === 1) {
            toggleText.textContent = checked[0];
        } else {
            toggleText.textContent = `${checked.length} seleccionadas`;
        }
    }

    function rebuild(newColorsMap) {
        if (newColorsMap) {
            colorsMap = newColorsMap;
        }
        menuEl.innerHTML = '';

        const searchWrap = document.createElement('div');
        searchWrap.className = 'cf-dropdown-multiselect__search';
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.className = 'cf-input cf-input--sm';
        searchInput.placeholder = 'Buscar categoría...';
        searchInput.autocomplete = 'off';
        searchWrap.appendChild(searchInput);
        menuEl.appendChild(searchWrap);

        if (selectElement.options.length === 0) {
            const noCats = document.createElement('div');
            noCats.className = 'cf-text-muted cf-fs-sm cf-p-2';
            noCats.textContent = 'Sin categorías disponibles';
            menuEl.appendChild(noCats);
            window.attachDropdownMultiselectSearch(menuEl);
            updateText();
            return;
        }

        Array.from(selectElement.options).forEach(opt => {
            if (!opt.value) return;

            const label = document.createElement('label');
            label.className = 'cf-dropdown-multiselect__item';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'cf-checkbox';
            checkbox.value = opt.value;
            checkbox.checked = opt.selected;

            checkbox.addEventListener('change', function() {
                opt.selected = checkbox.checked;
                selectElement.dispatchEvent(new Event('change', { bubbles: true }));
                updateText();
            });

            const badge = document.createElement('span');
            badge.className = 'cf-badge cf-badge--pill';
            badge.textContent = opt.textContent;
            badge.style.border = 'none';
            badge.style.padding = '2px 8px';
            badge.style.fontSize = '0.75rem';
            badge.style.color = '#fff';
            
            const color = colorsMap[opt.value] || '#6c757d';
            badge.style.backgroundColor = color;

            label.appendChild(checkbox);
            label.appendChild(badge);
            menuEl.appendChild(label);
        });
        window.attachDropdownMultiselectSearch(menuEl);
        updateText();
    }

    rebuild();

    selectElement.rebuildCustomDropdown = rebuild;
};

