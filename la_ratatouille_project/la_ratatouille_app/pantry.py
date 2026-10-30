"""
Pantry (class diagram: Pantry) for use cases 52-55.

Our schema has no Pantry table: a user's pantry is their UserIngredient rows.
This class wraps the managers that already exist on User:
    user.user_ingredients   the UserIngredient rows (ingredient, unit, quantity)
    user.pantry             the Ingredient objects (Ingredient.users, related_name="pantry")
"""
from .models import UserIngredient


class Pantry:
    def __init__(self, user):
        self.user = user

    # ------------------------------------------------------------ reading
    def items(self):
        """Every UserIngredient row in this pantry."""
        return self.user.user_ingredients.select_related("ingredient", "unit")

    def ingredients(self):
        """Just the Ingredient objects, using the existing user.pantry manager."""
        return self.user.pantry.all()

    # ------------------------------------------------------------ UC 54 Create Pantry
    @classmethod
    def create(cls, user, starting_items=()):
        """Start a pantry. It is empty unless starting_items [(ingredient, unit, qty)] are given."""
        pantry = cls(user)
        for ingredient, unit, quantity in starting_items:
            pantry.add_ingredient(ingredient, quantity, unit)
        return pantry

    # ------------------------------------------------------------ UC 55 Delete Pantry
    def delete(self):
        """Remove every ingredient from the pantry. Returns how many were removed."""
        deleted, _ = self.user.user_ingredients.all().delete()
        return deleted

    # ------------------------------------------------------------ UC 52 Edit Ingredient in Pantry
    def add_ingredient(self, ingredient, quantity, unit=None):
        """Add an ingredient or change its amount. 0 removes it. (class diagram: addIngredient)"""
        quantity = int(quantity)
        if quantity < 0:
            raise ValueError("Quantity can't be negative.")
        if quantity == 0:
            self.remove_ingredient(ingredient)
            return None
        item, _ = UserIngredient.objects.update_or_create(
            user=self.user, ingredient=ingredient,
            defaults={"unit": unit, "quantity": quantity},
        )
        return item

    def remove_ingredient(self, ingredient):
        """Take one ingredient out. Returns True if it was there. (class diagram: removeIngredient)"""
        deleted, _ = self.user.user_ingredients.filter(ingredient=ingredient).delete()
        return deleted > 0

    # ------------------------------------------------------------ UC 53 (yes/no version)
    def check_recipe_ingredients(self, recipe, multiplier=1):
        """True if the pantry has everything the recipe needs. (class diagram: checkRecipeIngredients)"""
        return not recipe.get_missing_ingredients(self, multiplier)
