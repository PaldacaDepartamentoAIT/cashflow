"""Validación, compresión y gestión de las fotos adjuntas de una transacción.

Se aceptan JPG, PNG, WEBP y HEIC (el formato por defecto de los iPhone).
Todo archivo aceptado se recomprime a JPEG hasta quedar por debajo de
`settings.TRANSACTION_PHOTO_TARGET_BYTES` (40 KB por defecto). Recomprimir
completo con Pillow, además de acotar el almacenamiento, descarta los metadatos
EXIF (incluida la geolocalización) y destruye cualquier payload incrustado.
"""

from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError

from CashFlow.debug import debug_event

# Los iPhone graban en HEIC por defecto. Registrar el decodificador permite
# aceptarlos; procesar_foto() los reescribe a JPEG como a todo lo demás.
pillow_heif.register_heif_opener()

EXTENSIONES_PERMITIDAS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}
TIPOS_PERMITIDOS = {
    'image/jpeg', 'image/pjpeg', 'image/png', 'image/webp',
    'image/heic', 'image/heif', 'image/heic-sequence', 'image/heif-sequence',
}
# Tipos que algunos navegadores envían cuando no reconocen el formato: no aportan
# información, así que se dejan pasar y decide Pillow, que es la comprobación real.
TIPOS_DESCONOCIDOS = {'application/octet-stream', 'binary/octet-stream'}
FORMATOS_PILLOW = {'JPEG', 'PNG', 'WEBP', 'HEIF'}

# De mayor a menor: se busca la mejor combinación que quepa bajo el objetivo.
DIMENSIONES = (1600, 1280, 1024, 800, 640, 480)
CALIDADES = (85, 75, 65, 55, 45, 38, 30)


def max_fotos():
    """Leído en cada llamada para que override_settings funcione en los tests."""
    return getattr(settings, 'TRANSACTION_PHOTOS_MAX', 10)


def objetivo_bytes():
    return getattr(settings, 'TRANSACTION_PHOTO_TARGET_BYTES', 40 * 1024)


def max_subida_bytes():
    return getattr(settings, 'TRANSACTION_PHOTO_MAX_UPLOAD_BYTES', 15 * 1024 * 1024)


def _mb(n):
    return round(n / (1024 * 1024), 1)


def validar_foto(archivo):
    """Valida tamaño, extensión, tipo de contenido y que sea realmente una imagen.

    Lanza ValidationError con un mensaje en español explicando qué hay que corregir.
    """
    nombre = getattr(archivo, 'name', '') or 'archivo'

    if archivo.size > max_subida_bytes():
        raise ValidationError(
            "La foto «%s» pesa %s MB: el máximo permitido por archivo es %s MB. "
            "Reduzca la resolución de la cámara o recorte la imagen antes de subirla."
            % (nombre, _mb(archivo.size), _mb(max_subida_bytes()))
        )

    if Path(nombre).suffix.lower() not in EXTENSIONES_PERMITIDAS:
        raise ValidationError(
            "El archivo «%s» no tiene una extensión de imagen admitida: solo se "
            "aceptan archivos JPG, PNG, WEBP o HEIC." % nombre
        )

    tipo = (getattr(archivo, 'content_type', '') or '').lower()
    if tipo and tipo not in TIPOS_PERMITIDOS and tipo not in TIPOS_DESCONOCIDOS:
        raise ValidationError(
            "El archivo «%s» se envió con el tipo de contenido «%s», que no "
            "corresponde a una imagen JPG, PNG, WEBP o HEIC." % (nombre, tipo)
        )

    try:
        archivo.seek(0)
        imagen = Image.open(archivo)
        imagen.verify()
        if imagen.format not in FORMATOS_PILLOW:
            raise ValidationError(
                "El archivo «%s» es una imagen en formato %s, que no está "
                "admitido: use JPG, PNG, WEBP o HEIC." % (nombre, imagen.format)
            )
    except ValidationError:
        raise
    except UnidentifiedImageError:
        raise ValidationError(
            "El archivo «%s» no es una imagen válida o está dañado: use un "
            "archivo JPG, PNG, WEBP o HEIC." % nombre
        )
    except Image.DecompressionBombError:
        raise ValidationError(
            "La imagen «%s» tiene dimensiones desproporcionadas y no puede "
            "procesarse." % nombre
        )
    except Exception:
        raise ValidationError(
            "No se pudo leer el archivo «%s»: verifique que sea una imagen JPG, "
            "PNG, WEBP o HEIC no dañada." % nombre
        )
    finally:
        archivo.seek(0)


