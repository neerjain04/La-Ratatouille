from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import *

NUM_INGREDIENTS = 5
INGREDIENT_NAMES = [f"ingredient_{i}" for i in range(1, NUM_INGREDIENTS + 1)]
USERNAME = "emeril"

class SearchTests(TestCase):
    '''Test search page'''
    @classmethod
    def setUpTestData(cls):
        print("Setting up test data")
        # create a test user
        cls.user = User.objects.create_user(USERNAME)
        cls.user.save()

        # create ingredients
        cls.ingredients = [Ingredient(name=name) for name in INGREDIENT_NAMES]
        for ingredient in cls.ingredients:
            ingredient.save()

        # create recipes and add ingredients to them
        for i in range(1, NUM_INGREDIENTS + 1):
            ingredients_slice = cls.ingredients[:i]
            recipe = Recipe(name=f"recipe_{i}", calories_per_serving=100 * i,
                             num_servings=i, prep_time=10 * i, user=cls.user)
            recipe.save()
            # recipe_i has ingredients 1 through i
            for ingredient in ingredients_slice:
                RecipeIngredient(recipe=recipe, ingredient=ingredient, quantity = 1).save()
                    # def setUp(self):

    def setUp(self):
        # log in test user without password
        self.client.force_login(user=self.user)
        

    def test_search_by_ingredient(self):
        '''Test search by ingredient'''
        for i in range(1, NUM_INGREDIENTS + 1):
            for j , expected_count in zip(range(i + 1, NUM_INGREDIENTS + 2),
                                          range(NUM_INGREDIENTS + 1 - i, 0, -1)):
                response = self.client.get(
                    "/search/", query_params={"ingredients": [str(k) for k in range(i, j)]})
                
                self.assertEqual(len(response.context.get("recipes")), expected_count,
                                 f"expected {expected_count} recipes with ingredients {i} to {j - 1}")
                
    def test_search_count_missing_ingredient(self):
        '''Test count of missing ingredients'''
        user_ingredient_indices = (0, 2)
        for i in sorted(user_ingredient_indices):
            UserIngredient(user=self.user, ingredient=self.ingredients[i], quantity=1).save()
        response = self.client.get("/search/", query_params={"ingredients": 1})
        recipes = response.context.get("recipes")
        for r in recipes:
            missing = r.id
            for i in user_ingredient_indices:
                if r.id > i:
                    missing -= 1
            self.assertEqual(r.count_missing_ingredients, missing,
                             f"Expected {missing} missing ingredients for recipe {r.id}")
