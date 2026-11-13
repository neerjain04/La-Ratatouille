"""
Tests for Aiden's use cases (SRS section 3.1).

    Adjust Batch Size ......................... AdjustBatchSizeTests
    Edit Ingredient in Pantry ................. EditPantryTests, PantryFoodGroupTests
    Determine Missing Ingredients ............. MissingIngredientsTests
    Create Pantry ............................. CreatePantryTests
    Delete Pantry ............................. DeletePantryTests
    Generate Recipe Using AI .................. RecipeAITests, AIRecipePageTests
    Save Recipe Created by AI ................. AIRecipePageTests
    Training the AI on the dataset ............ TrainRecipeAICommandTests
    Dataset ingredients and food groups ....... FoodGroupRuleTests, LoadIngredientsCommandTests
    The shared recipe page .................... RecipeDetailPageTests

Run all of these:      python manage.py test la_ratatouille_app.test_use_cases
Run one use case:      python manage.py test la_ratatouille_app.test_use_cases.DeletePantryTests
Run the whole app:     python manage.py test la_ratatouille_app
"""
import csv
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from .food_groups import RULES, count_dataset_ingredients, food_group_for, name_key, read_dataset_recipes
from .forms import PantryItemForm
from .management.commands.load_ingredients import BUNDLED_LIST
from .models import Ingredient, Recipe, RecipeIngredient, Review, Unit, UserIngredient
from .pantry import Pantry
from .recipe_ai import DRAFT_SESSION_KEY, MODEL_PATH, RecipeAI, save_draft

FoodGroup = Ingredient.FoodGroup


