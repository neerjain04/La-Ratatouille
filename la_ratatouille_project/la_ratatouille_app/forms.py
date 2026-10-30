
from django import forms
from .models import Ingredient, Review


# Search Form
class SearchForm(forms.Form):
    ingredients = forms.MultipleChoiceField(
        label="Ingredients",
        choices=((i.id, i.name) for i in Ingredient.objects.all()),
        widget=forms.CheckboxSelectMultiple,
        required=False,
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
