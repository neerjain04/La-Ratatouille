"""
Pantry logic for use cases 51-55, written against the team's models.

In our schema a user's pantry is simply their UserIngredient rows
(user.user_ingredients). There is no separate Pantry table.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from .models import Recipe, UserIngredient

TWO_PLACES = Decimal("0.01")


class PantryError(ValueError):
    """A pantry change that isn't allowed; the message is shown to the user."""


def get_pantry(user):
    """Every ingredient the user has on hand."""
    return UserIngredient.objects.filter(user=user).select_related("ingredient", "unit")


# ---------------------------------------------------------------- UC 54 Create Pantry
def create_pantry(user, starting_items=()):
    """
    Start a user's pantry, optionally with ingredients they already have.
    starting_items: list of (ingredient, unit, quantity). An empty pantry needs no rows.
    """
    for ingredient, unit, quantity in starting_items:
        set_pantry_item(user, ingredient, unit, quantity)
    return get_pantry(user)


# ---------------------------------------------------------------- UC 55 Delete Pantry
def delete_pantry(user):
    """Remove every ingredient from the user's pantry. Returns how many were removed."""
    deleted, _ = UserIngredient.objects.filter(user=user).delete()
    return deleted


# ---------------------------------------------------------------- UC 52 Edit Ingredient in Pantry
def set_pantry_item(user, ingredient, unit, quantity):
    """
    Add an ingredient or change its amount/unit. A quantity of 0 removes it.
    Returns the saved UserIngredient, or None if it was removed.
    """
    quantity = int(quantity)
    if quantity < 0:
        raise PantryError("Quantity can't be negative.")
    if quantity == 0:
        remove_pantry_item(user, ingredient)
        return None
    item, _ = UserIngredient.objects.update_or_create(
        user=user, ingredient=ingredient,
        defaults={"unit": unit, "quantity": quantity},
    )
    return item


def remove_pantry_item(user, ingredient):
    """Remove one ingredient. Returns True if something was removed."""
    deleted, _ = UserIngredient.objects.filter(user=user, ingredient=ingredient).delete()
    return deleted > 0


# ---------------------------------------------------------------- UC 51 Adjust Batch Size
@dataclass
class ScaledLine:
    ingredient: object
    unit: object
    original: int
    scaled: Decimal


def scale_recipe(recipe: Recipe, servings: int):
    """
    The recipe's ingredients scaled from recipe.num_servings to `servings`.
    Nothing is saved: the stored recipe never changes.
    """
    if servings < 1:
        raise ValueError("Servings must be at least 1.")
    factor = Decimal(servings) / Decimal(recipe.num_servings)
    lines = []
    for ri in recipe.recipe_ingredients.select_related("ingredient", "unit"):
        scaled = (Decimal(ri.quantity) * factor).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        lines.append(ScaledLine(ri.ingredient, ri.unit, ri.quantity, scaled))
    return factor, lines


# ---------------------------------------------------------------- UC 53 Determine Missing Ingredients
@dataclass
class MissingLine:
    ingredient: object
    unit: object
    needed: Decimal
    have: Decimal
    reason: str  # "not in pantry" | "not enough" | "different unit"

    @property
    def short_by(self):
        return max(self.needed - self.have, Decimal("0"))


def missing_ingredients(recipe: Recipe, user, servings: int | None = None):
    """Ingredients the user is missing or short on for this recipe (optionally scaled)."""
    _, lines = scale_recipe(recipe, servings or recipe.num_servings)
    have = {item.ingredient_id: item for item in get_pantry(user)}
    missing = []
    for line in lines:
        item = have.get(line.ingredient.id)
        line_unit_id = line.unit.id if line.unit else None
        if item is None:
            missing.append(MissingLine(line.ingredient, line.unit, line.scaled, Decimal("0"), "not in pantry"))
        elif item.unit_id != line_unit_id:
            # No unit conversion yet (cups vs grams): flag it instead of guessing.
            missing.append(MissingLine(line.ingredient, line.unit, line.scaled, Decimal(item.quantity), "different unit"))
        elif item.quantity < line.scaled:
            missing.append(MissingLine(line.ingredient, line.unit, line.scaled, Decimal(item.quantity), "not enough"))
    return missing
