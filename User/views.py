from django.contrib import messages, auth
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import CustomPasswordChangeForm
from .models import CustomUser
from django.contrib.auth import get_user_model
from django.urls import reverse

import datetime


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', None)
        password = request.POST.get('password', None)

        User = get_user_model()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email.')
            return redirect('login')

        # Now check if the password is correct
        user = auth.authenticate(email=email, password=password)
        if user is not None:
            auth.login(request, user)
            return redirect('ALM_home')
        else:
            messages.error(request, 'Incorrect password.')
            return redirect('login')

    return render(request, 'users/login.html')


@login_required
def update_profile(request):
    user = request.user

    if request.method == 'POST':
        name = request.POST.get('name', user.name)
        surname = request.POST.get('surname', user.surname)
        phone_number = request.POST.get('phone_number', user.phone_number)
        gender = request.POST.get('gender', user.gender)

        # Update user fields
        user.name = name
        user.surname = surname
        user.phone_number = phone_number
        user.gender = gender
        user.save()

        messages.success(
            request, 'Your profile has been updated successfully.')
        return redirect('settings')

    return render(request, 'users/update_profile.html', {
        'user': user,
    })


@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(
                request, 'Your password has been changed successfully.')
            return redirect('settings')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomPasswordChangeForm(user=request.user)

    return render(request, 'users/change_password.html', {'form': form})


@login_required
def password_change_done(request):
    return render(request, 'users/password_change_done.html')


@login_required
def settings(request):
    return render(request, 'users/settings.html')


def custom_logout_view(request):
    logout(request)
    messages.success(request, "Successfully logged out.")
    return redirect(reverse('login'))  # Redirect to login page after logout
