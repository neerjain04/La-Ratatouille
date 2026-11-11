from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin

from .models import *

admin.site.register(Tag)
admin.site.register(Unit)


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    """Ingredients by food group, so the dataset load can be checked in /admin/."""
    list_display = ["name", "food_group", "vegan", "gluten_free"]
    list_filter = ["food_group"]
    list_editable = ["food_group"]
    search_fields = ["name"]

class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    min_num = 0
    can_delete = True

class RecipeTagInline(admin.TabularInline):
    model = RecipeTag
    extra = 1
    min_num = 0
    can_delete = True

class RecipeReviewInline(admin.TabularInline):
    model = Review
    extra = 1
    min_num = 0
    can_delete = True

class UserIngredientInline(admin.TabularInline):
    model = UserIngredient
    extra = 1
    min_num = 0
    can_delete = True

class UserFavoriteInline(admin.TabularInline):
    model = Favorite
    extra = 1
    min_num = 0
    can_delete = True

class UserProfileInline(admin.StackedInline):
    model = Profile

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    inlines = [RecipeIngredientInline, RecipeTagInline, RecipeReviewInline]

class MyUserAdmin(UserAdmin):
    inlines = [UserIngredientInline, UserFavoriteInline, UserProfileInline]

admin.site.unregister(User)

admin.site.register(User, MyUserAdmin)
