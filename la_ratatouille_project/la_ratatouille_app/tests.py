"""
Tests for the pantry use cases (UC 51-55). Run with:
    python manage.py test la_ratatouille_app
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from . import services
from .models import Ingredient, Recipe, RecipeIngredient, Unit, UserIngredient


class PantryTestBase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("ann", password="pw-123456!")
        self.cup = Unit.objects.create(name="cup", abbr="c")
        self.gram = Unit.objects.create(name="gram", abbr="g")
        self.each = Unit.objects.create(name="each", abbr="ea")
        self.flour = Ingredient.objects.create(name="Flour")
        self.milk = Ingredient.objects.create(name="Milk")
        self.egg = Ingredient.objects.create(name="Egg")
        self.recipe = Recipe.objects.create(
            name="Pancakes", instructions="Mix and cook.", calories_per_serving=200,
            num_servings=4, prep_time=20, user=self.user,
        )
        RecipeIngredient.objects.create(recipe=self.recipe, ingredient=self.flour, unit=self.cup, quantity=2)
        RecipeIngredient.objects.create(recipe=self.recipe, ingredient=self.milk, unit=self.cup, quantity=3)
        RecipeIngredient.objects.create(recipe=self.recipe, ingredient=self.egg, unit=self.each, quantity=2)


class CreatePantryTests(PantryTestBase):           # UC 54
    def test_new_user_has_empty_pantry(self):
        self.assertEqual(services.get_pantry(self.user).count(), 0)

    def test_create_with_starting_items(self):
        services.create_pantry(self.user, [(self.flour, self.cup, 3), (self.egg, self.each, 6)])
        self.assertEqual(services.get_pantry(self.user).count(), 2)


class DeletePantryTests(PantryTestBase):           # UC 55
    def test_delete_removes_every_item(self):
        services.create_pantry(self.user, [(self.flour, self.cup, 3), (self.milk, self.cup, 1)])
        self.assertEqual(services.delete_pantry(self.user), 2)
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_get_shows_confirmation_post_deletes(self):
        services.set_pantry_item(self.user, self.flour, self.cup, 3)
        self.client.force_login(self.user)
        self.client.get(reverse("pantry_delete"))
        self.assertEqual(UserIngredient.objects.count(), 1)
        self.client.post(reverse("pantry_delete"))
        self.assertEqual(UserIngredient.objects.count(), 0)


class EditPantryTests(PantryTestBase):             # UC 52
    def test_add_then_update(self):
        services.set_pantry_item(self.user, self.flour, self.cup, 1)
        services.set_pantry_item(self.user, self.flour, self.cup, 5)
        self.assertEqual(UserIngredient.objects.get(user=self.user, ingredient=self.flour).quantity, 5)

    def test_zero_removes(self):
        services.set_pantry_item(self.user, self.flour, self.cup, 1)
        self.assertIsNone(services.set_pantry_item(self.user, self.flour, self.cup, 0))
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_negative_rejected(self):
        with self.assertRaises(services.PantryError):
            services.set_pantry_item(self.user, self.flour, self.cup, -1)

    def test_pantry_page_form(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("pantry"), {"ingredient": self.milk.id, "quantity": 2, "unit": self.cup.id})
        self.assertRedirects(resp, reverse("pantry"))
        self.assertContains(self.client.get(reverse("pantry")), "Milk")


class AdjustBatchSizeTests(PantryTestBase):        # UC 51
    def test_double(self):
        factor, lines = services.scale_recipe(self.recipe, 8)
        self.assertEqual(factor, 2)
        self.assertEqual([l.scaled for l in lines], [Decimal("4.00"), Decimal("6.00"), Decimal("4.00")])

    def test_half_keeps_fractions(self):
        _, lines = services.scale_recipe(self.recipe, 2)
        self.assertIn(Decimal("1.50"), [l.scaled for l in lines])   # 3 cups milk -> 1.5

    def test_zero_servings_rejected(self):
        with self.assertRaises(ValueError):
            services.scale_recipe(self.recipe, 0)

    def test_page(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("recipe_detail", args=[self.recipe.id]), {"servings": 8})
        self.assertContains(resp, "Ingredients for 8 servings")
        self.assertContains(resp, "4 c Flour")


class MissingIngredientsTests(PantryTestBase):     # UC 53
    def test_empty_pantry(self):
        missing = services.missing_ingredients(self.recipe, self.user)
        self.assertEqual(len(missing), 3)

    def test_short_and_unit_mismatch(self):
        services.set_pantry_item(self.user, self.flour, self.cup, 3)   # enough
        services.set_pantry_item(self.user, self.milk, self.cup, 1)    # need 3
        services.set_pantry_item(self.user, self.egg, self.gram, 100)  # wrong unit
        missing = {m.ingredient.name: m for m in services.missing_ingredients(self.recipe, self.user)}
        self.assertNotIn("Flour", missing)
        self.assertEqual(missing["Milk"].short_by, Decimal("2"))
        self.assertEqual(missing["Egg"].reason, "different unit")

    def test_scaled_batch(self):
        services.set_pantry_item(self.user, self.flour, self.cup, 3)
        services.set_pantry_item(self.user, self.milk, self.cup, 6)
        services.set_pantry_item(self.user, self.egg, self.each, 2)
        self.assertEqual(services.missing_ingredients(self.recipe, self.user, 4), [])
        names = [m.ingredient.name for m in services.missing_ingredients(self.recipe, self.user, 8)]
        self.assertEqual(names, ["Flour", "Egg"])
