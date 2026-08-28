"""Señales de la app: limpieza de archivos al eliminar fotos de transacciones."""

from django.db import transaction as db_transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import TransactionPhoto


@receiver(post_delete, sender=TransactionPhoto)
def borrar_archivo_de_foto(sender, instance, **kwargs):
    """Borra el archivo del storage cuando se elimina la fila.

    Django no borra archivos al borrar registros, así que esto es lo único que
    libera los bytes. Se difiere con on_commit porque guardar_transaccion()
    elimina fotos dentro de un atomic(): si hubiera rollback, las filas volverían
    pero los archivos ya estarían perdidos. Fuera de un bloque atómico on_commit
    se ejecuta de inmediato, así que eliminar_transaccion() funciona igual.

    Además, tener este receptor registrado desactiva el fast-delete de Django, de
    modo que al borrar una Transaction sí se dispara post_delete por cada foto
    en cascada.
    """
    if not instance.image or not instance.image.name:
        return
    nombre = instance.image.name
    storage = instance.image.storage
    db_transaction.on_commit(lambda: storage.delete(nombre))
