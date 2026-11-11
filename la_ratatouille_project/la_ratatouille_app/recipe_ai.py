"""
A very simple recipe AI for 3.1.29 Generate Recipe Using AI and 3.1.30 Save Recipe Created by AI.

It is a statistical model, not a large language model. Training reads recipes
(the food_recipes.csv dataset, and optionally recipes saved on our site) and learns:

    which ingredients are used together ........ picks ingredients that go with your pantry
    where each ingredient shows up in the steps . puts the steps in a sensible order
    a few real sentences that use each one ...... writes the instructions
    which dish names go with which ingredients .. names the recipe ("Spinach & Paneer Curry")
    how long those dishes take .................. fills in prep time

Refine it by training on more data:
    python manage.py train_recipe_ai --dataset ~/Downloads/food_recipes.csv --min-recipes 5
    python manage.py train_recipe_ai --dataset ~/Downloads/food_recipes.csv --include-site-recipes

The trained model is plain JSON (data/recipe_ai_model.json), so it can be opened and read.
"""
import json
import random
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from statistics import median

from django.db import transaction

from .food_groups import _singular, clean_name, food_group_for, name_key
from .models import Ingredient, Recipe, RecipeIngredient, Unit

MODEL_PATH = Path(__file__).resolve().parent / "data" / "recipe_ai_model.json"
DRAFT_SESSION_KEY = "ai_recipe_draft"

# Starting amounts by food group for a 4-serving recipe: (quantity, unit name, rough calories).
# The user can change them after saving. Unit names match the load_ingredients command.
DEFAULT_AMOUNTS = {
    "protein": (500, "gram", 800), "legume": (1, "cup", 650), "dairy": (1, "cup", 150),
    "vegetable": (1, "cup", 30), "fruit": (1, "each", 80), "grain": (1, "cup", 600),
    "nut_seed": (2, "tablespoon", 100), "herb_spice": (1, "teaspoon", 5), "oil_fat": (2, "tablespoon", 240),
    "condiment": (1, "tablespoon", 30), "baking": (1, "tablespoon", 50), "beverage": (1, "cup", 50),
    "other": (1, "each", 0),
}
STAPLE_GROUPS = {"herb_spice", "oil_fat", "condiment", "baking", "beverage"}   # never the "main" ingredient
# Ingredients whose food-group amount would be silly (1 cup of garlic, 500 g of eggs).
AMOUNT_OVERRIDES = [
    ("vegetable", re.compile(r"garlic|ginger|chill?i|jalapeno"), (1, "tablespoon", 5)),
    ("protein", re.compile(r"\beggs?\b"), (3, "each", 210)),
]

# Words that don't identify an ingredient in the instructions ("Fresh", "powder", ...).
_VAGUE_WORDS = {
    "fresh", "whole", "dry", "dried", "red", "green", "yellow", "black", "white", "powder", "seed", "split",
    "raw", "ripe", "small", "large", "baby", "sweet", "extra", "virgin", "taste", "mixed", "cooked", "leaf",
    "boneless", "roasted", "chopped", "instant", "all", "purpose", "the", "and", "with", "for",
}
# Last word of a dataset title that isn't a kind of dish ("... Chicken Recipe").
_NOT_DISHES = {"chicken", "cheese", "cream", "vegetable", "vegetables", "home", "cooker", "flour", "fruits",
               "style", "way", "mix", "recipe", "recipes", "special", "version", "the", "and", "with"}
_STEP_VERBS = {
    "add", "heat", "stir", "cook", "mix", "saute", "place", "pour", "grind", "boil", "cut", "chop", "roast",
    "fry", "bake", "combine", "toss", "sprinkle", "garnish", "blend", "whisk", "season", "transfer", "soak",
    "knead", "marinate", "simmer", "steam", "drizzle", "spread", "squeeze", "dice", "slice", "peel", "wash",
    "grate", "toast", "melt", "bring", "allow", "keep", "remove", "dry",
}
_DEVANAGARI = re.compile("[ऀ-ॿ]")


def _keywords(name):
    """Words that show an ingredient is mentioned in a step: "Cumin seeds (Jeera)" -> ["cumin"]."""
    words = [_singular(w) for w in re.findall(r"[a-z]+", re.sub(r"\([^)]*\)", " ", name.lower()))]
    useful = [w for w in words if len(w) > 2 and w not in _VAGUE_WORDS]
    return useful or words[:1]


