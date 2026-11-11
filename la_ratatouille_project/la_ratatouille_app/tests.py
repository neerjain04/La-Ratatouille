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


# Tests for Aiden's use cases (3.1.14, 3.1.18, 3.1.25, 3.1.26, 3.1.27) are in test_use_cases.py
