from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Favorite, Ingredient, Recipe, RecipeIngredient, Review, Tag, Unit


class RecipeWorkflowTests(TestCase):
    """Check that recipe owners and signed-in users can use their workflows."""

    def setUp(self):
        self.user = User.objects.create_user(username="cook", password="test-password")
        self.other_user = User.objects.create_user(
            username="another-cook", password="test-password"
        )
        self.ingredient = Ingredient.objects.create(name="Tomato")
        self.unit = Unit.objects.create(name="Piece", abbr="pc")
        self.tag = Tag.objects.create(name="Dinner")

    def recipe_data(self, **overrides):
        data = {
            "name": "Tomato soup",
            "instructions": "Cook the tomatoes.",
            "calories_per_serving": "120",
            "num_servings": "2",
            "prep_time": "20",
            "tags": [str(self.tag.pk)],
            "recipe_ingredients-TOTAL_FORMS": "1",
            "recipe_ingredients-INITIAL_FORMS": "0",
            "recipe_ingredients-MIN_NUM_FORMS": "1",
            "recipe_ingredients-MAX_NUM_FORMS": "1000",
            "recipe_ingredients-0-ingredient": str(self.ingredient.pk),
            "recipe_ingredients-0-quantity": "3",
            "recipe_ingredients-0-unit": str(self.unit.pk),
        }
        data.update(overrides)
        return data

    def create_recipe(self, user=None):
        recipe = Recipe.objects.create(
            name="Tomato soup",
            instructions="Cook the tomatoes.",
            calories_per_serving=120,
            num_servings=2,
            prep_time=20,
            user=user or self.user,
        )
        RecipeIngredient.objects.create(
            recipe=recipe,
            ingredient=self.ingredient,
            quantity=3,
            unit=self.unit,
        )
        return recipe

    def test_create_recipe_saves_owner_tags_and_ingredients(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("recipe_create"), self.recipe_data())

        recipe = Recipe.objects.get(name="Tomato soup")
        self.assertRedirects(
            response,
            reverse("recipe_detail", args=[recipe.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(recipe.user, self.user)
        self.assertQuerySetEqual(recipe.tags.all(), [self.tag], ordered=False)
        self.assertEqual(recipe.recipe_ingredients.get().quantity, 3)

    def test_create_recipe_requires_login(self):
        response = self.client.get(reverse("recipe_create"))
        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('recipe_create')}",
            fetch_redirect_response=False,
        )

    def test_edit_recipe_updates_only_owner_recipe(self):
        recipe = self.create_recipe()
        self.client.force_login(self.user)
        data = self.recipe_data(
            name="Roasted tomatoes",
            **{
                "recipe_ingredients-TOTAL_FORMS": "2",
                "recipe_ingredients-INITIAL_FORMS": "1",
                "recipe_ingredients-1-ingredient": "",
                "recipe_ingredients-1-quantity": "",
                "recipe_ingredients-1-unit": "",
            },
        )
        data["recipe_ingredients-0-id"] = str(recipe.recipe_ingredients.get().pk)
        data["recipe_ingredients-0-quantity"] = "4"
        response = self.client.post(reverse("recipe_edit", args=[recipe.pk]), data)

        self.assertRedirects(
            response,
            reverse("recipe_detail", args=[recipe.pk]),
            fetch_redirect_response=False,
        )
        recipe.refresh_from_db()
        self.assertEqual(recipe.name, "Roasted tomatoes")
        self.assertEqual(recipe.recipe_ingredients.get().quantity, 4)

    def test_users_cannot_edit_or_delete_another_users_recipe(self):
        recipe = self.create_recipe(user=self.other_user)
        self.client.force_login(self.user)

        self.assertEqual(
            self.client.get(reverse("recipe_edit", args=[recipe.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.get(reverse("recipe_delete", args=[recipe.pk])).status_code, 404
        )

    def test_delete_requires_confirmation_and_removes_recipe(self):
        recipe = self.create_recipe()
        self.client.force_login(self.user)

        self.assertEqual(
            self.client.get(reverse("recipe_delete", args=[recipe.pk])).status_code, 200
        )
        response = self.client.post(reverse("recipe_delete", args=[recipe.pk]))

        self.assertRedirects(
            response, reverse("my_recipes"), fetch_redirect_response=False
        )
        self.assertFalse(Recipe.objects.filter(pk=recipe.pk).exists())

    def test_rating_is_saved_updated_and_limited_to_five_stars(self):
        recipe = self.create_recipe(user=self.other_user)
        self.client.force_login(self.user)

        self.client.post(reverse("rate_recipe", args=[recipe.pk]), {"rating": "5"})
        self.assertEqual(Review.objects.get(recipe=recipe, user=self.user).rating, 5)

        self.client.post(reverse("rate_recipe", args=[recipe.pk]), {"rating": "3"})
        self.assertEqual(Review.objects.filter(recipe=recipe, user=self.user).count(), 1)
        self.assertEqual(Review.objects.get(recipe=recipe, user=self.user).rating, 3)

        self.client.post(reverse("rate_recipe", args=[recipe.pk]), {"rating": "6"})
        self.assertEqual(Review.objects.get(recipe=recipe, user=self.user).rating, 3)

    def test_user_can_favorite_unfavorite_and_view_favorites(self):
        recipe = self.create_recipe(user=self.other_user)
        self.client.force_login(self.user)

        self.client.post(reverse("favorite_recipe", args=[recipe.pk]))
        self.assertTrue(Favorite.objects.filter(user=self.user, recipe=recipe).exists())
        response = self.client.get(reverse("favorites"))
        self.assertContains(response, recipe.name)

        self.client.post(reverse("unfavorite_recipe", args=[recipe.pk]))
        self.assertFalse(Favorite.objects.filter(user=self.user, recipe=recipe).exists())
        self.assertNotContains(self.client.get(reverse("favorites")), recipe.name)