class PantryTestBase(TestCase):
    """Two users, three units, and a pancake recipe (4 servings: 2 c flour, 3 c milk, 2 eggs)."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("ann", password="pw-123456!")
        self.other_user = User.objects.create_user("bob", password="pw-123456!")
        self.cup = Unit.objects.create(name="cup", abbr="c")
        self.gram = Unit.objects.create(name="gram", abbr="g")
        self.each = Unit.objects.create(name="each", abbr="ea")
        self.flour = Ingredient.objects.create(name="Flour", food_group=FoodGroup.GRAIN)
        self.milk = Ingredient.objects.create(name="Milk", food_group=FoodGroup.DAIRY)
        self.egg = Ingredient.objects.create(name="Egg", food_group=FoodGroup.PROTEIN)
        self.recipe = Recipe.objects.create(
            name="Pancakes", instructions="Mix and cook.", calories_per_serving=200,
            num_servings=4, prep_time=20, user=self.user,
        )
        RecipeIngredient.objects.create(recipe=self.recipe, ingredient=self.flour, unit=self.cup, quantity=2)
        RecipeIngredient.objects.create(recipe=self.recipe, ingredient=self.milk, unit=self.cup, quantity=3)
        RecipeIngredient.objects.create(recipe=self.recipe, ingredient=self.egg, unit=self.each, quantity=2)
        self.recipe_url = reverse("recipe_detail", args=[self.recipe.id])


# ---------------------------------------------------------------------------- Create Pantry
class CreatePantryTests(PantryTestBase):

    def test_new_user_starts_with_empty_pantry(self):
        pantry = Pantry(self.user)
        self.assertEqual(pantry.items().count(), 0)
        self.assertEqual(pantry.ingredients().count(), 0)

    def test_create_with_starting_items(self):
        pantry = Pantry.create(self.user, [(self.flour, self.cup, 3), (self.egg, self.each, 6)])
        self.assertEqual(pantry.items().count(), 2)
        self.assertEqual(set(pantry.ingredients()), {self.flour, self.egg})
        self.assertEqual(UserIngredient.objects.get(user=self.user, ingredient=self.egg).quantity, 6)

    def test_create_without_items_saves_nothing(self):
        Pantry.create(self.user)
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_create_rejects_negative_starting_amount(self):
        with self.assertRaises(ValueError):
            Pantry.create(self.user, [(self.flour, self.cup, -2)])

    def test_each_user_has_own_pantry(self):
        Pantry.create(self.user, [(self.flour, self.cup, 3)])
        self.assertEqual(Pantry(self.other_user).items().count(), 0)

    def test_empty_pantry_page(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("pantry"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Your pantry is empty")
        self.assertNotContains(resp, "Delete my pantry")

    def test_pantry_page_requires_login(self):
        resp = self.client.get(reverse("pantry"))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('pantry')}")


# ---------------------------------------------------------------------------- Edit Ingredient in Pantry
class EditPantryTests(PantryTestBase):

    def test_add_new_ingredient(self):
        item = Pantry(self.user).add_ingredient(self.flour, 2, self.cup)
        self.assertEqual((item.ingredient, item.quantity, item.unit), (self.flour, 2, self.cup))
        self.assertTrue(UserIngredient.objects.filter(user=self.user, ingredient=self.flour).exists())

    def test_change_amount_updates_same_row(self):
        pantry = Pantry(self.user)
        pantry.add_ingredient(self.flour, 1, self.cup)
        pantry.add_ingredient(self.flour, 5, self.cup)
        self.assertEqual(UserIngredient.objects.filter(user=self.user, ingredient=self.flour).count(), 1)
        self.assertEqual(UserIngredient.objects.get(user=self.user, ingredient=self.flour).quantity, 5)

    def test_change_unit(self):
        pantry = Pantry(self.user)
        pantry.add_ingredient(self.flour, 2, self.cup)
        pantry.add_ingredient(self.flour, 250, self.gram)
        self.assertEqual(UserIngredient.objects.get(user=self.user, ingredient=self.flour).unit, self.gram)

    def test_amount_given_as_text(self):
        self.assertEqual(Pantry(self.user).add_ingredient(self.flour, "3", self.cup).quantity, 3)

    def test_amount_zero_removes_ingredient(self):
        pantry = Pantry(self.user)
        pantry.add_ingredient(self.flour, 1, self.cup)
        self.assertIsNone(pantry.add_ingredient(self.flour, 0, self.cup))
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_amount_zero_for_missing_ingredient_is_harmless(self):
        self.assertIsNone(Pantry(self.user).add_ingredient(self.milk, 0, self.cup))
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_negative_amount_rejected(self):
        with self.assertRaises(ValueError):
            Pantry(self.user).add_ingredient(self.flour, -1, self.cup)
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_remove_ingredient(self):
        pantry = Pantry(self.user)
        pantry.add_ingredient(self.flour, 1, self.cup)
        self.assertTrue(pantry.remove_ingredient(self.flour))
        self.assertFalse(pantry.remove_ingredient(self.flour))

    def test_remove_only_touches_this_user(self):
        Pantry(self.user).add_ingredient(self.flour, 1, self.cup)
        Pantry(self.other_user).add_ingredient(self.flour, 4, self.cup)
        Pantry(self.user).remove_ingredient(self.flour)
        self.assertEqual(UserIngredient.objects.get(user=self.other_user, ingredient=self.flour).quantity, 4)

    def test_page_adds_ingredient(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("pantry"), {"ingredient": self.milk.id, "quantity": 2, "unit": self.cup.id})
        self.assertRedirects(resp, reverse("pantry"))
        self.assertEqual(UserIngredient.objects.get(user=self.user, ingredient=self.milk).quantity, 2)
        self.assertContains(self.client.get(reverse("pantry")), "2 c")

    def test_page_updates_amount_and_shows_message(self):
        self.client.force_login(self.user)
        self.client.post(reverse("pantry"), {"ingredient": self.milk.id, "quantity": 2, "unit": self.cup.id})
        resp = self.client.post(reverse("pantry"), {"ingredient": self.milk.id, "quantity": 7, "unit": self.cup.id},
                                follow=True)
        self.assertContains(resp, "Pantry now has 7 c Milk.")
        self.assertEqual(UserIngredient.objects.filter(user=self.user).count(), 1)

    def test_page_amount_zero_removes(self):
        Pantry(self.user).add_ingredient(self.milk, 2, self.cup)
        self.client.force_login(self.user)
        resp = self.client.post(reverse("pantry"), {"ingredient": self.milk.id, "quantity": 0}, follow=True)
        self.assertContains(resp, "Removed Milk.")
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_page_rejects_negative_amount(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("pantry"), {"ingredient": self.milk.id, "quantity": -1})
        self.assertEqual(resp.status_code, 200)                 # form shown again with an error
        self.assertTrue(resp.context["form"].errors)
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_page_rejects_unknown_ingredient(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("pantry"), {"ingredient": 99999, "quantity": 1})
        self.assertIn("ingredient", resp.context["form"].errors)
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_remove_button(self):
        Pantry(self.user).add_ingredient(self.flour, 1, self.cup)
        self.client.force_login(self.user)
        resp = self.client.post(reverse("pantry_remove_item", args=[self.flour.id]), follow=True)
        self.assertContains(resp, "Removed Flour from your pantry.")
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_remove_button_needs_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("pantry_remove_item", args=[self.flour.id])).status_code, 405)

    def test_remove_unknown_ingredient_is_404(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("pantry_remove_item", args=[99999])).status_code, 404)


class PantryFoodGroupTests(PantryTestBase):
    """The ingredient menu and the pantry list are split by food group."""

    def test_menu_split_into_food_groups_in_order(self):
        choices = list(PantryItemForm().fields["ingredient"].choices)
        self.assertEqual(choices[0], ("", "---------"))
        self.assertEqual([label for label, _ in choices[1:]],
                         [FoodGroup.PROTEIN.label, FoodGroup.DAIRY.label, FoodGroup.GRAIN.label])
        self.assertEqual(dict(choices[1:])[FoodGroup.DAIRY.label], [(self.milk.pk, "Milk")])

    def test_ingredient_without_group_listed_under_other(self):
        mystery = Ingredient.objects.create(name="Mystery")
        self.assertEqual(mystery.food_group, FoodGroup.OTHER)
        last_label, last_options = list(PantryItemForm().fields["ingredient"].choices)[-1]
        self.assertEqual((last_label, last_options), ("Other", [(mystery.pk, "Mystery")]))

    def test_grouped_menu_still_validates(self):
        form = PantryItemForm({"ingredient": self.milk.pk, "quantity": 2, "unit": self.cup.pk})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["ingredient"], self.milk)

    def test_page_menu_has_optgroups(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("pantry"))
        self.assertContains(resp, '<optgroup label="Dairy &amp; alternatives">')
        self.assertContains(resp, '<optgroup label="Proteins (meat, seafood, eggs, tofu)">')

    def test_pantry_list_under_group_headings(self):
        Pantry.create(self.user, [(self.flour, self.cup, 3), (self.milk, self.cup, 1), (self.egg, self.each, 6)])
        self.client.force_login(self.user)
        table = self.client.get(reverse("pantry")).content.decode().split("<table>")[1].split("</table>")[0]
        order = [table.index(text) for text in
                 ("Proteins", "Egg", "Dairy &amp; alternatives", "Milk", "Grains, flours &amp; bread", "Flour")]
        self.assertEqual(order, sorted(order))


# ---------------------------------------------------------------------------- Adjust Batch Size
class AdjustBatchSizeTests(PantryTestBase):

    def amounts(self, multiplier):
        return [amount for _, _, amount in self.recipe.scale_batch(multiplier)]

    def test_same_size_unchanged(self):
        self.assertEqual(self.amounts(1), [Decimal("2.00"), Decimal("3.00"), Decimal("2.00")])

    def test_double(self):
        self.assertEqual(self.amounts(2), [Decimal("4.00"), Decimal("6.00"), Decimal("4.00")])

    def test_half_keeps_fractions(self):
        self.assertEqual(self.amounts(Decimal("0.5")), [Decimal("1.00"), Decimal("1.50"), Decimal("1.00")])

    def test_multiplier_for_servings(self):
        self.assertEqual(self.recipe.multiplier_for(8), 2)
        self.assertEqual(self.recipe.multiplier_for(4), 1)
        self.assertEqual(self.recipe.multiplier_for(6), Decimal("1.5"))

    def test_zero_and_negative_rejected(self):
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                self.recipe.scale_batch(bad)

    def test_scaling_does_not_change_saved_recipe(self):
        self.recipe.scale_batch(3)
        self.assertEqual(sorted(self.recipe.recipe_ingredients.values_list("quantity", flat=True)), [2, 2, 3])

    def test_page_default_servings(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.recipe_url)
        self.assertContains(resp, "Ingredients for 4 servings")
        self.assertContains(resp, "2 c Flour")

    def test_page_scaled_up(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.recipe_url, {"servings": 8})
        self.assertContains(resp, "Ingredients for 8 servings")
        self.assertContains(resp, "4 c Flour")
        self.assertContains(resp, "6 c Milk")

    def test_page_scaled_down_shows_fraction(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.recipe_url, {"servings": 2})
        self.assertContains(resp, "1.50 c Milk")

    def test_page_bad_servings_falls_back_to_recipe(self):
        self.client.force_login(self.user)
        for bad in ("0", "501", "abc"):
            resp = self.client.get(self.recipe_url, {"servings": bad})
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "Ingredients for 4 servings")


# ---------------------------------------------------------------------------- Determine Missing Ingredients
class MissingIngredientsTests(PantryTestBase):

    def missing_names(self, pantry, multiplier=1):
        return [ingredient.name for ingredient, _, _, _ in self.recipe.get_missing_ingredients(pantry, multiplier)]

    def test_empty_pantry_missing_everything(self):
        pantry = Pantry(self.user)
        self.assertEqual(self.missing_names(pantry), ["Flour", "Milk", "Egg"])
        self.assertFalse(pantry.check_recipe_ingredients(self.recipe))

    def test_full_pantry_missing_nothing(self):
        pantry = Pantry.create(self.user, [(self.flour, self.cup, 2), (self.milk, self.cup, 3), (self.egg, self.each, 2)])
        self.assertEqual(self.recipe.get_missing_ingredients(pantry), [])
        self.assertTrue(pantry.check_recipe_ingredients(self.recipe))

    def test_short_amount_reports_need_and_have(self):
        pantry = Pantry.create(self.user, [(self.flour, self.cup, 3), (self.milk, self.cup, 1), (self.egg, self.each, 2)])
        self.assertEqual(self.recipe.get_missing_ingredients(pantry), [(self.milk, self.cup, Decimal("3.00"), 1)])

    def test_different_unit_counts_as_missing(self):
        pantry = Pantry.create(self.user, [(self.flour, self.cup, 3), (self.milk, self.cup, 3), (self.egg, self.gram, 100)])
        self.assertEqual(self.recipe.get_missing_ingredients(pantry), [(self.egg, self.each, Decimal("2.00"), 0)])

    def test_extra_pantry_items_ignored(self):
        salt = Ingredient.objects.create(name="Salt", food_group=FoodGroup.HERB_SPICE)
        pantry = Pantry.create(self.user, [(salt, self.gram, 10)])
        self.assertNotIn("Salt", self.missing_names(pantry))

    def test_bigger_batch_needs_more(self):
        pantry = Pantry.create(self.user, [(self.flour, self.cup, 3), (self.milk, self.cup, 6), (self.egg, self.each, 2)])
        self.assertTrue(pantry.check_recipe_ingredients(self.recipe))
        self.assertEqual(self.missing_names(pantry, 2), ["Flour", "Egg"])
        self.assertFalse(pantry.check_recipe_ingredients(self.recipe, 2))

    def test_other_users_pantry_not_counted(self):
        Pantry.create(self.other_user, [(self.flour, self.cup, 9), (self.milk, self.cup, 9), (self.egg, self.each, 9)])
        self.assertEqual(len(self.missing_names(Pantry(self.user))), 3)

    def test_page_lists_missing(self):
        Pantry.create(self.user, [(self.flour, self.cup, 2)])
        self.client.force_login(self.user)
        resp = self.client.get(self.recipe_url)
        self.assertContains(resp, "What you're missing")
        self.assertContains(resp, "Milk: need 3 c, you have 0")
        self.assertNotContains(resp, "Flour: need")

    def test_page_everything_present(self):
        Pantry.create(self.user, [(self.flour, self.cup, 2), (self.milk, self.cup, 3), (self.egg, self.each, 2)])
        self.client.force_login(self.user)
        self.assertContains(self.client.get(self.recipe_url), "You have everything you need.")

    def test_page_uses_batch_size(self):
        Pantry.create(self.user, [(self.flour, self.cup, 3), (self.milk, self.cup, 6), (self.egg, self.each, 4)])
        self.client.force_login(self.user)
        resp = self.client.get(self.recipe_url, {"servings": 8})
        self.assertContains(resp, "Flour: need 4 c, you have 3")



# ---------------------------------------------------------------------------- Delete Pantry
class DeletePantryTests(PantryTestBase):

    def fill(self, user):
        return Pantry.create(user, [(self.flour, self.cup, 3), (self.milk, self.cup, 1)])

    def test_delete_removes_every_item_and_returns_count(self):
        self.assertEqual(self.fill(self.user).delete(), 2)
        self.assertEqual(UserIngredient.objects.filter(user=self.user).count(), 0)

    def test_delete_empty_pantry_returns_zero(self):
        self.assertEqual(Pantry(self.user).delete(), 0)

    def test_delete_keeps_ingredients_and_recipes(self):
        self.fill(self.user).delete()
        self.assertEqual(Ingredient.objects.count(), 3)
        self.assertEqual(self.recipe.recipe_ingredients.count(), 3)

    def test_delete_only_this_users_pantry(self):
        self.fill(self.user)
        self.fill(self.other_user)
        Pantry(self.user).delete()
        self.assertEqual(Pantry(self.other_user).items().count(), 2)

    def test_pantry_usable_after_delete(self):
        pantry = self.fill(self.user)
        pantry.delete()
        pantry.add_ingredient(self.egg, 6, self.each)
        self.assertEqual(pantry.items().count(), 1)

    def test_get_shows_confirmation_and_deletes_nothing(self):
        self.fill(self.user)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("pantry_delete")), "Delete your pantry?")
        self.assertEqual(UserIngredient.objects.count(), 2)

    def test_post_deletes_and_shows_message(self):
        self.fill(self.user)
        self.client.force_login(self.user)
        resp = self.client.post(reverse("pantry_delete"), follow=True)
        self.assertRedirects(resp, reverse("pantry"))
        self.assertContains(resp, "Deleted your pantry (2 ingredients).")
        self.assertEqual(UserIngredient.objects.count(), 0)

    def test_requires_login(self):
        self.fill(self.user)
        resp = self.client.post(reverse("pantry_delete"))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('pantry_delete')}")
        self.assertEqual(UserIngredient.objects.count(), 2)

    def test_delete_link_only_when_pantry_has_items(self):
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(reverse("pantry")), "Delete my pantry")
        self.fill(self.user)
        self.assertContains(self.client.get(reverse("pantry")), "Delete my pantry")


# ---------------------------------------------------------------------------- Dataset ingredients and food groups
class FoodGroupRuleTests(TestCase):

    def test_examples(self):
        expected = {
            "Whole Eggs": "protein", "Chicken breasts": "protein", "Tofu": "protein", "spam": "protein",
            "Chana dal (Bengal Gram Dal)": "legume", "Rajma (Large Kidney Beans)": "legume",
            "Milk": "dairy", "Hung Curd (Greek Yogurt)": "dairy", "Coconut milk": "dairy",
            "Onion": "vegetable", "Brinjal (Baingan / Eggplant)": "vegetable", "Banana Stem": "vegetable",
            "Mango (Ripe)": "fruit", "Lemon": "fruit",
            "Basmati rice": "grain", "Egg noodles": "grain", "Gram flour (besan)": "grain",
            "Cashew nuts": "nut_seed", "Flax seed powder (flax meal)": "nut_seed",
            "Mustard seeds": "herb_spice", "Amchur (Dry Mango Powder)": "herb_spice",
            "Kalonji (Onion Nigella Seeds)": "herb_spice", "Black cardamom (Badi Elaichi)": "herb_spice",
            "Mustard oil": "oil_fat", "Dijon Mustard": "condiment", "Tomato Ketchup": "condiment",
            "Cocoa Powder": "baking", "Jaggery": "baking", "Instant Coffee Powder": "beverage",
            "Toothpicks": "other",
        }
        self.assertEqual({name: food_group_for(name) for name in expected}, expected)

    def test_every_rule_uses_a_real_food_group(self):
        for group, _ in RULES:
            self.assertIn(group, FoodGroup.values)

    def test_name_key_merges_spellings(self):
        for a, b in [("Onion", "Onions"), ("Lemongrass", "Lemon Grass"), ("Bay leaf", "Bay leaves"),
                     ("Mustard seeds", "Mustard seeds (Rai/ Kadugu)"), ("Green Chilli", "Green Chillies")]:
            self.assertEqual(name_key(a), name_key(b), (a, b))
        self.assertNotEqual(name_key("Cumin seeds (Jeera)"), name_key("Cumin powder (Jeera)"))

    def test_bundled_list_is_clean(self):
        with open(BUNDLED_LIST, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        names = [row["name"] for row in rows]
        self.assertGreater(len(rows), 300)
        self.assertEqual(len({n.lower() for n in names}), len(names))         # no duplicates
        self.assertTrue(all(n.isascii() and 0 < len(n) <= 50 for n in names))
        self.assertTrue(all(row["food_group"] in FoodGroup.values for row in rows))
        self.assertNotIn("water", {n.lower() for n in names})


class LoadIngredientsCommandTests(TestCase):

    def load(self, *args, **options):
        out = StringIO()
        call_command("load_ingredients", *args, stdout=out, **options)
        return out.getvalue()

    def test_loads_bundled_list_with_groups(self):
        self.load()
        with open(BUNDLED_LIST, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(Ingredient.objects.count(), len(rows))
        self.assertEqual(Ingredient.objects.get(name="Salt").food_group, "herb_spice")
        self.assertEqual(Ingredient.objects.get(name="Whole Eggs").food_group, "protein")
        self.assertEqual(Ingredient.objects.get(name="Milk").food_group, "dairy")
        self.assertGreaterEqual(Ingredient.objects.values("food_group").distinct().count(), 10)

    def test_running_twice_adds_nothing(self):
        self.load()
        count = Ingredient.objects.count()
        self.assertIn("0 added", self.load())
        self.assertEqual(Ingredient.objects.count(), count)

    def test_existing_ingredient_not_duplicated_and_gets_group(self):
        Ingredient.objects.create(name="salt")
        self.load()
        self.assertEqual(Ingredient.objects.filter(name__iexact="salt").count(), 1)
        self.assertEqual(Ingredient.objects.get(name__iexact="salt").food_group, "herb_spice")

    def test_hand_added_ingredients_get_group(self):
        for name in ("spam", "bacon", "Mystery dust"):
            Ingredient.objects.create(name=name)
        self.load()
        self.assertEqual(Ingredient.objects.get(name="spam").food_group, "protein")
        self.assertEqual(Ingredient.objects.get(name="bacon").food_group, "protein")
        self.assertEqual(Ingredient.objects.get(name="Mystery dust").food_group, "other")

    def test_chosen_group_not_overwritten(self):
        Ingredient.objects.create(name="Honey", food_group=FoodGroup.CONDIMENT)
        self.load()
        self.assertEqual(Ingredient.objects.get(name="Honey").food_group, "condiment")

    def test_min_recipes_limits_list(self):
        with open(BUNDLED_LIST, newline="", encoding="utf-8") as f:
            common = sum(1 for row in csv.DictReader(f) if int(row["recipe_count"]) >= 1000)
        self.load(min_recipes=1000)
        self.assertEqual(Ingredient.objects.count(), common)

    def test_units_added_once_without_clashing(self):
        Unit.objects.create(name="cup", abbr="c")
        self.load()
        count = Unit.objects.count()
        self.assertEqual(Unit.objects.filter(name="cup").count(), 1)
        self.assertTrue(Unit.objects.filter(abbr="tsp").exists())
        self.load()
        self.assertEqual(Unit.objects.count(), count)

    def test_dataset_option_reads_raw_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "food_recipes.csv"
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["recipe_title", "ingredients"])
                writer.writerow(["A", "Onions|Salt|Water|Paneer"])
                writer.writerow(["B", "Onion|Salt|नमक"])
                writer.writerow(["C", "Onion|Chicken"])
            self.assertEqual(count_dataset_ingredients(path)[0], ("Onion", "vegetable", 3))
            self.load(dataset=str(path), min_recipes=2)
        self.assertEqual(sorted(Ingredient.objects.values_list("name", flat=True)), ["Onion", "Salt"])

    def test_dataset_option_missing_file(self):
        with self.assertRaises(CommandError):
            self.load(dataset="/no/such/file.csv")


# ---------------------------------------------------------------------------- The shared recipe page
class RecipeDetailPageTests(PantryTestBase):
    """One recipe page holds Jenna's reviews and favorites plus batch size and missing ingredients."""

    def test_one_url_for_recipe_detail(self):
        self.assertEqual(self.recipe_url, f"/recipe/{self.recipe.id}/")

    def test_reviews_and_batch_size_on_same_page(self):
        Review.objects.create(user=self.user, recipe=self.recipe, rating=5, comment="Fluffy!")
        self.client.force_login(self.user)
        resp = self.client.get(self.recipe_url, {"servings": 8})
        self.assertContains(resp, "Fluffy!")
        self.assertContains(resp, "Favorite Recipe")
        self.assertContains(resp, "Ingredients for 8 servings")
        self.assertContains(resp, "What you're missing")
        self.assertContains(resp, "Submit Review")

    def test_logged_out_visitor_sent_to_login(self):
        resp = self.client.get(self.recipe_url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_add_comment_redirects_back_to_recipe(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("add_comment", args=[self.recipe.id]), {"rating": 4, "comment": "Good"})
        self.assertRedirects(resp, self.recipe_url)


# ---------------------------------------------------------------------------- Recipe AI
# A tiny training set so these tests are fast and predictable: (title, ingredients, steps, minutes).
SAMPLE_RECIPES = [
    ("Paneer Butter Masala Recipe", ["Paneer", "Butter", "Onions", "Tomatoes", "Salt"],
     ["Heat the butter in a pan.", "Add the onions and saute until soft.", "Add the tomatoes and cook until mushy.",
      "Add the paneer and simmer for five minutes.", "Season with salt to taste and serve."], 30),
    ("Tomato Onion Curry Recipe", ["Onion", "Tomatoes", "Sunflower Oil", "Salt", "Garlic"],
     ["Heat the oil in a kadai.", "Add the garlic and saute for a minute.", "Add the onion and cook until golden.",
      "Add the tomatoes and cook until soft.", "Add salt and stir well to combine."], 40),
    ("Garlic Rice Recipe", ["Basmati rice", "Garlic", "Sunflower Oil", "Salt", "Onion"],
     ["Heat the oil in a pan.", "Add the garlic and fry until golden.", "Add the onion and saute until soft.",
      "Add the rice and stir to coat.", "Add salt and cook covered until done."], 25),
    ("Paneer Tikka Recipe", ["Paneer", "Onion", "Salt", "Sunflower Oil"],
     ["Heat the oil in a grill pan.", "Add the onion and paneer and roast until charred.",
      "Sprinkle salt and serve."], 20),
    ("टमाटर करी", ["टमाटर", "Salt"], ["टमाटर डालें।"], 10),          # Hindi: skipped
]


class RecipeAITests(TestCase):

    def setUp(self):
        self.ai = RecipeAI.train(SAMPLE_RECIPES, min_recipes=1)
        self.known = self.ai.data["ingredients"]

    def test_learns_ingredients_and_what_goes_together(self):
        self.assertEqual(self.ai.data["trained_on"], 4)                  # the Hindi recipe is skipped
        self.assertEqual(self.known["onion"]["name"], "Onion")           # "Onion"/"Onions" merged
        self.assertEqual(self.known["paneer"]["goes_with"]["onion"], 2)
        self.assertNotIn("basmatirice", self.known["paneer"]["goes_with"])

    def test_learns_step_order_and_sentences(self):
        self.assertLess(self.known["sunfloweroil"]["position"], self.known["salt"]["position"])
        self.assertIn("Add the tomatoes and cook until soft.", self.known["tomato"]["sentences"])

    def test_learns_dish_names_and_times(self):
        self.assertEqual(self.known["paneer"]["dishes"], {"masala": 1, "tikka": 1})
        self.assertEqual(self.ai.data["dish_minutes"]["curry"], 40)

    def test_same_seed_same_recipe(self):
        self.assertEqual(self.ai.generate(["Paneer"], seed=7), self.ai.generate(["Paneer"], seed=7))

    def test_must_include_and_pantry(self):
        draft = self.ai.generate(pantry=["Onion", "Tomatoes"], must_include=["Paneer"], size=4, seed=1)
        names = [line["name"] for line in draft["ingredients"]]
        self.assertIn("Paneer", names)
        self.assertTrue(draft["name"].startswith("Paneer"))
        self.assertTrue(set(draft["from_pantry"]) <= {"Onion", "Tomatoes"})

    def test_draft_fits_recipe_model(self):
        for seed in range(5):
            draft = self.ai.generate(servings=2, size=4, seed=seed)
            names = [line["name"] for line in draft["ingredients"]]
            self.assertLessEqual(len(draft["name"]), 50)
            self.assertEqual(len(names), len(set(names)))
            self.assertTrue(all(line["quantity"] >= 1 for line in draft["ingredients"]))
            self.assertEqual(draft["num_servings"], 2)
            self.assertIsInstance(draft["prep_time"], int)
            self.assertIsInstance(draft["calories_per_serving"], int)
            self.assertTrue(draft["instructions"].startswith("1. "))

    def test_more_servings_more_food(self):
        small = self.ai.generate(must_include=["Paneer"], servings=4, size=4, seed=3)
        big = self.ai.generate(must_include=["Paneer"], servings=8, size=4, seed=3)
        self.assertEqual([l["quantity"] * 2 for l in small["ingredients"]], [l["quantity"] for l in big["ingredients"]])

    def test_unlearned_ingredient_reported(self):
        draft = self.ai.generate(must_include=["Unicorn horn"], seed=1)
        self.assertEqual(draft["not_learned"], ["Unicorn horn"])

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.json"
            self.ai.save(path)
            self.assertEqual(RecipeAI.from_file(path).data, self.ai.data)

    def test_bundled_model_trained_on_dataset(self):
        ai = RecipeAI.from_file(MODEL_PATH)
        self.assertGreater(ai.data["trained_on"], 5000)
        self.assertGreater(len(ai.data["ingredients"]), 300)
        draft = ai.generate(["Onion", "Tomatoes", "Basmati rice"], seed=1)
        self.assertGreaterEqual(len(draft["ingredients"]), 4)


class AIRecipePageTests(PantryTestBase):
    """Generate and Save, through the pages (uses the bundled model)."""

    def generate(self, **options):
        data = {"servings": 4, "size": 6, "use_pantry": "on", **options}
        return self.client.post(reverse("ai_generate_recipe"), data)

    def test_needs_login(self):
        resp = self.client.get(reverse("ai_generate_recipe"))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('ai_generate_recipe')}")

    def test_form_with_grouped_menu(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("ai_generate_recipe"))
        self.assertContains(resp, "Make a recipe with AI")
        self.assertContains(resp, "Let the AI choose")
        self.assertContains(resp, '<optgroup label="Dairy &amp; alternatives">')
        self.assertNotContains(resp, "Save this recipe")

    def test_generate_shows_draft_and_keeps_it(self):
        Pantry.create(self.user, [(self.milk, self.cup, 2)])
        self.client.force_login(self.user)
        resp = self.generate(main_ingredient=self.flour.id)
        self.assertContains(resp, "Save this recipe")
        draft = self.client.session[DRAFT_SESSION_KEY]
        self.assertIn("Flour", resp.context["draft"]["not_learned"] + [l["name"] for l in draft["ingredients"]])

    def test_bad_options_make_no_draft(self):
        self.client.force_login(self.user)
        resp = self.generate(servings=0)
        self.assertIsNone(resp.context["draft"])
        self.assertNotIn(DRAFT_SESSION_KEY, self.client.session)

    def test_save_creates_ai_recipe(self):
        self.client.force_login(self.user)
        self.generate()
        draft = self.client.session[DRAFT_SESSION_KEY]
        resp = self.client.post(reverse("ai_save_recipe"), follow=True)
        recipe = Recipe.objects.get(ai_generated=True)
        self.assertRedirects(resp, reverse("recipe_detail", args=[recipe.id]))
        self.assertEqual((recipe.user, recipe.name), (self.user, draft["name"][:50]))
        self.assertEqual(recipe.recipe_ingredients.count(), len(draft["ingredients"]))
        self.assertContains(resp, "Made with the La Ratatouille recipe AI.")
        self.assertContains(resp, f"Saved {escape(recipe.name)} to your recipes.")
        self.assertNotIn(DRAFT_SESSION_KEY, self.client.session)       # saving twice needs a new draft

    def test_save_without_draft(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("ai_save_recipe"))
        self.assertRedirects(resp, reverse("ai_generate_recipe"))
        self.assertFalse(Recipe.objects.filter(ai_generated=True).exists())

    def test_save_needs_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("ai_save_recipe")).status_code, 405)

    def test_save_draft_reuses_ingredients_and_units(self):
        draft = {"name": "Milk & Mystery Bowl", "instructions": "1. Mix.", "num_servings": 4, "prep_time": 10,
                 "calories_per_serving": 50, "ingredients": [
                     {"name": "milk", "food_group": "dairy", "quantity": 1, "unit": "cup"},
                     {"name": "Mystery Spice", "food_group": "herb_spice", "quantity": 1, "unit": "teaspoon"}]}
        recipe = save_draft(draft, self.user)
        self.assertTrue(recipe.ai_generated)
        lines = {ri.ingredient.name: ri for ri in recipe.recipe_ingredients.select_related("ingredient", "unit")}
        self.assertEqual(lines["Milk"].ingredient, self.milk)                 # matched "milk" to "Milk"
        self.assertEqual(lines["Milk"].unit, self.cup)
        self.assertIsNone(lines["Mystery Spice"].unit)                         # no "teaspoon" unit in this DB
        self.assertEqual(Ingredient.objects.get(name="Mystery Spice").food_group, "herb_spice")

    def test_normal_recipes_not_marked_ai(self):
        self.assertFalse(self.recipe.ai_generated)
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(self.recipe_url), "recipe AI")


