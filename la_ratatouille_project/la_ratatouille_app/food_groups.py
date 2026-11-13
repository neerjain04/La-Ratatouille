"""
Food groups for the pantry page (Edit Ingredient in Pantry).

Our ingredient list comes from the food_recipes.csv dataset (8,000 recipes).
data/ingredients.csv is that list already cleaned up, with a food group and the
number of dataset recipes that use each ingredient. The load_ingredients
command puts it into the Ingredient table.

Each ingredient gets the food group of the first rule below whose pattern is
found in its name. Specific phrases come before general words, e.g.
"mustard oil" is an oil before "mustard seed" is a spice, and "cocoa powder"
is baking before "powder" is a spice.
"""
import csv
import re
from collections import Counter, defaultdict

# Codes match Ingredient.FoodGroup in models.py.
RULES = [
    ("condiment", r"ketchup|sauce|vinegar|vinaigrette|mayo|dijon|\bspread\b|nutella|peanut butter|tahini"
                  r"|pickle|achar|chutney|salsa|\bstock\b|broth|\bjam\b|gulkand|\bpaste\b|hummus|pesto"),
    ("beverage", r"coffee|\btea\b|soda water|aerated water|coconut water|\bwine\b|\bbeer\b|\brum\b|baileys"),
    ("oil_fat", r"\boil\b|shortening|\blard\b|margarine"),
    ("dairy", r"\bmilk\b|buttermilk|cream(?! of tartar)|cheese|\bcurd\b|yogh?urt|\bbutter\b|\bghee\b|paneer"
              r"|khoya|mawa|chenna|mascarpone|ricotta|feta|\bdahi\b"),
    ("baking", r"sugar|jaggery|\bhoney\b|syrup|baking|cooking soda|yeast|cocoa|chocolate|vanilla|custard"
               r"|gelatin|\bagar\b|sprinkles|\beno|fruit salt|silver foil|\bvark\b|ganache|icing|corn ?starch"
               r"|cream of tartar|marshmallow|caramel\b"),
    ("protein", r"\beggs?\b(?! noodles)|egg whites?|egg yolks?|chicken|mutton|\blamb\b|\bbeef\b|\bpork\b|bacon"
                r"|\bham\b|sausage|\bspam\b|\bturkey\b(?! berr)|\bfish\b|fillet|prawns?|shrimps?|\bcrab\b"
                r"|salmon|tuna|\bbasa\b|\bsquid\b|mussels?|keema|\bmeat\b|tofu|soy chunks|soya? granules"
                r"|tempeh|seitan"),
    ("nut_seed", r"groundnut powder|flax"),
    ("herb_spice", r"\bsalt\b|peppercorns?|pepper corns|pepper powder|white pepper|turmeric|haldi|chilli powder"
                   r"|chill?i flakes|dr(y|ied) red chill|dried chill|byadagi|kashmiri dry|cumin|jeera"
                   r"|coriander powder|coriander \(dhania\) seeds|coriander seeds|mustard seed|asafoetida|\bhing\b"
                   r"|cinnamon|dalchini|\bcloves?\b|laung|cardamom|elaichi|bay lea|tej patta|fennel|saunf"
                   r"|methi seed|fenugreek seed|methi powder|ajwain|carom|masala|oregano|saffron|paprika|amchur"
                   r"|mango powder|nutmeg|\bmace\b|javitri|star anise|nigella|kalonji|anardana|thyme|rosemary"
                   r"|herbs|seasoning|dry ginger|curry powder|rasam powder|sambar powder|cayenne|sichuan"
                   r"|stone flower|garlic powder|onion powder|\bpowder\b|\bspices?\b"),
    ("herb_spice", r"curry lea|coriander|dhania|\bmint\b|pudina|basil|parsley|\bdill\b|chives|lemon ?grass"
                   r"|kaffir lime|tulsi|rose petals|rose water|\bsage\b|tarragon|cilantro|methi lea|fenugreek lea"),
    ("legume", r"\bdal\b|\bdhal\b|lentil|chickpea|\bchana\b|rajma|kidney bean|black beans?|black eyed|lobia"
               r"|\bmoong\b|masoor|\burad\b|toor|arhar|horse gram|soybean|soya dal|^badi\b(?! hari)|wadi|lilva|avarekalu"
               r"|broad beans?|avarekai|pottukadalai|(?<!brussel )sprouts"),
    ("grain", r"\bflour\b|\batta\b|maida|\brice\b|basmati|\bpoha\b|semolina|sooji|\brava\b|\boats?\b|oatmeal"
              r"|muesli|quinoa|millet|barley|couscous|pasta|penne|spaghetti|fusilli|macaroni|noodles|vermicelli"
              r"|semiya|bread|\bbuns?\b|baguette|tortilla|taco|pita|biscuit|cracker|corn ?meal|sabudana"
              r"|tapioca|dalia|broken wheat|wheat bran|bajra|jowar|ragi|buckwheat|rajgira|\bpav\b|croutons"
              r"|\bsev\b|boondi|papad|cereal|corn ?flakes"),
    ("nut_seed", r"\bnuts?\b|cashew|almond|badam|pistachio|walnut|peanut|moongphali|groundnut|chironji"
                 r"|hazelnut|pecan|makhana|lotus seed|chia|flax|sunflower seed|pumpkin seed|melon seed|sesame"
                 r"|\btil\b|dry fruits?|poppy"),
    ("vegetable", r"banana stem|drumstick lea"),
    ("fruit", r"mango|banana|apple|lemon|\blime\b|orange|pineapple|strawberr|blueberr|cranberr|cherr(?!y tomato)"
              r"|raisin|sultana|\bdates?\b|\bfigs?\b|prunes|apricot|kiwi|papaya|watermelon|melon\b|pomegranate"
              r"|avocado|grape|peach|\bpears?\b|plum|guava|amla|gooseberr|kokum|tamarind|coconut|jackfruit"
              r"|fruits?\b|berr(y|ies)\b"),
    ("vegetable", r"onion|shallot|garlic|ginger|chill?i|jalapeno|tomato|potato|aloo|carrot|gajjar|capsicum"
                  r"|bell pepper|mushroom|spinach|palak|cauliflower|gobi|cabbage|cucumber|\bpeas\b|matar|beans"
                  r"|\bcorn\b|brinjal|eggplant|zucchini|pumpkin|kaddu|beetroot|broccoli|okra|bhindi|gourd|lauki"
                  r"|karela|radish|mooli|lettuce|olives?|\byam\b|colocasia|arbi|drumstick|celery|leek|tindora"
                  r"|parval|bok choy|turnip|arugula|amaranth|greens|vegetables?|lotus stem|sundakkai"
                  r"|turkey berr|kale|asparagus"),
]
_COMPILED = [(group, re.compile(pattern)) for group, pattern in RULES]