def _codificar(imagen, calidad):
    buf = BytesIO()
    imagen.save(buf, 'JPEG', quality=calidad, optimize=True, progressive=True)
    return buf.getvalue()


def _reducir(imagen, dimension):
    copia = imagen.copy()
    copia.thumbnail((dimension, dimension), Image.LANCZOS)
    return copia


def comprimir_a_objetivo(imagen, objetivo):
    """Devuelve (bytes JPEG, ancho, alto) con el mejor detalle que quepa bajo `objetivo`.

    Recorre las dimensiones de mayor a menor. En cada una sondea primero la calidad
    mínima: si ni así cabe, salta a la dimensión siguiente sin recodificar en balde.
    Cuando cabe, hace una búsqueda binaria sobre CALIDADES para quedarse con la
    mejor calidad que sigue cumpliendo el objetivo (~4 codificaciones típicas).
    """
    for dimension in DIMENSIONES:
        copia = _reducir(imagen, dimension)
        if len(_codificar(copia, CALIDADES[-1])) > objetivo:
            continue

        # Búsqueda binaria: índice más bajo (mejor calidad) que cabe.
        bajo, alto = 0, len(CALIDADES) - 1
        mejor = _codificar(copia, CALIDADES[alto])
        while bajo <= alto:
            medio = (bajo + alto) // 2
            datos = _codificar(copia, CALIDADES[medio])
            if len(datos) <= objetivo:
                mejor = datos
                alto = medio - 1
            else:
                bajo = medio + 1
        return mejor, copia.width, copia.height

    # Ni la dimensión más pequeña con la calidad más baja cabe: se acepta igualmente
    # (la imagen ya es mínima) y se deja constancia para poder revisarlo.
    copia = _reducir(imagen, DIMENSIONES[-1])
    datos = _codificar(copia, CALIDADES[-1])
    debug_event(
        "transaccion.foto.objetivo_no_alcanzado",
        objetivo=objetivo,
        tamano=len(datos),
        ancho=copia.width,
        alto=copia.height,
    )
    return datos, copia.width, copia.height


def procesar_foto(archivo):
    """Normaliza una imagen subida: rotación EXIF, sin alfa, JPEG bajo el objetivo.

    Devuelve (ContentFile listo para guardar, dict con ancho/alto/size_bytes).
    """
    archivo.seek(0)
    imagen = Image.open(archivo)
    imagen = ImageOps.exif_transpose(imagen)

    if imagen.mode in ('RGBA', 'LA', 'P'):
        imagen = imagen.convert('RGBA')
        fondo = Image.new('RGB', imagen.size, (255, 255, 255))
        fondo.paste(imagen, mask=imagen.split()[-1])
        imagen = fondo
    elif imagen.mode != 'RGB':
        imagen = imagen.convert('RGB')

    datos, ancho, alto = comprimir_a_objetivo(imagen, objetivo_bytes())
    meta = {'width': ancho, 'height': alto, 'size_bytes': len(datos)}
    return ContentFile(datos, name=f'{uuid4().hex}.jpg'), meta


def crear_fotos(transaction, archivos, user):
    """Valida, procesa y guarda las fotos nuevas de una transacción."""
    from .models import TransactionPhoto

    if not archivos:
        return []

    ultima = transaction.photos.order_by('-position').values_list('position', flat=True).first()
    posicion = (ultima or 0) + 1

    creadas = []
    for archivo in archivos:
        validar_foto(archivo)
        contenido, meta = procesar_foto(archivo)
        foto = TransactionPhoto(
            transaction=transaction,
            original_filename=(getattr(archivo, 'name', '') or '')[:255],
            position=posicion,
            uploaded_by=user if getattr(user, 'is_authenticated', False) else None,
            **meta,
        )
        foto.image.save(contenido.name, contenido, save=False)
        foto.save()
        creadas.append(foto)
        posicion += 1

    return creadas


def eliminar_fotos(transaction, ids):
    """Elimina fotos de ESTA transacción. El filtro por `transaction` es lo que
    impide borrar fotos ajenas aunque lleguen ids de otra transacción."""
    if not ids:
        return 0
    borradas = 0
    for foto in transaction.photos.filter(id__in=ids):
        foto.delete()
        borradas += 1
    return borradas
