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

        # create test users
        cls.user = User.objects.create_user("Emeril")
        cls.user.save()
        quina = User.objects.create_user("Quina")
        quina.save()

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
            # recipe_i has ingredients 0 through i - 1
            for ingredient in ingredients_slice:
                RecipeIngredient(recipe=recipe, ingredient=ingredient, quantity = 1).save()

        # add tags to recipes
        cls.dessert_tag = Tag(name="dessert")
        cls.dessert_tag.save()
        cls.low_carb_tag = Tag(name="low carb")
        cls.low_carb_tag.save()
        cls.unused_tag = Tag(name="unused")
        cls.unused_tag.save()
        RecipeTag(recipe=cls.recipes[0], tag=cls.dessert_tag).save()
        RecipeTag(recipe=cls.recipes[1], tag=cls.dessert_tag).save()
        RecipeTag(recipe=cls.recipes[1], tag=cls.low_carb_tag).save()
        RecipeTag(recipe=cls.recipes[2], tag=cls.low_carb_tag).save()

        # add ingredients to user pantry
        UserIngredient(user=cls.user, ingredient=cls.ingredients[0], quantity=1).save()
        UserIngredient(user=cls.user, ingredient=cls.ingredients[2], quantity=1).save()

        # add reviews to recipes
        Review(user=cls.user, recipe=cls.recipes[0], rating=4).save()
        Review(user=quina, recipe=cls.recipes[0], rating=3).save()
        Review(user=quina, recipe=cls.recipes[1], rating=2).save()
        Review(user=cls.user, recipe=cls.recipes[2], rating=4).save()


    def setUp(self):
        # log in test user without password
        self.client.force_login(user=self.user)

################################################################################
# Tests for search by ingredient
################################################################################
    def test_search_by_ingredient(self):
        '''Test search by ingredient'''
        response = self.client.get("/search/", query_params={"ingredients": [2]})
        self.assertEqual(len(response.context.get("recipe_page")), 3, f"expected 3 recipes with ingredient 2")
        response = self.client.get("/search/", query_params={"ingredients": [4]})
        self.assertEqual(len(response.context.get("recipe_page")), 1, f"expected 1 recipes with ingredient 4")
        response = self.client.get("/search/", query_params={"ingredients": [5]})
        self.assertEqual(len(response.context.get("recipe_page")), 0, f"expected 1 recipes with ingredient 5")
                
    def test_search_count_missing_ingredient(self):
        '''Test count of missing ingredients'''
        response = self.client.get("/search/", query_params={"ingredients": 1})
        recipes = response.context.get("recipe_page")
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
        self.assertEqual(len(response.context.get("recipe_page")), 2, "Expect 2 vegan recipes")
        UserTag(user=self.user, tag=gluten_free_tag).save()
        self.assertEqual(len(response.context.get("recipe_page")), 2,
                         "Expect 1 recipe that is both vegan and gluten free")

################################################################################
# Tests for search by prep_time
################################################################################
    def test_search_by_prep_time_expect_none(self):
        '''Test filtering by prep time'''
        response = self.client.get("/search/", query_params={"max_prep_time": 1})
        self.assertEqual(len(response.context.get("recipe_page")), 0,
                                 "Expect 0 recipes with max prep time 1")
    def test_search_by_prep_time_expect_one(self):
        response = self.client.get("/search/", query_params={"max_prep_time": 10})
        self.assertEqual(len(response.context.get("recipe_page")), 1,
                                         "Expect 1 recipes with max prep time 10")
    def test_search_by_prep_time_expect_multiple(self):
        response = self.client.get("/search/", query_params={"max_prep_time": 39})
        self.assertEqual(len(response.context.get("recipe_page")), 3,
                                         "Expect 3 recipes with max prep time 39")
        
