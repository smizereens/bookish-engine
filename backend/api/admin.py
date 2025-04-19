from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (User, Tag, Ingredient, Recipe, RecipeIngredient,
                     Follow, Favorite, ShoppingCart)

# --- Inline Admins ---
class RecipeIngredientInline(admin.TabularInline):
    """Inline admin for RecipeIngredient within Recipe admin."""
    model = RecipeIngredient
    extra = 1 # Number of empty forms to display
    min_num = 1 # Minimum number of ingredients required
    autocomplete_fields = ('ingredient',) # Use autocomplete for ingredients

# --- Model Admins ---
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for the custom User model."""
    list_display = ('id', 'email', 'username', 'first_name',
                    'last_name', 'is_staff', 'avatar')
    search_fields = ('email', 'username')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    # Use default fieldsets from BaseUserAdmin, add custom fields if needed

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin configuration for the Tag model."""
    list_display = ('name', 'slug', 'color')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)} # Auto-populate slug from name

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    """Admin configuration for the Ingredient model."""
    list_display = ('name', 'measurement_unit')
    search_fields = ('name',)
    list_filter = ('measurement_unit',)

@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    """Admin configuration for the Recipe model."""
    list_display = ('name', 'author', 'get_favorite_count', 'pub_date')
    list_filter = ('author__username', 'name', 'tags__name') # Filter by author username, recipe name, tag name
    search_fields = ('name', 'author__username')
    readonly_fields = ('get_favorite_count', 'pub_date')
    inlines = [RecipeIngredientInline] # Add ingredients directly in recipe admin
    filter_horizontal = ('tags',) # Better UI for ManyToMany tags
    autocomplete_fields = ('author',) # Autocomplete for author selection

    @admin.display(description='Times Favorited')
    def get_favorite_count(self, obj):
        """Calculate and display the number of times a recipe is favorited."""
        return obj.favorited_by.count()

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    """Admin configuration for the Follow model."""
    list_display = ('id', 'user', 'following') # Added id for clarity
    search_fields = ('user__username', 'following__username')
    list_filter = ('user__username', 'following__username') # Filter by usernames
    autocomplete_fields = ('user', 'following') # Easier user selection

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """Admin configuration for the Favorite model."""
    list_display = ('id', 'user', 'recipe') # Added id for clarity
    search_fields = ('user__username', 'recipe__name')
    list_filter = ('user__username', 'recipe__name') # Filter by usernames and recipe names
    autocomplete_fields = ('user', 'recipe')

@admin.register(ShoppingCart)
class ShoppingCartAdmin(admin.ModelAdmin):
    """Admin configuration for the ShoppingCart model."""
    list_display = ('id', 'user', 'recipe') # Added id for clarity
    search_fields = ('user__username', 'recipe__name')
    list_filter = ('user__username', 'recipe__name') # Filter by usernames and recipe names
    autocomplete_fields = ('user', 'recipe')

# Note: RecipeIngredient is managed via inline in RecipeAdmin,
# but you could register it separately if needed for direct management.
# @admin.register(RecipeIngredient)
# class RecipeIngredientAdmin(admin.ModelAdmin):
#     list_display = ('recipe', 'ingredient', 'amount')
#     autocomplete_fields = ('recipe', 'ingredient')
#     list_filter = ('recipe__name', 'ingredient__name')
#     search_fields = ('recipe__name', 'ingredient__name')