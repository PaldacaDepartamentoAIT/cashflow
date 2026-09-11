from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, SetPasswordForm

class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Nombre de usuario", widget=forms.TextInput(attrs={'class': 'cf-input', 'placeholder': 'usuario123'}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={'class': 'cf-input', 'placeholder': '********'}))

    # Van como non_field_errors: la plantilla debe renderizarlos aparte de los
    # errores de campo. El texto de Django es mas rigido y suena a traduccion.
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': "Usuario o contraseña incorrectos. Verifica los datos e inténtalo de nuevo.",
        'inactive': "Esta cuenta está desactivada. Contacta al administrador.",
    }

class RegistroForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, label="Nombre", widget=forms.TextInput(attrs={'class': 'cf-input', 'placeholder': 'Tu nombre'}))
    last_name = forms.CharField(max_length=30, required=True, label="Apellido", widget=forms.TextInput(attrs={'class': 'cf-input', 'placeholder': 'Tu apellido'}))
    email = forms.EmailField(required=True, label="Email", widget=forms.EmailInput(attrs={'class': 'cf-input', 'placeholder': 'ejemplo@correo.com'}))
    username = forms.CharField(label="Nombre de usuario", widget=forms.TextInput(attrs={'class': 'cf-input', 'placeholder': 'usuario123'}))

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aseguramos que los campos de contraseña también tengan la clase form-control
        for field in self.fields:
            if 'password' in field:
                self.fields[field].widget.attrs.update({'class': 'cf-input', 'placeholder': '********'})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class SolicitarResetForm(forms.Form):
    """Primer paso del restablecimiento: el usuario escribe su nombre de usuario."""

    username = forms.CharField(
        label="Nombre de usuario",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'cf-input',
            'placeholder': 'usuario123',
            'autofocus': True,
            'autocomplete': 'username',
        }),
    )

    def clean_username(self):
        # La busqueda del usuario vive en la vista; aqui solo normalizamos.
        return self.cleaned_data['username'].strip()


class NuevaPasswordForm(SetPasswordForm):
    """Segundo paso: define la nueva contrasena desde el enlace del correo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'cf-input', 'placeholder': '********'})
