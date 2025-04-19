from django_filters.rest_framework import FilterSet, filters
from rest_framework.filters import SearchFilter

from .models import Recipe, Ingredient, Tag, Favorite, ShoppingCart

class IngredientSearchFilter(SearchFilter):
    """Custom search filter parameter name for ingredients."""
    search_param = 'name' # Use 'name' query parameter for searching ingredients

class RecipeFilter(FilterSet):
    """FilterSet for Recipes."""
    tags = filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',
        to_field_name='slug',
        queryset=Tag.objects.all(),
        label='Filter by tag slugs (e.g., ?tags=lunch&tags=breakfast)'
    )
    is_favorited = filters.BooleanFilter(
        method='filter_is_favorited',
        label='Filter by favorite status (e.g., ?is_favorited=true)'
    )
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart',
        label='Filter by shopping cart status (e.g., ?is_in_shopping_cart=true)'
    )
    # Author filtering is handled directly by name in Meta

    class Meta:
        model = Recipe
        # Fields that can be filtered directly by model field lookup
        fields = ('author',) # Allows filtering like ?author=1

    def _filter_user_recipe_list(self, queryset, name, value, related_model):
        """
        Helper method to filter recipes based on user's related lists
        (Favorites or ShoppingCart).
        """
        user = self.request.user
        if value and user.is_authenticated:
            # Filter recipes that exist in the related model for the current user
            return queryset.filter(pk__in=related_model.objects.filter(user=user).values_list('recipe_id'))
        # If value is False or user is not authenticated, return the original queryset
        # (We don't filter for "not favorited" or "not in cart" based on requirements)
        return queryset

    def filter_is_favorited(self, queryset, name, value):
        """Filter recipes based on whether they are in the user's favorites."""
        return self._filter_user_recipe_list(queryset, name, value, Favorite)

    def filter_is_in_shopping_cart(self, queryset, name, value):
        """Filter recipes based on whether they are in the user's shopping cart."""
        return self._filter_user_recipe_list(queryset, name, value, ShoppingCart)