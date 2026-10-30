"""
Tests for the pantry use cases (UC 51-55). Run with:
    python manage.py test la_ratatouille_app
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .pantry import Pantry
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
        self.assertEqual(Pantry(self.user).items().count(), 0)

    def test_create_with_starting_items(self):
        pantry = Pantry.create(self.user, [(self.flour, self.cup, 3), (self.egg, self.each, 6)])
        self.assertEqual(pantry.items().count(), 2)
        self.assertEqual(set(pantry.ingredients()), {self.flour, self.egg})   # existing user.pantry manager


class DeletePantryTests(PantryTestBase):           # UC 55
    def test_delete_removes_every_item(self):
        pantry = Pantry.create(self.user, [(self.flour, self.cup, 3), (self.milk, self.cup, 1)])
        self.assertEqual(pantry.delete(), 2)
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_get_shows_confirmation_post_deletes(self):
        Pantry(self.user).add_ingredient(self.flour, 3, self.cup)
        self.client.force_login(self.user)
        self.client.get(reverse("pantry_delete"))
        self.assertEqual(UserIngredient.objects.count(), 1)
        self.client.post(reverse("pantry_delete"))
        self.assertEqual(UserIngredient.objects.count(), 0)


class EditPantryTests(PantryTestBase):             # UC 52
    def test_add_then_update(self):
        pantry = Pantry(self.user)
        pantry.add_ingredient(self.flour, 1, self.cup)
        pantry.add_ingredient(self.flour, 5, self.cup)
        self.assertEqual(UserIngredient.objects.get(user=self.user, ingredient=self.flour).quantity, 5)

    def test_zero_removes(self):
        pantry = Pantry(self.user)
        pantry.add_ingredient(self.flour, 1, self.cup)
        self.assertIsNone(pantry.add_ingredient(self.flour, 0, self.cup))
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_remove(self):
        pantry = Pantry(self.user)
        pantry.add_ingredient(self.flour, 1, self.cup)
        self.assertTrue(pantry.remove_ingredient(self.flour))
        self.assertFalse(pantry.remove_ingredient(self.flour))

    def test_negative_rejected(self):
        with self.assertRaises(ValueError):
            Pantry(self.user).add_ingredient(self.flour, -1, self.cup)

    def test_pantry_page_form(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("pantry"), {"ingredient": self.milk.id, "quantity": 2, "unit": self.cup.id})
        self.assertRedirects(resp, reverse("pantry"))
        self.assertContains(self.client.get(reverse("pantry")), "Milk")


class AdjustBatchSizeTests(PantryTestBase):        # UC 51
    def test_double(self):
        amounts = [amount for _, _, amount in self.recipe.scale_batch(2)]
        self.assertEqual(amounts, [Decimal("4.00"), Decimal("6.00"), Decimal("4.00")])

    def test_half_keeps_fractions(self):
        amounts = [amount for _, _, amount in self.recipe.scale_batch(self.recipe.multiplier_for(2))]
        self.assertIn(Decimal("1.50"), amounts)          # 3 cups milk -> 1.5

    def test_zero_rejected(self):
        with self.assertRaises(ValueError):
            self.recipe.scale_batch(0)

    def test_page(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("recipe_detail", args=[self.recipe.id]), {"servings": 8})
        self.assertContains(resp, "Ingredients for 8 servings")
        self.assertContains(resp, "4 c Flour")


class MissingIngredientsTests(PantryTestBase):     # UC 53
    def test_empty_pantry(self):
        pantry = Pantry(self.user)
        self.assertEqual(len(self.recipe.get_missing_ingredients(pantry)), 3)
        self.assertFalse(pantry.check_recipe_ingredients(self.recipe))

    def test_short_and_unit_mismatch(self):
        pantry = Pantry.create(self.user, [(self.flour, self.cup, 3), (self.milk, self.cup, 1), (self.egg, self.gram, 100)])
        missing = {ing.name: (needed, have) for ing, _, needed, have in self.recipe.get_missing_ingredients(pantry)}
        self.assertNotIn("Flour", missing)
        self.assertEqual(missing["Milk"], (Decimal("3.00"), 1))
        self.assertEqual(missing["Egg"][1], 0)           # grams vs "each" counts as missing

    def test_scaled_batch(self):
        pantry = Pantry.create(self.user, [(self.flour, self.cup, 3), (self.milk, self.cup, 6), (self.egg, self.each, 2)])
        self.assertTrue(pantry.check_recipe_ingredients(self.recipe))
        names = [ing.name for ing, _, _, _ in self.recipe.get_missing_ingredients(pantry, 2)]
        self.assertEqual(names, ["Flour", "Egg"])
