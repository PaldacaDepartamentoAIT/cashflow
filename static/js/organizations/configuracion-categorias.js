/**
 * Administración de categorías dentro de la pantalla de Configuración.
 *
 * No define endpoints propios: reutiliza las vistas `guardar_categoria` y
 * `eliminar_categoria`, que devuelven al usuario aquí gracias al campo oculto
 * `next` de cada formulario.
 */
function initConfiguracionCategorias(config) {
    const modal = document.getElementById('catModal');
    // Los usuarios con rol Viewer ven el listado, pero no los modales de edición.
    if (!modal || window.userIsViewer) return;

    const form = document.getElementById('catForm');
    const title = document.getElementById('catModalTitle');
    const nameInput = form.querySelector('[name="name"]');
    const descInput = form.querySelector('[name="description"]');
    const colorInput = form.querySelector('[name="color"]');
    const hexInput = document.getElementById('cat-color-hex');
    const presetsBox = document.getElementById('cat-color-presets');

    const deleteModal = document.getElementById('catDeleteModal');
    const deleteForm = document.getElementById('catDeleteForm');
    const deleteName = document.getElementById('catDeleteName');

    const DEFAULT_COLOR = '#3b82f6';
    const PRESET_COLORS = [
        '#ef4444', '#f97316', '#f59e0b', '#eab308',
        '#84cc16', '#22c55e', '#10b981', '#14b8a6',
        '#06b6d4', '#3b82f6', '#6366f1', '#8b5cf6',
        '#a855f7', '#ec4899', '#64748b', '#111827'
    ];

    /** Acepta "#abc", "abc123" o "#ABCDEF" y devuelve siempre "#rrggbb". */
    function normalizeHex(value) {
        let hex = String(value || '').trim().replace(/^#/, '');
        if (/^[0-9a-fA-F]{3}$/.test(hex)) {
            hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2];
        }
        if (!/^[0-9a-fA-F]{6}$/.test(hex)) return null;
        return '#' + hex.toLowerCase();
    }

    function markActivePreset(hex) {
        presetsBox.querySelectorAll('.cat-preset').forEach(function (btn) {
            btn.classList.toggle('is-active', btn.dataset.color === hex);
        });
    }

    /** Única vía para cambiar el color: mantiene selector, hex y presets en sincronía. */
    function setColor(value) {
        const hex = normalizeHex(value) || DEFAULT_COLOR;
        colorInput.value = hex;
        hexInput.value = hex;
        markActivePreset(hex);
    }

    PRESET_COLORS.forEach(function (hex) {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'cat-preset';
        btn.dataset.color = hex;
        btn.style.backgroundColor = hex;
        btn.title = hex;
        btn.setAttribute('aria-label', 'Usar el color ' + hex);
        presetsBox.appendChild(btn);
    });

    presetsBox.addEventListener('click', function (e) {
        const btn = e.target.closest('.cat-preset');
        if (btn) setColor(btn.dataset.color);
    });

    // El selector nativo del navegador siempre entrega un #rrggbb válido.
    colorInput.addEventListener('input', function () { setColor(colorInput.value); });

    // Mientras se escribe solo se aplica lo que ya es válido; al salir se corrige.
    hexInput.addEventListener('input', function () {
        const hex = normalizeHex(hexInput.value);
        if (hex) {
            colorInput.value = hex;
            markActivePreset(hex);
        }
    });
    hexInput.addEventListener('blur', function () { setColor(colorInput.value); });

    /** Sustituye el id 0 de la URL de plantilla por el id real. */
    function urlFor(template, id) {
        return template.replace(/0\/$/, id + '/');
    }

    document.getElementById('cat-new-btn').addEventListener('click', function () {
        form.reset();
        form.action = config.crearUrl;
        title.innerText = 'Nueva Categoría';
        setColor(DEFAULT_COLOR);
        CFModal.open('catModal');
        nameInput.focus();
    });

    document.addEventListener('click', function (e) {
        const editBtn = e.target.closest('.js-cat-edit');
        if (editBtn) {
            form.action = urlFor(config.editarUrlTpl, editBtn.dataset.id);
            title.innerText = 'Editar Categoría';
            nameInput.value = editBtn.dataset.name || '';
            descInput.value = editBtn.dataset.description || '';
            setColor(editBtn.dataset.color);
            CFModal.open('catModal');
            nameInput.focus();
            return;
        }

        const delBtn = e.target.closest('.js-cat-delete');
        if (delBtn) {
            deleteForm.action = urlFor(config.eliminarUrlTpl, delBtn.dataset.id);
            deleteName.innerText = delBtn.dataset.name || '';
            CFModal.open('catDeleteModal');
        }
    });
}