class RecipeAI:
    """The trained model. `data` is the dict saved to JSON."""

    def __init__(self, data):
        self.data = data

    # ------------------------------------------------------------------ training
    @classmethod
    def train(cls, recipes, min_recipes=10, max_pairs=25, max_sentences=6):
        """
        recipes: (title, [ingredient names], [steps], minutes) tuples, e.g. from
        food_groups.read_dataset_recipes(). Recipes not written in English are skipped.
        """
        spellings = defaultdict(Counter)
        used_in = Counter()
        together = defaultdict(Counter)
        dishes_for = defaultdict(Counter)
        dish_minutes = defaultdict(list)
        positions = defaultdict(list)
        sentences_for = defaultdict(Counter)
        all_sentences = Counter()
        sizes = []
        trained_on = 0

        for title, names, steps, minutes in recipes:
            if _DEVANAGARI.search(title + " ".join(names) + " ".join(steps)):
                continue
            keys = {}
            for raw in names:
                name = clean_name(raw)
                key = name_key(name) if name else ""
                if key:
                    spellings[key][name] += 1
                    keys[key] = _keywords(name)
            if not keys:
                continue
            trained_on += 1
            sizes.append(len(keys))
            for key in keys:
                used_in[key] += 1
            for a, b in combinations(sorted(keys), 2):
                together[a][b] += 1
                together[b][a] += 1

            title_words = re.sub(r"\s*recipe.*$", "", title.lower()).split()
            dish = title_words[-1] if title_words else ""
            if dish.isalpha() and len(dish) > 2 and dish not in _NOT_DISHES:
                dish = _singular(dish)
                for key in keys:
                    dishes_for[key][dish] += 1
                if minutes:
                    dish_minutes[dish].append(minutes)

            placed = set()
            for index, step in enumerate(steps):
                place = index / max(len(steps) - 1, 1)
                for sentence in re.split(r"(?<=[.!])\s+", step):
                    sentence = sentence.strip()
                    lowered = sentence.lower()
                    # skip titles, and sentences the dataset cut short ("Heat oil in a")
                    if (not 20 <= len(sentence) <= 140 or "recipe" in lowered or "  " in sentence
                            or not sentence.endswith((".", "!"))):
                        continue
                    all_sentences[sentence] += 1
                    first_word = re.match(r"[a-z]+", lowered)
                    for key, words in keys.items():
                        if any(word in lowered for word in words):
                            if key not in placed:      # where it is first mentioned
                                positions[key].append(place)
                                placed.add(key)
                            if first_word and first_word.group() in _STEP_VERBS:
                                sentences_for[key][sentence] += 1

        kept = {key for key, count in used_in.items() if count >= min_recipes}
        ingredients = {}
        for key in kept:
            name = spellings[key].most_common(1)[0][0]
            # Prefer short sentences that mention few other ingredients.
            ranked = sorted(sentences_for[key].items(), key=lambda item: (-item[1], abs(len(item[0]) - 70)))
            ingredients[key] = {
                "name": name,
                "food_group": food_group_for(name),
                "recipes": used_in[key],
                "position": round(sum(positions[key]) / len(positions[key]), 3) if positions[key] else 0.5,
                "goes_with": dict([(o, n) for o, n in together[key].most_common() if o in kept][:max_pairs]),
                "dishes": dict(dishes_for[key].most_common(5)),
                "sentences": [sentence for sentence, _ in ranked[:max_sentences]],
            }
        dish_counts = Counter({dish: len(times) for dish, times in dish_minutes.items()})
        return cls({
            "trained_on": trained_on,
            "min_recipes": min_recipes,
            "median_size": int(median(sizes)) if sizes else 8,
            "median_minutes": int(median(m for times in dish_minutes.values() for m in times)) if dish_minutes else 30,
            "dish_minutes": {dish: int(median(dish_minutes[dish])) for dish, _ in dish_counts.most_common(60)},
            "closing": [s for s, n in all_sentences.most_common(200)
                        if n >= 2 and any(w in s.lower() for w in ("taste", "serve", "adjust", "garnish"))][:5],
            "ingredients": ingredients,
        })

    # ------------------------------------------------------------------ saving and loading
    def save(self, path=MODEL_PATH):
        Path(path).write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding="utf-8")

    @classmethod
    def from_file(cls, path=MODEL_PATH):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    # ------------------------------------------------------------------ 3.1.29 Generate Recipe Using AI
    def generate(self, pantry=(), must_include=(), servings=4, size=None, seed=None):
        """
        Make a recipe draft (a plain dict, nothing is saved).
            pantry        ingredient names the user has; the model prefers these
            must_include  ingredient names that have to be in the recipe
        Names the model hasn't learned are ignored.
        """
        rng = random.Random(seed)
        known = self.data["ingredients"]
        pantry_keys = {name_key(n) for n in pantry} & known.keys()
        chosen = [key for key in dict.fromkeys(name_key(n) for n in must_include) if key in known]
        size = max(3, min(size or self.data["median_size"], 15))

        if not chosen:   # start from a main ingredient: one from the pantry if possible
            mains = [k for k in (pantry_keys or known) if known[k]["food_group"] not in STAPLE_GROUPS] or list(known)
            chosen.append(rng.choices(mains, weights=[known[k]["recipes"] for k in mains])[0])

        while len(chosen) < size:
            # How often two ingredients appear together, relative to how common each is
            # (so salt, which is in everything, doesn't outscore real matches). The first
            # ingredient counts double so the recipe stays about it.
            scores = Counter()
            for weight, key in zip([2] + [1] * len(chosen), chosen):
                for other, together in known[key]["goes_with"].items():
                    if other not in chosen:
                        scores[other] += weight * together / (known[key]["recipes"] * known[other]["recipes"]) ** 0.5
            if not scores:
                break
            for key in scores.keys() & pantry_keys:
                scores[key] *= 1.5
            top = scores.most_common(5)
            chosen.append(rng.choices([k for k, _ in top], weights=[s for _, s in top])[0])

        mains = [k for k in chosen if known[k]["food_group"] not in STAPLE_GROUPS][:2] or chosen[:1]
        dish_scores = Counter()
        for key in mains:
            dish_scores.update({d: n for d, n in known[key]["dishes"].items() if d in self.data["dish_minutes"]})
        dish = dish_scores.most_common(1)[0][0] if dish_scores else "bowl"
        short = [re.sub(r"\s*\(.*?\)", "", known[k]["name"]).strip().title() for k in mains]
        name = f"{' & '.join(short)} {dish.title()}"
        if len(name) > 50:
            name = f"{short[0]} {dish.title()}"[:50]

        ordered = sorted(chosen, key=lambda k: known[k]["position"])
        ours = {word for k in chosen for word in _keywords(known[k]["name"])}
        others = {word for k, info in known.items() if k not in chosen for word in _keywords(info["name"])} - ours
        steps = ["Wash, chop and measure all the ingredients."]
        for key in ordered:
            options = [s for s in known[key]["sentences"] if s not in steps]
            if options and len(steps) < 10:
                # prefer sentences that don't mention ingredients this recipe doesn't have
                fewest = min(sum(w in s.lower() for w in others) for s in options)
                steps.append(rng.choice([s for s in options if sum(w in s.lower() for w in others) == fewest]))
        if self.data["closing"]:
            steps.append(self.data["closing"][0])

        lines, calories = [], 0
        for key in ordered:
            group = known[key]["food_group"]
            quantity, unit, kcal = DEFAULT_AMOUNTS.get(group, DEFAULT_AMOUNTS["other"])
            for override_group, pattern, amount in AMOUNT_OVERRIDES:
                if group == override_group and pattern.search(known[key]["name"].lower()):
                    quantity, unit, kcal = amount
                    break
            lines.append({"name": known[key]["name"], "food_group": group, "unit": unit,
                          "quantity": max(1, round(quantity * servings / 4))})
            calories += kcal * servings / 4

        return {
            "name": name,
            "instructions": "\n".join(f"{n}. {step}" for n, step in enumerate(steps, start=1)),
            "num_servings": servings,
            "prep_time": self.data["dish_minutes"].get(dish, self.data["median_minutes"]),
            "calories_per_serving": int(calories / servings),
            "ingredients": lines,
            "from_pantry": [known[k]["name"] for k in chosen if k in pantry_keys],
            "not_learned": [n for n in must_include if name_key(n) not in known],
        }


# ---------------------------------------------------------------------- 3.1.30 Save Recipe Created by AI
def save_draft(draft, user):
    """Save a generate() draft as one of the user's recipes (marked ai_generated). Returns the Recipe."""
    with transaction.atomic():
        recipe = Recipe.objects.create(
            name=draft["name"][:50], instructions=draft["instructions"], user=user, ai_generated=True,
            num_servings=draft["num_servings"], prep_time=draft["prep_time"],
            calories_per_serving=draft["calories_per_serving"],
        )
        for line in draft["ingredients"]:
            ingredient = Ingredient.objects.filter(name__iexact=line["name"]).first()
            if ingredient is None:
                group = line["food_group"] if line["food_group"] in Ingredient.FoodGroup.values else "other"
                ingredient = Ingredient.objects.create(name=line["name"][:50], food_group=group)
            RecipeIngredient.objects.get_or_create(
                recipe=recipe, ingredient=ingredient,
                defaults={"unit": Unit.objects.filter(name=line["unit"]).first(), "quantity": line["quantity"]},
            )
    return recipe
