from django import forms
from django.forms import inlineformset_factory

from .models import Ingredient, Recipe, RecipeIngredient, Tag


# Only show ingredients that already exist in the recipe database.
class SearchForm(forms.Form):
    ingredients = forms.ModelMultipleChoiceField(
        label="Ingredients",
        queryset=Ingredient.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )


# Collect recipe details and optional tags from the user.
class RecipeForm(forms.ModelForm):
    calories_per_serving = forms.IntegerField(min_value=0)
    num_servings = forms.IntegerField(min_value=1)
    prep_time = forms.IntegerField(min_value=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tags"] = forms.ModelMultipleChoiceField(
            queryset=Tag.objects.all(),
            required=False,
        )
        if self.instance.pk:
            self.fields["tags"].initial = self.instance.tags.all()

    class Meta:
        model = Recipe
        fields = [
            "name",
            "instructions",
            "calories_per_serving",
            "num_servings",
            "prep_time",
            "photo",
        ]
        widgets = {
            "instructions": forms.Textarea(attrs={"rows": 5}),
        }


# Each form in this set represents one recipe ingredient and its amount.
class RecipeIngredientForm(forms.ModelForm):
    quantity = forms.IntegerField(min_value=1, label="Quantity")

    class Meta:
        model = RecipeIngredient
        fields = ["ingredient", "quantity", "unit"]


RecipeIngredientFormSet = inlineformset_factory(
    Recipe,
    RecipeIngredient,
    form=RecipeIngredientForm,
    fields=["ingredient", "quantity", "unit"],
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


# Keep ratings within the supported one-to-five star range.
class RatingForm(forms.Form):
    rating = forms.TypedChoiceField(
        choices=[
            (value, f"{value} star{'s' if value != 1 else ''}")
            for value in range(1, 6)
        ],
        coerce=int,
        label="Your rating",
    )