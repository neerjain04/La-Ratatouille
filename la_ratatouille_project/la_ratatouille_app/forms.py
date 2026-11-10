from django import forms
from .models import Ingredient, Tag, Review, Unit
from django.core.validators import MinValueValidator, MaxValueValidator

# Search Form
class SearchForm(forms.Form):
    order_by = forms.ChoiceField(
        label="Sort by",
        choices=(("name", "Alphabetical (A->Z)"),
            ("-name", "Alphabetical (Z->A)"),
            ("ingredient_count", "Ingredient count (lowest first)"),
            ("prep_time", "Preparation Time (lowest first)"),
            ("rating", "Rating (lowest first)"),
            ("-rating", "Rating (highest first)"),),
        required=False,
    )

    ingredients = forms.ModelMultipleChoiceField(
        label="Ingredients",
        queryset=Ingredient.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    tags = forms.ModelMultipleChoiceField(
        label="Tag",
        queryset=Tag.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    min_rating = forms.FloatField(
        label="Minimum rating",
        required=False,
        validators=[MinValueValidator(limit_value=1), MaxValueValidator(limit_value=5)],
    )

    max_ingredient_count = forms.IntegerField(
        label="Maximum ingredient count",
        required=False,
        validators=[MinValueValidator(limit_value=1),],
    )

    max_prep_time = forms.IntegerField(
        label="Maximum preparation time",
        required=False,
        validators=[MinValueValidator(limit_value=1),],
    )

# Review Form
class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[
            (1, "1 Star"),
            (2, "2 Stars"),
            (3, "3 Stars"),
            (4, "4 Stars"),
            (5, "5 Stars")
        ],
        coerce=int,
        required=True
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {
            "comment": forms.Textarea(
                attrs={"placeholder": "Write your comment here..."}
            )
        }
        required=False

class PantryItemForm(forms.Form):
    """UC 52: add an ingredient or change its amount. Quantity 0 removes it."""
    ingredient = forms.ModelChoiceField(queryset=Ingredient.objects.all())
    quantity = forms.IntegerField(min_value=0)
    unit = forms.ModelChoiceField(queryset=Unit.objects.all(), required=False)


class BatchSizeForm(forms.Form):
    """UC 51: how many servings to make."""
    servings = forms.IntegerField(min_value=1, max_value=500)
