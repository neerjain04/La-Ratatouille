from django import forms
from django.forms import inlineformset_factory
from .models import Ingredient, Tag, Review, Unit, Recipe, RecipeIngredient
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

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

    items_per_page = forms.TypedChoiceField(
        label="Recipes per page",
        choices=((i, i) for i in (5, 10, 20, 50)),
        required=False,
        initial=10,
        coerce=int,
    )

    name = forms.CharField(
        label="Name",
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
    """add an ingredient or change its amount. Quantity 0 removes it."""
    ingredient = forms.ModelChoiceField(queryset=Ingredient.objects.all())
    quantity = forms.IntegerField(min_value=0)
    unit = forms.ModelChoiceField(queryset=Unit.objects.all(), required=False)


class BatchSizeForm(forms.Form):
    """how many servings to make."""
    servings = forms.IntegerField(min_value=1, max_value=500)

class SignUpForm(UserCreationForm):
    # Add an email field to the signup form
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    # Make sure an email is not already registered
    def clean_email(self):
        email = self.cleaned_data["email"]

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")

        return email
class RecipeForm(forms.ModelForm):
    """Validate the details a user supplies when adding or editing a recipe."""
    calories_per_serving = forms.IntegerField(min_value=0)
    num_servings = forms.IntegerField(min_value=1, label="Servings")
    prep_time = forms.IntegerField(min_value=0, label="Preparation time (minutes)")
    tags = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["tags"].initial = self.instance.tags.all()

    class Meta:
        model = Recipe
        fields = ["name", "instructions", "calories_per_serving", "num_servings", "prep_time"]


class RecipeIngredientForm(forms.ModelForm):
    quantity = forms.IntegerField(min_value=1)

    class Meta:
        model = RecipeIngredient
        fields = ["ingredient", "quantity", "unit"]


RecipeIngredientFormSet = inlineformset_factory(
    Recipe, RecipeIngredient, form=RecipeIngredientForm,
    extra=3, min_num=1, validate_min=True, can_delete=True,
)


class RatingForm(forms.Form):
    rating = forms.TypedChoiceField(
        choices=[(value, f"{value} star{'s' if value != 1 else ''}") for value in range(1, 6)],
        coerce=int,
        label="Your rating",
    )
