
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
#change later once recipe is actually implemented
from .models import Review


# Home page
def index(request):
    return HttpResponse("Welcome to La Ratatouille. This page is under construction.")



# Add Comment
@login_required
def add_comment(request, recipe_id):

    if request.method == "POST":

        recipe = get_object_or_404(Recipe, id=recipe_id)

        rating = request.POST.get("rating")
        comment = request.POST.get("comment", "").strip()

        # Check that a rating was selected
        if rating not in ["1", "2", "3", "4", "5"]:
            return HttpResponse("Please select a rating from 1 to 5.", status=400)

        # Check if the user already reviewed this recipe
        existing_review = Review.objects.filter(
            user=request.user,
            recipe=recipe
        ).exists()

        if existing_review:
            return HttpResponse(
                "You have already reviewed this recipe.",
                status=400
            )

        # Save the rating and optional comment
        Review.objects.create(
            user=request.user,
            recipe=recipe,
            rating=int(rating),
            comment=comment
        )

        return redirect("recipe_detail", recipe_id=recipe_id)

    return HttpResponse("Invalid request.", status=405)
