from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.custom_logout_view, name='logout'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('change-password/', views.change_password, name='change_password'),
    path('password-change-done/', views.password_change_done, name='password_change_done'),
    path('settings/', views.settings, name='settings'),
]
