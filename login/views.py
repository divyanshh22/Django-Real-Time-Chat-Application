from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from .models import CustomUser, ProfilePic


def login_view(request):
    if request.user.is_authenticated:
        return redirect('chat:home-view')

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome, {user.first_name}!")
            return redirect('chat:home-view')
        else:
            messages.error(request, "Invalid username or password!")
            return redirect('login-view')
    return render(request, 'login/login.html')


def home_redirect_view(request):
    return redirect('chat:home-view')


def register_view(request):
    if request.user.is_authenticated:
        return redirect('chat:home-view')

    if request.method == 'POST':
        username   = request.POST['username']
        first_name = request.POST['first_name']
        last_name  = request.POST['last_name']
        email      = request.POST['email']
        password1  = request.POST['password1']
        password2  = request.POST['password2']

        if password1 != password2:
            messages.error(request, "Password Don't Match")
            return redirect('register-view')

        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, "Username is already Taken")
            return redirect('register-view')

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered!")
            return redirect('register-view')

        try:
            user = CustomUser.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password1,
            )
            messages.success(request, "Account created successfully!")
            return redirect('login-view')
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('register-view')

    return render(request, 'login/register.html')


@login_required(login_url='login-view')
def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully!")
    return redirect('login-view')


@login_required(login_url='login-view')
def profile_view(request):
    profile, _ = ProfilePic.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        pic = request.FILES.get('profile_pic')
        if pic:
            profile.profile_pic = pic
            profile.save()
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()
        messages.success(request, 'Profile updated!')
        return redirect('profile-view')

    return render(request, 'login/profile.html', {'profile': profile})


@login_required(login_url='login-view')
def user_profile_view(request, username):
    user = get_object_or_404(CustomUser, username=username)
    profile, _ = ProfilePic.objects.get_or_create(user=user)
    return render(request, 'login/user_profile.html', {
        'profile_user': user,
        'profile': profile
    })