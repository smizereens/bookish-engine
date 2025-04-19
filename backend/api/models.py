import base64

from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from django.core.validators import MinValueValidator, RegexValidator
from django.utils.translation import gettext_lazy as _
from django.db import models

# --- Custom Field for Base64 Images ---
class Base64ImageField(models.ImageField):
    """Custom ImageField to handle Base64 encoded images."""
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            # base64 encoded image - decode
            format, imgstr = data.split(';base64,') # format ~= data:image/X,
            ext = format.split('/')[-1] # guess file extension
            # Generate a unique name or use a default one
            name = f'image.{ext}'
            data = ContentFile(base64.b64decode(imgstr), name=name)
        return super().to_internal_value(data)

# --- Custom User Model ---
class User(AbstractUser):
    """Custom User Model."""
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    email = models.EmailField(
        'Email address',
        unique=True,
        max_length=254,
    )
    first_name = models.CharField(
        'First name',
        max_length=150,
    )
    last_name = models.CharField(
        'Last name',
        max_length=150,
    )
    avatar = Base64ImageField(
        _('avatar'),
        upload_to='avatars/',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ('id',)

    def __str__(self):
        return self.get_full_name() or self.username

# --- Core Recipe Models ---
class Tag(models.Model):
    """Tag for recipes (e.g., Breakfast, Lunch, Dinner)."""
    name = models.CharField(
        'Name',
        max_length=200,
        unique=True,
    )
    color = models.CharField(
        'Color HEX',
        max_length=7,
        unique=True,
        validators=[RegexValidator(
            regex=r'^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$',
            message='Enter a valid hex color code (e.g., #RRGGBB)'
        )]
    )
    slug = models.SlugField(
        'Slug',
        max_length=200,
        unique=True,
    )

    class Meta:
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'
        ordering = ('name',)

    def __str__(self):
        return self.name

class Ingredient(models.Model):
    """Ingredient used in recipes."""
    name = models.CharField(
        'Name',
        max_length=200,
    )
    measurement_unit = models.CharField(
        'Measurement Unit',
        max_length=200,
    )

    class Meta:
        verbose_name = 'Ingredient'
        verbose_name_plural = 'Ingredients'
        ordering = ('name',)
        constraints = [
            models.UniqueConstraint(fields=['name', 'measurement_unit'],
                                    name='unique_ingredient_unit')
        ]

    def __str__(self):
        return f'{self.name}, {self.measurement_unit}'

class Recipe(models.Model):
    """Recipe details."""
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recipes',
        verbose_name='Author',
    )
    name = models.CharField(
        'Name',
        max_length=200,
    )
    image = Base64ImageField( # Use the custom field here
        'Image',
        upload_to='recipes/images/',
    )
    text = models.TextField(
        'Description',
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        through='RecipeIngredient',
        related_name='recipes',
        verbose_name='Ingredients',
    )
    tags = models.ManyToManyField(
        Tag,
        related_name='recipes',
        verbose_name='Tags',
    )
    cooking_time = models.PositiveSmallIntegerField(
        'Cooking Time (min)',
        validators=[MinValueValidator(1, 'Must be at least 1 minute')]
    )
    pub_date = models.DateTimeField(
        'Publication Date',
        auto_now_add=True,
    )

    class Meta:
        verbose_name = 'Recipe'
        verbose_name_plural = 'Recipes'
        ordering = ('-pub_date',) # Default sort: newest first

    def __str__(self):
        return self.name

class RecipeIngredient(models.Model):
    """Intermediate model for Recipe-Ingredient relationship (stores amount)."""
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='recipeingredients', # Custom related_name for clarity
        verbose_name='Recipe',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE, # Or models.PROTECT if ingredients shouldn't be deleted if used
        related_name='recipeingredients', # Custom related_name for clarity
        verbose_name='Ingredient',
    )
    amount = models.PositiveSmallIntegerField(
        'Amount',
        validators=[MinValueValidator(1, 'Amount must be at least 1')]
    )

    class Meta:
        verbose_name = 'Recipe Ingredient'
        verbose_name_plural = 'Recipe Ingredients'
        constraints = [
            models.UniqueConstraint(fields=['recipe', 'ingredient'],
                                    name='unique_recipe_ingredient')
        ]

    def __str__(self):
        return f'{self.ingredient.name} ({self.amount} {self.ingredient.measurement_unit}) in "{self.recipe.name}"'


# --- User Interaction Models ---
class Follow(models.Model):
    """Model for User-to-User subscriptions."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='follower', # The one who follows
        verbose_name='Follower',
    )
    following = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='following', # The one being followed
        verbose_name='Following',
    )

    class Meta:
        verbose_name = 'Follow'
        verbose_name_plural = 'Follows'
        constraints = [
            models.UniqueConstraint(fields=['user', 'following'],
                                    name='unique_follow'),
            models.CheckConstraint(check=~models.Q(user=models.F('following')),
                                   name='prevent_self_follow')
        ]

    def __str__(self):
        return f'{self.user} follows {self.following}'

class Favorite(models.Model):
    """Model for User's favorite recipes."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='favorites',
        verbose_name='User',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='favorited_by',
        verbose_name='Recipe',
    )

    class Meta:
        verbose_name = 'Favorite'
        verbose_name_plural = 'Favorites'
        constraints = [
            models.UniqueConstraint(fields=['user', 'recipe'],
                                    name='unique_favorite')
        ]

    def __str__(self):
        return f'{self.user} favorites {self.recipe}'

class ShoppingCart(models.Model):
    """Model for User's shopping cart (recipes to buy ingredients for)."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shopping_cart',
        verbose_name='User',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='in_shopping_carts',
        verbose_name='Recipe',
    )

    class Meta:
        verbose_name = 'Shopping Cart Item'
        verbose_name_plural = 'Shopping Cart Items'
        constraints = [
            models.UniqueConstraint(fields=['user', 'recipe'],
                                    name='unique_shopping_cart_item')
        ]

    def __str__(self):
        return f'{self.recipe} in {self.user}\'s shopping cart'