class TrainRecipeAICommandTests(TestCase):

    def write_dataset(self, folder):
        path = Path(folder) / "food_recipes.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["recipe_title", "ingredients", "instructions", "prep_time", "cook_time"])
            for title, names, steps, minutes in SAMPLE_RECIPES:
                writer.writerow([title, "|".join(names), "|".join(steps), f"{minutes} M", "0 M"])
        return path

    def test_reads_dataset_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            first = next(read_dataset_recipes(self.write_dataset(folder)))
        self.assertEqual(first[0], "Paneer Butter Masala Recipe")
        self.assertEqual(first[1][0], "Paneer")
        self.assertEqual(first[3], 30)

    def test_trains_and_saves_model(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "model.json"
            out = StringIO()
            call_command("train_recipe_ai", dataset=str(self.write_dataset(folder)), min_recipes=2,
                         output=str(output), stdout=out)
            model = RecipeAI.from_file(output)
        self.assertIn("Trained on 4 recipes", out.getvalue())
        self.assertIn("paneer", model.data["ingredients"])
        self.assertNotIn("basmatirice", model.data["ingredients"])          # only in 1 recipe

    def test_include_site_recipes(self):
        user = get_user_model().objects.create_user("cook")
        recipe = Recipe.objects.create(name="Saffron Milk", instructions="Warm the milk.\nAdd the saffron.",
                                       calories_per_serving=100, num_servings=2, prep_time=5, user=user)
        for name in ("Saffron strands", "Milk"):
            RecipeIngredient.objects.create(recipe=recipe, ingredient=Ingredient.objects.create(name=name), quantity=1)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "model.json"
            call_command("train_recipe_ai", dataset=str(self.write_dataset(folder)), min_recipes=1,
                         include_site_recipes=True, output=str(output), stdout=StringIO())
            model = RecipeAI.from_file(output)
        self.assertEqual(model.data["trained_on"], 5)
        self.assertIn("saffronstrand", model.data["ingredients"])

    def test_missing_dataset(self):
        with self.assertRaises(CommandError):
            call_command("train_recipe_ai", dataset="/no/such/file.csv", stdout=StringIO())
