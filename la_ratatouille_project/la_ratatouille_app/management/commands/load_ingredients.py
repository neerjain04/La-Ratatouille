"""
Put the dataset's ingredients (with food groups) and common units into the database.

    python manage.py load_ingredients
        Loads data/ingredients.csv: the 390 ingredients used by 10+ recipes in food_recipes.csv.

    python manage.py load_ingredients --dataset ~/Downloads/food_recipes.csv --min-recipes 5
        Rebuilds the list from the full dataset instead (rarer ingredients included).

Safe to run more than once: ingredients and units that already exist are left alone,
except that an ingredient still in the "Other" group is given its food group.
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from la_ratatouille_app.food_groups import count_dataset_ingredients, food_group_for
from la_ratatouille_app.models import Ingredient, Unit

BUNDLED_LIST = Path(__file__).resolve().parents[2] / "data" / "ingredients.csv"

# (name, abbreviation) for the pantry's unit menu. "each" is already in the team database.
UNITS = [
    ("each", "ea"), ("piece", "pc"), ("pinch", "pinch"),
    ("teaspoon", "tsp"), ("tablespoon", "tbsp"), ("cup", "cup"),
    ("milliliter", "ml"), ("liter", "L"), ("gram", "g"), ("kilogram", "kg"),
    ("ounce", "oz"), ("pound", "lb"),
]


class Command(BaseCommand):
    help = "Load ingredients from the food_recipes.csv dataset, grouped by food group, plus common units."

    def add_arguments(self, parser):
        parser.add_argument("--dataset", help="Path to food_recipes.csv. Default: the bundled data/ingredients.csv")
        parser.add_argument("--min-recipes", type=int, default=10,
                            help="Only ingredients used by at least this many dataset recipes (default 10)")

    def handle(self, *args, **options):
        if options["dataset"]:
            path = Path(options["dataset"]).expanduser()
            if not path.is_file():
                raise CommandError(f"No file at {path}")
            rows = count_dataset_ingredients(path)
        else:
            with open(BUNDLED_LIST, newline="", encoding="utf-8") as f:
                rows = [(r["name"], r["food_group"], int(r["recipe_count"])) for r in csv.DictReader(f)]
        rows = [row for row in rows if row[2] >= options["min_recipes"]]

        other = Ingredient.FoodGroup.OTHER
        by_name = {ingredient.name.lower(): ingredient for ingredient in Ingredient.objects.all()}
        created = regrouped = units_added = 0

        with transaction.atomic():
            for name, group, _ in rows:
                ingredient = by_name.get(name.lower())
                if ingredient is None:
                    by_name[name.lower()] = Ingredient.objects.create(name=name, food_group=group)
                    created += 1
                elif ingredient.food_group == other and group != other:
                    ingredient.food_group = group
                    ingredient.save(update_fields=["food_group"])
                    regrouped += 1

            # Ingredients that were added by hand (e.g. "egg", "bacon") get a group too.
            for ingredient in Ingredient.objects.filter(food_group=other):
                group = food_group_for(ingredient.name)
                if group != other:
                    ingredient.food_group = group
                    ingredient.save(update_fields=["food_group"])
                    regrouped += 1

            unit_names = {n.lower() for n in Unit.objects.values_list("name", flat=True)}
            unit_abbrs = {a.lower() for a in Unit.objects.values_list("abbr", flat=True)}
            for name, abbr in UNITS:
                if name.lower() not in unit_names and abbr.lower() not in unit_abbrs:
                    Unit.objects.create(name=name, abbr=abbr)
                    units_added += 1

        self.stdout.write(self.style.SUCCESS(
            f"Ingredients: {created} added, {regrouped} given a food group, "
            f"{Ingredient.objects.count()} in total. Units: {units_added} added."
        ))
