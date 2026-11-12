from django.test import TestCase
from django.contrib.auth.models import User
from .models import *
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from .pantry import Pantry


class SearchTests(TestCase):
    '''Test search page'''
    @classmethod
    def setUpTestData(cls):
        NUM_INGREDIENTS = 5
        INGREDIENT_NAMES = [f"ingredient_{i}" for i in range(1, NUM_INGREDIENTS + 1)]
        USERNAME = "emeril"

        # create a test user
        cls.user = User.objects.create_user(USERNAME)
        cls.user.save()

        # create ingredients
        cls.ingredients = [Ingredient(name=name) for name in INGREDIENT_NAMES]
        for ingredient in cls.ingredients:
            ingredient.save()

        # create recipes and add ingredients to them
        cls.recipes = []
        for i in range(1, NUM_INGREDIENTS):
            ingredients_slice = cls.ingredients[:i]
            recipe = Recipe(name=f"recipe_{i}", calories_per_serving=100 * i,
                             num_servings=i, prep_time=10 * i, user=cls.user)
            recipe.save()
            cls.recipes.append(recipe)
            # recipe_i has ingredients 1 through i - 1
            for ingredient in ingredients_slice:
                RecipeIngredient(recipe=recipe, ingredient=ingredient, quantity = 1).save()

        # add ingredients to user pantry
        UserIngredient(user=cls.user, ingredient=cls.ingredients[0], quantity=1).save()
        UserIngredient(user=cls.user, ingredient=cls.ingredients[2], quantity=1).save()

    def setUp(self):
        # log in test user without password
        self.client.force_login(user=self.user)
        
    def test_search_by_ingredient(self):
        '''Test search by ingredient'''
        response = self.client.get("/search/", query_params={"ingredients": [2]})
        self.assertEqual(len(response.context.get("recipes")), 3, f"expected 3 recipes with ingredient 2")
        response = self.client.get("/search/", query_params={"ingredients": [4]})
        self.assertEqual(len(response.context.get("recipes")), 1, f"expected 1 recipes with ingredient 4")
        response = self.client.get("/search/", query_params={"ingredients": [5]})
        self.assertEqual(len(response.context.get("recipes")), 0, f"expected 1 recipes with ingredient 5")
                
    def test_search_count_missing_ingredient(self):
        '''Test count of missing ingredients'''
        response = self.client.get("/search/", query_params={"ingredients": 1})
        recipes = response.context.get("recipes")
        r1 = recipes[0]
        r3 = recipes[2]
        r4 = recipes[3]
        self.assertEqual(r1.count_missing_ingredients, 0, "Expected 0 missing ingredients for " + r1.name)
        self.assertEqual(r3.count_missing_ingredients, 1, "Expected 1 missing ingredients for " + r3.name)
        self.assertEqual(r4.count_missing_ingredients, 2, "Expected 2 missing ingredients for " + r4.name)
       
    def test_dietary_restriction(self):
        '''Test filtering by dietary restriction'''
        vegan_tag = Tag(name="vegan")
        vegan_tag.save()
        gluten_free_tag = Tag(name="gluten free")
        gluten_free_tag.save()
        RecipeTag(recipe=self.recipes[0], tag=vegan_tag).save()
        RecipeTag(recipe=self.recipes[1], tag=vegan_tag).save()
        RecipeTag(recipe=self.recipes[1], tag=gluten_free_tag).save()
        RecipeTag(recipe=self.recipes[2], tag=gluten_free_tag).save()
        UserTag(user=self.user, tag=vegan_tag).save()
        response = self.client.get("/search/", query_params={"ingredients": 1})
        self.assertEqual(len(response.context.get("recipes")), 2, "Expect 2 vegan recipes")
        UserTag(user=self.user, tag=gluten_free_tag).save()
        self.assertEqual(len(response.context.get("recipes")), 2,
                         "Expect 1 recipe that is both vegan and gluten free")

    def test_search_by_prep_time(self):
        '''Test filtering by prep time'''
        response = self.client.get("/search/", query_params={"max_prep_time": 1})
        self.assertEqual(len(response.context.get("recipes")), 0,
                                 "Expect 0 recipes with max prep time 1")
        response = self.client.get("/search/", query_params={"max_prep_time": 10})
        self.assertEqual(len(response.context.get("recipes")), 1,
                                         "Expect 1 recipes with max prep time 10")
        response = self.client.get("/search/", query_params={"max_prep_time": 39})
        self.assertEqual(len(response.context.get("recipes")), 3,
                                         "Expect 3 recipes with max prep time 39")


