from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from djoser.views import UserViewSet as DjoserUserViewSet
from rest_framework import viewsets, status, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from .models import (User, Tag, Ingredient, Recipe, Follow, Favorite,
                     ShoppingCart, RecipeIngredient)
from .serializers import (TagSerializer, IngredientSerializer,
                          RecipeReadSerializer, RecipeWriteSerializer,
                          FollowSerializer, RecipeMinifiedSerializer,
                          CustomUserSerializer) # Import CustomUserSerializer
from .permissions import IsOwnerOrReadOnly # Import custom permissions
from .filters import RecipeFilter, IngredientSearchFilter
from .pagination import CustomPageNumberPagination


class CustomUserViewSet(DjoserUserViewSet):
    """
    Custom UserViewSet extending Djoser's.
    Handles /users/, /users/me/, /users/{id}/, /users/subscriptions/, /users/{id}/subscribe/
    Uses CustomUserSerializer for representation.
    """
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer # Use our custom serializer for user representation
    pagination_class = CustomPageNumberPagination
    # Permissions are handled by Djoser for most actions (e.g., AllowAny for list/retrieve, IsAuthenticated for me)
    # We add specific permissions for custom actions.

    @action(detail=False, methods=['get'],
            permission_classes=[permissions.IsAuthenticated])
    def subscriptions(self, request):
        """
        List users the current authenticated user is subscribed to.
        Returns paginated list of users using FollowSerializer.
        """
        user = request.user
        # Get User objects the current user is following
        followed_users = User.objects.filter(following__user=user)
        page = self.paginate_queryset(followed_users)
        # Use FollowSerializer to represent the followed users, including their recipes
        serializer = FollowSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[permissions.IsAuthenticated])
    def subscribe(self, request, id=None):
        """
        Subscribe (POST) to or unsubscribe (DELETE) from the user with the given id.
        Requires authentication.
        """
        user = request.user
        following_user = get_object_or_404(User, id=id)

        if user == following_user:
            return Response({'errors': 'You cannot subscribe to yourself.'},
                            status=status.HTTP_400_BAD_REQUEST)

        follow_instance = Follow.objects.filter(user=user, following=following_user)

        if request.method == 'POST':
            if follow_instance.exists():
                return Response({'errors': 'You are already subscribed to this user.'},
                                status=status.HTTP_400_BAD_REQUEST)
            # Create the follow relationship
            Follow.objects.create(user=user, following=following_user)
            # Return the representation of the followed user
            serializer = FollowSerializer(following_user, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == 'DELETE':
            if not follow_instance.exists():
                return Response({'errors': 'You are not subscribed to this user.'},
                                status=status.HTTP_400_BAD_REQUEST)
            # Delete the follow relationship
            follow_instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
    
    def avatar(self, request):
        """
        DELETE /users/me/avatar/  →  удалить аватар и вернуть 204.
        """
        user = request.user
        if not user.avatar:
            return Response(
                {'errors': 'Avatar already absent.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.avatar.delete(save=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Tags (Read Only).
    Accessible by anyone. No pagination.
    """
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None # No pagination for tags


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for Ingredients (Read Only with Search).
    Accessible by anyone. Supports searching by name start. No pagination.
    """
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [IngredientSearchFilter] # Use custom search filter
    search_fields = ['^name'] # Search starts with name (case-insensitive by default)
    pagination_class = None # No pagination for ingredients


class RecipeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Recipes.
    Handles CRUD operations, plus custom actions for favorite, shopping cart,
    and downloading the shopping list.
    Permissions: ReadOnly for anyone, Write allowed only for owner.
    Filtering: Supports filtering by tags, author, is_favorited, is_in_shopping_cart.
    Pagination: Uses custom pagination.
    """
    queryset = Recipe.objects.all()
    # Apply custom permission: Owner can edit/delete, anyone can read.
    # IsAuthenticatedOrReadOnly is implicitly handled for list/retrieve.
    # IsOwnerOrReadOnly checks author for update/destroy.
    permission_classes = [IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend] # Enable django-filter
    filterset_class = RecipeFilter # Use the custom filterset
    pagination_class = CustomPageNumberPagination # Use custom pagination

    def get_serializer_class(self):
        """Return appropriate serializer class based on action."""
        if self.action in ('list', 'retrieve'):
            return RecipeReadSerializer
        # For create, update, partial_update, destroy
        return RecipeWriteSerializer

    def perform_create(self, serializer):
        """Set the author automatically when creating a recipe."""
        serializer.save(author=self.request.user)

    def _manage_user_recipe_list(self, request, pk, related_model, serializer_class, error_msg_exists, error_msg_not_exists):
        """
        Helper function for adding (POST) / removing (DELETE) recipes
        from a user-specific list (Favorite or ShoppingCart).
        Requires authentication.
        """
        user = request.user
        recipe = get_object_or_404(Recipe, pk=pk)
        instance = related_model.objects.filter(user=user, recipe=recipe)

        if request.method == 'POST':
            if instance.exists():
                return Response({'errors': error_msg_exists}, status=status.HTTP_400_BAD_REQUEST)
            # Create the relationship
            related_model.objects.create(user=user, recipe=recipe)
            # Return the minified recipe representation
            serializer = serializer_class(recipe, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        elif request.method == 'DELETE':
            if not instance.exists():
                return Response({'errors': error_msg_not_exists}, status=status.HTTP_400_BAD_REQUEST)
            # Delete the relationship
            instance.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[permissions.IsAuthenticated])
    def favorite(self, request, pk=None):
        """Add (POST) or Remove (DELETE) recipe from favorites."""
        return self._manage_user_recipe_list(
            request=request,
            pk=pk,
            related_model=Favorite,
            serializer_class=RecipeMinifiedSerializer,
            error_msg_exists='Recipe already in favorites.',
            error_msg_not_exists='Recipe not in favorites.'
        )

    @action(detail=True, methods=['post', 'delete'],
            permission_classes=[permissions.IsAuthenticated])
    def shopping_cart(self, request, pk=None):
        """Add (POST) or Remove (DELETE) recipe from shopping cart."""
        return self._manage_user_recipe_list(
            request=request,
            pk=pk,
            related_model=ShoppingCart,
            serializer_class=RecipeMinifiedSerializer,
            error_msg_exists='Recipe already in shopping cart.',
            error_msg_not_exists='Recipe not in shopping cart.'
        )

    @action(detail=False, methods=['get'],
            permission_classes=[permissions.IsAuthenticated])
    def download_shopping_cart(self, request):
        """
        Download the shopping list as a text file for the authenticated user.
        Aggregates ingredients from all recipes in the user's shopping cart.
        """
        user = request.user
        # Check if the shopping cart is empty first
        if not ShoppingCart.objects.filter(user=user).exists():
             return Response({'errors': 'Shopping cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        # Get ingredients from recipes in the user's cart, aggregate amounts
        ingredients = RecipeIngredient.objects.filter(
            recipe__in_shopping_carts__user=user # Filter through the ShoppingCart relation
        ).values(
            # Select ingredient fields
            'ingredient__name',
            'ingredient__measurement_unit'
        ).annotate(
            # Sum the amount for each unique ingredient+unit combination
            total_amount=Sum('amount')
        ).order_by('ingredient__name') # Ensure consistent order

        # Prepare the text content
        shopping_list_content = "Foodgram Shopping List:\n\n"
        for item in ingredients:
            shopping_list_content += (
                f"- {item['ingredient__name']} "
                f"({item['ingredient__measurement_unit']}): "
                f"{item['total_amount']}\n"
            )

        # Create the HttpResponse with plain text content type
        response = HttpResponse(shopping_list_content, content_type='text/plain; charset=utf-8')
        # Set the Content-Disposition header to trigger download
        response['Content-Disposition'] = 'attachment; filename="foodgram_shopping_list.txt"'
        return response
