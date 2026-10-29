from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from .forms import SignUpForm


# Existing homepage
def index(request):
    if request.user.is_authenticated:
        return render(request, "la_ratatouille_app/home.html")

    return redirect("login")

# Feature 2: Signup
def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)

        if form.is_valid():
            user = form.save()

            # Automatically log in after signup
            login(request, user)

            return redirect("index")

    else:
        form = SignUpForm()

    return render(request, "la_ratatouille_app/signup.html", {"form": form})

def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("index")
        else:
            return render(request, "la_ratatouille_app/login.html", {
                "error": "Invalid username or password."
            })

    return render(request, "la_ratatouille_app/login.html")

from django.views.decorators.http import require_POST

@require_POST
def user_logout(request):
    logout(request)
    return redirect("index")