"""
Tests for the pantry use cases (UC 51-55). Run with:
    python manage.py test la_ratatouille_app
"""



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


class RecipeManagementTests(TestCase):
    """Exercise the five assigned recipe use cases and their existing integrations."""

    def setUp(self):
        self.user = User.objects.create_user(username="cook")
        self.other = User.objects.create_user(username="other")
        self.tomato = Ingredient.objects.create(name="Tomato")
        self.onion = Ingredient.objects.create(name="Onion")
        self.unit = Unit.objects.create(name="each", abbr="ea")
        self.tag = Tag.objects.create(name="Dinner")
        self.client.force_login(self.user)

    def recipe_data(self):
        return {
            "name": "Soup", "instructions": "Cook the vegetables.",
            "calories_per_serving": "100", "num_servings": "2", "prep_time": "15",
            "tags": [str(self.tag.pk)],
            "recipe_ingredients-TOTAL_FORMS": "2",
            "recipe_ingredients-INITIAL_FORMS": "0",
            "recipe_ingredients-MIN_NUM_FORMS": "1",
            "recipe_ingredients-MAX_NUM_FORMS": "1000",
            "recipe_ingredients-0-ingredient": str(self.tomato.pk),
            "recipe_ingredients-0-quantity": "2",
            "recipe_ingredients-0-unit": str(self.unit.pk),
            "recipe_ingredients-1-ingredient": str(self.onion.pk),
            "recipe_ingredients-1-quantity": "1",
            "recipe_ingredients-1-unit": str(self.unit.pk),
        }

    def make_recipe(self, user=None):
        recipe = Recipe.objects.create(
            name="Soup", instructions="Cook.", calories_per_serving=100,
            num_servings=2, prep_time=15, user=user or self.user,
        )
        RecipeIngredient.objects.create(recipe=recipe, ingredient=self.tomato, quantity=2, unit=self.unit)
        return recipe

    def test_create_recipe_and_ingredients(self):
        response = self.client.post(reverse("recipe_create"), self.recipe_data())
        recipe = Recipe.objects.get(name="Soup")
        self.assertRedirects(response, reverse("recipe_detail", args=[recipe.pk]))
        self.assertEqual(recipe.user, self.user)
        self.assertEqual(recipe.recipe_ingredients.count(), 2)
        self.assertEqual(list(recipe.tags.all()), [self.tag])
        self.assertContains(self.client.get(reverse("my_recipes")), "Soup")

    def test_invalid_recipe_shows_errors_and_saves_nothing(self):
        data = self.recipe_data()
        data["name"] = ""
        data["recipe_ingredients-0-quantity"] = "0"
        response = self.client.post(reverse("recipe_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        self.assertContains(response, "Ensure this value is greater than or equal to 1")
        self.assertFalse(Recipe.objects.exists())

    def test_create_rejects_duplicate_ingredients(self):
        data = self.recipe_data()
        data["recipe_ingredients-1-ingredient"] = str(self.tomato.pk)
        response = self.client.post(reverse("recipe_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Recipe.objects.exists())

    def test_edit_updates_recipe_and_ingredients(self):
        recipe = self.make_recipe()
        item = recipe.recipe_ingredients.get()
        data = self.recipe_data()
        data["name"] = "Updated soup"
        data["recipe_ingredients-INITIAL_FORMS"] = "1"
        data["recipe_ingredients-0-id"] = str(item.pk)
        data["recipe_ingredients-0-quantity"] = "4"
        response = self.client.post(reverse("recipe_edit", args=[recipe.pk]), data)
        self.assertRedirects(response, reverse("recipe_detail", args=[recipe.pk]))
        recipe.refresh_from_db()
        self.assertEqual(recipe.name, "Updated soup")
        self.assertEqual(recipe.recipe_ingredients.get(ingredient=self.tomato).quantity, 4)
        self.assertEqual(recipe.recipe_ingredients.count(), 2)

    def test_edit_can_replace_an_ingredient(self):
        recipe = self.make_recipe()
        item = recipe.recipe_ingredients.get()
        data = self.recipe_data()
        data["recipe_ingredients-INITIAL_FORMS"] = "1"
        data["recipe_ingredients-0-id"] = str(item.pk)
        data["recipe_ingredients-0-DELETE"] = "on"
        response = self.client.post(reverse("recipe_edit", args=[recipe.pk]), data)
        self.assertRedirects(response, reverse("recipe_detail", args=[recipe.pk]))
        self.assertEqual(list(recipe.ingredients.all()), [self.onion])

    def test_users_cannot_edit_or_delete_someone_elses_recipe(self):
        recipe = self.make_recipe(user=self.other)
        for name in ("recipe_edit", "recipe_delete"):
            self.assertEqual(self.client.get(reverse(name, args=[recipe.pk])).status_code, 404)
            self.assertEqual(self.client.post(reverse(name, args=[recipe.pk])).status_code, 404)
        self.assertTrue(Recipe.objects.filter(pk=recipe.pk).exists())

    def test_delete_requires_confirmation(self):
        recipe = self.make_recipe()
        url = reverse("recipe_delete", args=[recipe.pk])
        self.assertContains(self.client.get(url), "Confirm delete")
        self.assertTrue(Recipe.objects.filter(pk=recipe.pk).exists())
        self.assertRedirects(self.client.post(url), reverse("my_recipes"))
        self.assertFalse(Recipe.objects.filter(pk=recipe.pk).exists())

    def test_rating_updates_average_and_preserves_comment(self):
        recipe = self.make_recipe()
        Review.objects.create(recipe=recipe, user=self.user, rating=2, comment="Good soup")
        Review.objects.create(recipe=recipe, user=self.other, rating=5)
        url = reverse("rate_recipe", args=[recipe.pk])
        self.assertRedirects(self.client.post(url, {"rating": "3"}), reverse("recipe_detail", args=[recipe.pk]))
        review = Review.objects.get(recipe=recipe, user=self.user)
        self.assertEqual((review.rating, review.comment), (3, "Good soup"))
        self.assertContains(self.client.get(reverse("recipe_detail", args=[recipe.pk])), "4.0 / 5")
        self.client.post(url, {"rating": "6"})
        review.refresh_from_db()
        self.assertEqual(review.rating, 3)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_rating_without_existing_review_allows_comment_later(self):
        recipe = self.make_recipe()
        self.client.post(reverse("rate_recipe", args=[recipe.pk]), {"rating": "4"})
        self.client.post(reverse("add_comment", args=[recipe.pk]), {"rating": "5", "comment": "Nice"})
        review = Review.objects.get(recipe=recipe, user=self.user)
        self.assertEqual((review.rating, review.comment), (4, "Nice"))

    def test_favorites_list_uses_existing_favorite_actions(self):
        recipe = self.make_recipe(user=self.other)
        self.client.post(reverse("favorite_recipe", args=[recipe.pk]))
        self.assertContains(self.client.get(reverse("favorite_recipes")), recipe.name)
        self.client.post(reverse("unfavorite_recipe", args=[recipe.pk]))
        self.assertNotContains(self.client.get(reverse("favorite_recipes")), recipe.name)

    def test_feature_pages_require_login(self):
        recipe = self.make_recipe()
        self.client.logout()
        for name, args in (
            ("recipe_create", []), ("my_recipes", []), ("favorite_recipes", []),
            ("recipe_edit", [recipe.pk]), ("recipe_delete", [recipe.pk]),
            ("rate_recipe", [recipe.pk]),
        ):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 302)

    def test_recipe_detail_keeps_batch_and_review_forms_separate(self):
        recipe = self.make_recipe()
        response = self.client.get(reverse("recipe_detail", args=[recipe.pk]), {"servings": 4})
        self.assertContains(response, "Ingredients for 4 servings")
        self.assertContains(response, 'name="servings"')
        self.assertContains(response, 'name="comment"')
        self.assertContains(response, "Save rating")

    def test_new_user_can_sign_up_and_reach_recipe_features(self):
        self.client.logout()
        response = self.client.post(reverse("signup"), {
            "username": "newcook",
            "email": "newcook@example.com",
            "password1": "SoupCooker-482!",
            "password2": "SoupCooker-482!",
        })
        self.assertRedirects(response, reverse("index"))
        self.assertContains(self.client.get(reverse("index")), "newcook")
        self.assertEqual(self.client.get(reverse("recipe_create")).status_code, 200)
        self.client.post(reverse("logout"))
        self.assertRedirects(
            self.client.get(reverse("favorite_recipes")),
            f'{reverse("login")}?next={reverse("favorite_recipes")}',
            fetch_redirect_response=False,
        )
        self.assertContains(self.client.get(reverse("login")), "Sign Up")
