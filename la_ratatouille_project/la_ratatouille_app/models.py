from django.db import models


from django.conf import settings


class Review(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    recipe = models.ForeignKey(
        "Recipe",
        on_delete=models.CASCADE
    )
    date = models.DateTimeField(auto_now_add=True)
    rating = models.IntegerField(null=True, blank=True)
    comment = models.TextField()

    def __str__(self):
        return self.comment
