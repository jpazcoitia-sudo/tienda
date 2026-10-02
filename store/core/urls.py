from . import views
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic.base import RedirectView
from django.urls import path
# urls.py



urlpatterns = [
    path('redirect-admin', RedirectView.as_view(url="/admin"),name="redirect-admin"),
    path('', views.home, name="home-page"),
    path('login', auth_views.LoginView.as_view(template_name = 'core/login.html',redirect_authenticated_user=True), name="login"),
    path('userlogin', views.login_user, name="login-user"),
    path('logout', views.logoutuser, name="logout"),
    # SACADAS el 02/10/2026 por seguridad (venian del proyecto original):
    #  - register/        : cualquiera podia crearse un usuario sin estar logueado.
    #  - password_reset/  : no mandaba ningun mail; entregaba el enlace para cambiar la
    #                       clave a quien supiera el email de un usuario.
    # Los usuarios se crean y las claves se cambian desde /admin
    # (o con: python manage.py changepassword <usuario>).
]
