# La-Ratatouille
La Ratatouille is a cookbook and meal planning web application that helps users discover recipes and prepare meals using ingredients they already have available.

## Running locally

From `la_ratatouille_project`, apply migrations and start Django:

```shell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Sign in with the superuser, then use `/admin/` to add ingredients, units, and tags for recipes. Signed-in users can add, edit, and delete their own recipes, rate and favorite recipes, and view their saved favorites. Recipe ratings use a 1-5 star scale.
