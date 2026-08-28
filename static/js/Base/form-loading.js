/**
 * CashFlow — estado de carga para formularios lentos.
 *
 * Opt-in por atributo:  <form data-cf-loading="Guardando transacción…">
 *
 * Guardar una transacción con fotos tarda: cada imagen se recomprime en el
 * servidor hasta bajar del objetivo de peso. Sin señal visible el usuario cree
 * que no pasó nada y vuelve a pulsar Guardar.
 */
(function () {
    const ATRIBUTO = 'data-cf-loading';

    function botonesEnvio(form) {
        return Array.prototype.slice.call(
            form.querySelectorAll('button[type="submit"], input[type="submit"]')
        );
    }

    function botonesCierre(form) {
        const modal = form.closest('.cf-modal');
        if (!modal) return [];
        return Array.prototype.slice.call(modal.querySelectorAll('[data-cf-dismiss="modal"]'));
    }

    function contarArchivos(form) {
        let total = 0;
        form.querySelectorAll('input[type="file"]').forEach(function (input) {
            total += input.files ? input.files.length : 0;
        });
        return total;
    }

    function mensaje(form) {
        const fotos = contarArchivos(form);
        if (fotos === 1) return 'Procesando 1 foto…';
        if (fotos > 1) return 'Procesando ' + fotos + ' fotos…';
        return form.getAttribute(ATRIBUTO) || 'Guardando…';
    }

    function activar(form) {
        if (form.classList.contains('is-loading')) return false;
        form.classList.add('is-loading');

        const texto = mensaje(form);
        botonesEnvio(form).forEach(function (btn) {
            btn.setAttribute('data-cf-label', btn.innerHTML);
            btn.innerHTML =
                '<span class="cf-spinner cf-spinner--btn" aria-hidden="true"></span>' + texto;
        });

        // Deshabilitar en el siguiente tick: hacerlo de forma síncrona dentro del
        // evento submit puede cancelar el envío en algunos navegadores.
        setTimeout(function () {
            botonesEnvio(form).forEach(function (btn) { btn.disabled = true; });
            botonesCierre(form).forEach(function (btn) { btn.disabled = true; });
        }, 0);

        return true;
    }

    function restaurar(form) {
        form.classList.remove('is-loading');
        botonesEnvio(form).forEach(function (btn) {
            const etiqueta = btn.getAttribute('data-cf-label');
            if (etiqueta !== null) {
                btn.innerHTML = etiqueta;
                btn.removeAttribute('data-cf-label');
            }
            btn.disabled = false;
        });
        botonesCierre(form).forEach(function (btn) { btn.disabled = false; });
    }

    // En fase de burbuja: corre DESPUÉS de los handlers propios del formulario,
    // así que e.defaultPrevented ya refleja si la validación del cliente lo rechazó.
    document.addEventListener('submit', function (e) {
        const form = e.target;
        if (!form || !form.hasAttribute || !form.hasAttribute(ATRIBUTO)) return;

        if (e.defaultPrevented) {
            restaurar(form);
            return;
        }
        if (!activar(form)) {
            e.preventDefault();  // ya se está enviando: evitar el envío doble
        }
    });

    // Al volver con el botón atrás el formulario puede restaurarse desde la
    // bfcache con los botones aún bloqueados.
    window.addEventListener('pageshow', function () {
        document.querySelectorAll('form.is-loading').forEach(restaurar);
    });
})();