# Dataset entries that aren't pantry ingredients, or that are a brand of something
# already on the list. Matched on the cleaned, lowercased name.
SKIP = {
    "water", "lukewarm water", "chilled water", "hot water", "cold water", "warm water",
    "ice cubes", "ice", "coal", "salt and pepper", "nutralite classic spread",
    "nutralite garlic & oregano spread", "banana leaf",
}
RENAME = {
    "vivatta maida": "All Purpose Flour (Maida)",
    "britannia cream cheese": "Cream Cheese",
    "britannia cheese block": "Cheese Block",
    "gingelly oil": "Sesame (Gingelly) Oil",
    "brown cardamom (badi elaichi)": "Black cardamom (Badi Elaichi)",
    "enos fruit salt": "Eno fruit salt",
}


def food_group_for(name):
    """The food group code for an ingredient name ("other" if no rule matches)."""
    lowered = name.lower().strip()
    for group, pattern in _COMPILED:
        if pattern.search(lowered):
            return group
    return "other"


def clean_name(name):
    """Tidy one dataset name, or return "" if it should be skipped."""
    name = re.sub(r"\s+", " ", name).strip(" ,.-")
    name = re.sub(r"\(\s*", "(", name)
    name = re.sub(r"\s*\)", ")", name)
    if not name.isascii() or not re.search(r"[A-Za-z]", name) or len(name) > 50:
        return ""          # the dataset also has every recipe in Hindi; we keep the English ones
    if name.lower() in SKIP:
        return ""
    return RENAME.get(name.lower(), name)


def _singular(word):
    if len(word) <= 3:
        return word
    if word == "leaves":
        return "leaf"
    if word.endswith("llies"):
        return word[:-2]                   # chillies -> chilli
    if word.endswith("ies"):
        return word[:-3] + "y"             # cherries -> cherry
    if word.endswith("oes") or re.search(r"(ss|x|ch|sh)es$", word):
        return word[:-2]                   # tomatoes -> tomato
    if word.endswith("s") and not word.endswith(("ss", "us")):
        return word[:-1]
    return word


def name_key(name):
    """
    Names that mean the same ingredient get the same key, e.g. "Onion" and "Onions",
    "Mustard seeds" and "Mustard seeds (Rai/ Kadugu)", "Lemongrass" and "Lemon Grass".
    """
    outside_brackets = re.sub(r"\([^)]*\)", " ", name.lower())
    words = [w for w in re.findall(r"[a-z]+", outside_brackets) if w not in ("and", "or")]
    return "".join(_singular(w) for w in words)


def read_dataset_recipes(path):
    """
    Yield (title, [ingredient names], [steps], minutes) for every row of food_recipes.csv.
    minutes is prep time + cook time, or None when the row has neither.
    """
    csv.field_size_limit(10 ** 8)
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            times = f"{row.get('prep_time') or ''} {row.get('cook_time') or ''}"
            minutes = sum(int(n) for n in re.findall(r"\d+", times))
            yield (
                (row.get("recipe_title") or "").strip(),
                [name for name in (row.get("ingredients") or "").split("|") if name.strip()],
                [step.strip() for step in (row.get("instructions") or "").split("|") if step.strip()],
                minutes or None,
            )


def count_dataset_ingredients(path):
    """
    Read food_recipes.csv and return [(name, food_group, recipe_count)], most used first.
    Spelling variants are merged and the most common spelling is kept.
    """
    spellings = defaultdict(Counter)
    for _, names, _, _ in read_dataset_recipes(path):
        for raw in names:
            name = clean_name(raw)
            key = name_key(name) if name else ""
            if key:
                spellings[key][name] += 1
    rows = []
    for variants in spellings.values():
        name = variants.most_common(1)[0][0]
        rows.append((name, food_group_for(name), sum(variants.values())))
    rows.sort(key=lambda row: (-row[2], row[0].lower()))
    return rows