################################################################################
# Tests for search by rating
################################################################################
    def test_search_by_rating_expect_none(self):
        response = response = self.client.get("/search/", query_params={"min_rating": 5})
        self.assertEqual(len(response.context.get("recipe_page")), 0,
                                         "Expect 0 recipes with min rating 5")

    def test_search_by_rating_expect_one(self):
            response = response = self.client.get("/search/", query_params={"min_rating": 4})
            self.assertEqual(len(response.context.get("recipe_page")), 1,
                                             "Expect 1 recipes with min rating 4")

    def test_search_by_rating_expect_multiple(self):
                response = response = self.client.get("/search/", query_params={"min_rating": 2})
                self.assertEqual(len(response.context.get("recipe_page")), 3,
                                                 "Expect 3 recipes with min rating 2")
                
################################################################################
# Tests for filter by tag
################################################################################
    def test_search_by_tag_expect_none(self):
        response = self.client.get("/search/", query_params={"tags": self.unused_tag.id})
        self.assertEqual(len(response.context.get("recipe_page")), 0, "Expect 0 recipes with unused tag")

    def test_search_by_multiple_tag(self):
        response = self.client.get("/search/", query_params={"tags": [self.low_carb_tag.id, self.dessert_tag.id]})
        self.assertEqual(len(response.context.get("recipe_page")), 1, "Expect 1 recipe with dessert and low carb tags")

################################################################################
# Tests for search by ingredient count
################################################################################
    def test_search_by_ingredient_count_expect_none(self):
        RecipeIngredient(recipe=self.recipes[0], ingredient=self.ingredients[4], quantity=1).save()
        response = self.client.get("/search/", query_params={"max_ingredient_count": 1})
        self.assertEqual(len(response.context.get("recipe_page")), 0, "Expect 0 recipes with 1 ingredient")

    def test_search_by_ingredient_count_expect_multiple(self):
        response = self.client.get("/search/", query_params={"max_ingredient_count": 3})
        self.assertEqual(len(response.context.get("recipe_page")), 3, "Expect 3 recipes with 3 or fewer ingredients")


################################################################################
# Tests for sort by rating
################################################################################
    def test_sort_by_rating_first_pair(self):
        response = self.client.get("/search/", query_params={"min_rating": 1, "order_by": "-rating"})
        results = response.context.get("recipe_page")
        self.assertGreaterEqual(results[0].rating, results[1].rating, "Expect 1st result rating >= 2nd result rating")

    def test_sort_by_rating_second_pair(self):
        response = self.client.get("/search/", query_params={"min_rating": 1, "order_by": "-rating"})
        results = response.context.get("recipe_page")
        self.assertGreaterEqual(results[1].rating, results[2].rating, "Expect 2rd result rating >= 3rd result rating")

################################################################################
# Tests for sort by ingredient count
################################################################################
    def test_sort_by_ingr_count_first_pair(self):
        response = self.client.get("/search/", query_params={"order_by": "ingredient_count"})
        results = response.context.get("recipe_page")
        self.assertLessEqual(results[0].ingredient_count, results[1].ingredient_count, "Expect 1st ingr. count <= 2nd ingr. count")

    def test_sort_by_ingr_count_second_pair(self):
        response = self.client.get("/search/", query_params={"order_by": "ingredient_count"})
        results = response.context.get("recipe_page")
        self.assertLessEqual(results[1].ingredient_count, results[2].ingredient_count, "Expect 2nd ingr. count <= 3rd ingr. count")

################################################################################
# Tests for sort by preparation time
################################################################################
    def test_sort_by_prep_time_first_pair(self):
        response = self.client.get("/search/", query_params={"order_by": "prep_time"})
        results = response.context.get("recipe_page")
        self.assertLessEqual(results[0].prep_time, results[1].prep_time, "Expect 1st prep time <= 2nd prep time")

    def test_sort_by_prep_time_second_pair(self):
        response = self.client.get("/search/", query_params={"order_by": "prep_time"})
        results = response.context.get("recipe_page")
        self.assertLessEqual(results[1].prep_time, results[2].prep_time, "Expect 2nd prep time <= 3rd prep time")

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
