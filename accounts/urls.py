from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('registro/', views.registro, name='registro'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Restablecimiento de contrasena (arranca con el nombre de usuario).
    path('password-reset/', views.solicitar_reset, name='password_reset'),
    path('password-reset/enviado/', views.PasswordResetSentView.as_view(), name='password_reset_sent'),
    path('password-reset/sin-correo/', views.PasswordResetNoEmailView.as_view(), name='password_reset_no_email'),
    path('password-reset/completado/', views.ResetCompleteView.as_view(), name='password_reset_complete'),
    path('password-reset/<uidb64>/<token>/', views.ResetConfirmView.as_view(), name='password_reset_confirm'),
]
