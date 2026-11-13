"""
Train (or re-train) the recipe AI used by the Generate Recipe Using AI page.

    python manage.py train_recipe_ai --dataset ~/Downloads/food_recipes.csv
        Learns from the dataset and overwrites data/recipe_ai_model.json.

    python manage.py train_recipe_ai --dataset ~/Downloads/food_recipes.csv --min-recipes 5
        Learns rarer ingredients too (any used by 5+ recipes instead of 10+).

    python manage.py train_recipe_ai --dataset ~/Downloads/food_recipes.csv --include-site-recipes
        Also learns from the recipes saved on our site, including AI recipes people have edited.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from la_ratatouille_app.food_groups import read_dataset_recipes
from la_ratatouille_app.models import Recipe
from la_ratatouille_app.recipe_ai import MODEL_PATH, RecipeAI


class Command(BaseCommand):
    help = "Train the recipe AI on the food_recipes.csv dataset (and optionally our saved recipes)."

    def add_arguments(self, parser):
        parser.add_argument("--dataset", required=True, help="Path to food_recipes.csv")
        parser.add_argument("--min-recipes", type=int, default=10,
                            help="Learn ingredients used by at least this many recipes (default 10)")
        parser.add_argument("--include-site-recipes", action="store_true",
                            help="Also learn from the recipes saved in our database")
        parser.add_argument("--output", default=str(MODEL_PATH), help=f"Where to save the model (default {MODEL_PATH})")

    def handle(self, *args, **options):
        path = Path(options["dataset"]).expanduser()
        if not path.is_file():
            raise CommandError(f"No file at {path}")
        recipes = list(read_dataset_recipes(path))
        if options["include_site_recipes"]:
            for recipe in Recipe.objects.prefetch_related("ingredients"):
                recipes.append((recipe.name, [i.name for i in recipe.ingredients.all()],
                                recipe.instructions.splitlines(), recipe.prep_time))

        model = RecipeAI.train(recipes, min_recipes=options["min_recipes"])
        model.save(options["output"])
        self.stdout.write(self.style.SUCCESS(
            f"Trained on {model.data['trained_on']} recipes; learned {len(model.data['ingredients'])} ingredients. "
            f"Saved to {options['output']}"
        ))
