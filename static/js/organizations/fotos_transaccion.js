/**
 * CashFlow — fotos adjuntas de transacciones.
 *
 * Vive fuera de transacciones.js / detalle_proyecto.js porque el mismo modal está
 * duplicado en tres plantillas y las firmas de editTransaction() divergen entre
 * ellas: el estado de las fotos tiene que ser único y compartido.
 */
const CFFotos = (function () {
    let config = {
        maxFotos: 10,
        listarUrl: function (id) { return '/transacciones/' + id + '/fotos/'; },
        verUrl: function (id) { return '/transacciones/fotos/' + id + '/'; }
    };

    // Archivos aún no enviados. FileList es inmutable, así que mantenemos el
    // array aparte y reconstruimos el input con DataTransfer.
    let pendientes = [];
    let objectUrls = [];

    function grid() { return document.getElementById('fotosGrid'); }
    function input() { return document.getElementById('fotosInput'); }
    function form() { return document.getElementById('transactionForm'); }

    function existentesNoMarcadas() {
        const g = grid();
        if (!g) return 0;
        return g.querySelectorAll('[data-foto-id]:not(.is-marked)').length;
    }

    function total() {
        return existentesNoMarcadas() + pendientes.length;
    }

    function actualizarContador() {
        const c = document.getElementById('fotosCounter');
        if (c) c.textContent = total() + ' / ' + config.maxFotos;
    }

    function sincronizarInput() {
        const inp = input();
        if (!inp) return;
        const dt = new DataTransfer();
        pendientes.forEach(function (f) { dt.items.add(f); });
        inp.files = dt.files;
    }

    function limpiarObjectUrls() {
        objectUrls.forEach(function (u) { URL.revokeObjectURL(u); });
        objectUrls = [];
    }

    function renderPendientes() {
        const g = grid();
        if (!g) return;
        g.querySelectorAll('[data-foto-pendiente]').forEach(function (el) { el.remove(); });

        pendientes.forEach(function (archivo, idx) {
            const url = URL.createObjectURL(archivo);
            objectUrls.push(url);

            const item = document.createElement('div');
            item.className = 'cf-photo-grid__item cf-photo-grid__item--pendiente';
            item.setAttribute('data-foto-pendiente', String(idx));

            const img = document.createElement('img');
            img.className = 'cf-photo-grid__img';
            img.src = url;
            img.alt = 'Foto por adjuntar';
            img.setAttribute('data-foto-full', url);
            item.appendChild(img);

            const badge = document.createElement('span');
            badge.className = 'cf-photo-grid__badge';
            badge.textContent = 'Nueva';
            item.appendChild(badge);

            const quitar = document.createElement('button');
            quitar.type = 'button';
            quitar.className = 'cf-photo-grid__remove';
            quitar.title = 'Quitar esta foto';
            quitar.textContent = '×';
            quitar.setAttribute('data-foto-quitar', String(idx));
            item.appendChild(quitar);

            g.appendChild(item);
        });

        sincronizarInput();
        actualizarContador();
    }

    function agregarArchivos(lista) {
        if (window.userIsViewer) return;
        const disponibles = config.maxFotos - total();
        if (disponibles <= 0) {
            alert('Solo puede adjuntar hasta ' + config.maxFotos + ' fotos por transacción.');
            sincronizarInput();
            return;
        }
        const nuevos = Array.prototype.slice.call(lista, 0, disponibles);
        if (lista.length > disponibles) {
            alert('Solo se agregaron ' + disponibles + ' foto(s): el máximo es ' +
                  config.maxFotos + ' por transacción.');
        }
        pendientes = pendientes.concat(nuevos);
        renderPendientes();
    }

    function quitarPendiente(idx) {
        if (window.userIsViewer) return;
        pendientes.splice(idx, 1);
        renderPendientes();
    }

    function marcarEliminacion(fotoId) {
        if (window.userIsViewer) return;
        const g = grid();
        const f = form();
        if (!g || !f) return;

        const item = g.querySelector('[data-foto-id="' + fotoId + '"]');
        if (!item) return;

        const existente = f.querySelector('input[name="delete_photo_ids"][value="' + fotoId + '"]');
        if (existente) {
            existente.remove();
            item.classList.remove('is-marked');
        } else {
            const hidden = document.createElement('input');
            hidden.type = 'hidden';
            hidden.name = 'delete_photo_ids';
            hidden.value = String(fotoId);
            f.appendChild(hidden);
            item.classList.add('is-marked');
        }
        actualizarContador();
    }

    function reset() {
        pendientes = [];
        limpiarObjectUrls();

        const g = grid();
        if (g) g.innerHTML = '';

        const inp = input();
        if (inp) inp.value = '';

        const f = form();
        if (f) {
            f.querySelectorAll('input[name="delete_photo_ids"]').forEach(function (el) { el.remove(); });
        }
        actualizarContador();
    }

    function cargarExistentes(id) {
        // duplicateTransaction() en detalle_proyecto.js llama editTransaction(0, ...),
        // así que sin esta guarda pediríamos /transacciones/0/fotos/ y daría 404.
        if (!id) return;
        const g = grid();
        if (!g) return;

        fetch(config.listarUrl(id), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (r) { return r.ok ? r.text() : ''; })
            .then(function (html) {
                g.insertAdjacentHTML('afterbegin', html);
                actualizarContador();
            })
            .catch(function () { /* la galería queda vacía; el guardado sigue funcionando */ });
    }

    function validarAntesDeEnviar() {
        if (total() > config.maxFotos) {
            return 'Solo puede adjuntar hasta ' + config.maxFotos +
                   ' fotos por transacción. Actualmente hay ' + total() + '.';
        }
        return null;
    }

    function verCompleta(src) {
        const modal = document.getElementById('photoModal');
        const img = document.getElementById('photoModalImg');
        if (!modal || !img || !window.CFModal) return;
        img.src = src;
        CFModal.open('photoModal');
    }

    function init(opts) {
        config = Object.assign(config, opts || {});

        // Delegado y registrado una sola vez: el partial de detalle se inyecta con
        // innerHTML, y las etiquetas <script> insertadas así no se ejecutan.
        document.addEventListener('click', function (e) {
            const quitar = e.target.closest('[data-foto-quitar]');
            if (quitar) {
                e.preventDefault();
                quitarPendiente(parseInt(quitar.getAttribute('data-foto-quitar'), 10));
                return;
            }
            const borrar = e.target.closest('[data-foto-remove]');
            if (borrar) {
                e.preventDefault();
                marcarEliminacion(borrar.getAttribute('data-foto-remove'));
                return;
            }
            const ver = e.target.closest('[data-foto-full]');
            if (ver) {
                e.preventDefault();
                verCompleta(ver.getAttribute('data-foto-full'));
            }
        });

        document.addEventListener('change', function (e) {
            if (e.target && e.target.id === 'fotosInput') {
                agregarArchivos(e.target.files);
            }
        });

        actualizarContador();
    }

    return {
        init: init,
        reset: reset,
        cargarExistentes: cargarExistentes,
        marcarEliminacion: marcarEliminacion,
        total: total,
        validarAntesDeEnviar: validarAntesDeEnviar
    };
})();

window.CFFotos = CFFotos;
