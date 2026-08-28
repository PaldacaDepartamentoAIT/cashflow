from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('home/', views.home_organizacion, name='home_organizacion'),
    path('configuracion/', views.configuracion, name='configuracion'),
    path('nueva/', views.crear_organizacion, name='crear_organizacion'),
    path('seleccionar/<int:org_id>/', views.seleccionar_organizacion, name='seleccionar_organizacion'),
    path('salir/', views.salir_organizacion, name='salir_organizacion'),
    
    # Transacciones
    path('transacciones/', views.lista_transacciones, name='lista_transacciones'),
    path('transacciones/guardar/', views.guardar_transaccion, name='crear_transaccion'),
    path('transacciones/guardar/<int:trans_id>/', views.guardar_transaccion, name='editar_transaccion'),
    path('transacciones/eliminar/<int:trans_id>/', views.eliminar_transaccion, name='eliminar_transaccion'),
    path('transacciones/detalle/<int:trans_id>/', views.detalle_transaccion, name='detalle_transaccion'),
    path('transacciones/<int:trans_id>/fotos/', views.listar_fotos_transaccion, name='listar_fotos_transaccion'),
    path('transacciones/fotos/<int:foto_id>/', views.ver_foto_transaccion, name='ver_foto_transaccion'),
    path('transacciones/fotos/<int:foto_id>/eliminar/', views.eliminar_foto_transaccion, name='eliminar_foto_transaccion'),
    path('transacciones/exportar-pdf/', views.exportar_pdf_transacciones, name='exportar_pdf_transacciones'),
    path('transacciones/exportar-xlsx/', views.exportar_xlsx_transacciones, name='exportar_xlsx_transacciones'),
    
    # Categorías
    path('categorias/', views.lista_categorias, name='lista_categorias'),
    path('categorias/guardar/', views.guardar_categoria, name='crear_categoria'),
    path('categorias/guardar/<int:cat_id>/', views.guardar_categoria, name='editar_categoria'),
    path('categorias/eliminar/<int:cat_id>/', views.eliminar_categoria, name='eliminar_categoria'),

    # Cuentas
    path('cuentas/', views.lista_cuentas, name='lista_cuentas'),
    path('cuentas/guardar/', views.guardar_cuenta, name='crear_cuenta'),
    path('cuentas/guardar/<int:acc_id>/', views.guardar_cuenta, name='editar_cuenta'),
    path('cuentas/eliminar/<int:acc_id>/', views.eliminar_cuenta, name='eliminar_cuenta'),
    path('cuentas/detalle/<int:acc_id>/', views.detalle_cuenta, name='detalle_cuenta'),

    # Proyectos
    path('proyectos/', views.lista_proyectos, name='lista_proyectos'),
    path('proyectos/guardar/', views.guardar_proyecto, name='crear_proyecto'),
    path('proyectos/guardar/<int:proj_id>/', views.guardar_proyecto, name='editar_proyecto'),
    path('proyectos/eliminar/<int:proj_id>/', views.eliminar_proyecto, name='eliminar_proyecto'),
    path('proyectos/detalle/<int:proj_id>/', views.detalle_proyecto, name='detalle_proyecto'),
    path('proyectos/<int:proj_id>/compartir/', views.compartir_proyecto, name='compartir_proyecto'),
    path('proyectos/enlaces/listar/', views.listar_enlaces_compartidos, name='listar_enlaces_compartidos'),
    path('proyectos/enlaces/<int:link_id>/eliminar/', views.eliminar_enlace_compartido, name='eliminar_enlace_compartido'),
    path('proyectos/compartido/<str:token>/', views.proyecto_publico, name='proyecto_publico'),

    # Valuaciones
    path('valuaciones/guardar/<int:proj_id>/', views.guardar_valuacion, name='crear_valuacion'),
    path('valuaciones/guardar/<int:proj_id>/<int:val_id>/', views.guardar_valuacion, name='editar_valuacion'),
    path('valuaciones/eliminar/<int:val_id>/', views.eliminar_valuacion, name='eliminar_valuacion'),
]
