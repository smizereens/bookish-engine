from django.db import transaction
from djoser.serializers import UserCreateSerializer, UserSerializer
from rest_framework import serializers
from drf_extra_fields.fields import Base64ImageField # Use the field from the library

from .models import (User, Tag, Ingredient, Recipe, RecipeIngredient,
                     Follow, Favorite, ShoppingCart)


# --- User Serializers (Djoser customization) ---
class CustomUserSerializer(UserSerializer):
    """Serializer for User display, includes subscription status."""
    is_subscribed = serializers.SerializerMethodField(read_only=True)
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'avatar')

    def get_is_subscribed(self, obj):
        """Check if the request user is subscribed to the obj user."""
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        user = request.user
        return Follow.objects.filter(user=user, following=obj).exists()

class CustomUserCreateSerializer(UserCreateSerializer):
    """Serializer for User creation."""
    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'password')


# --- Core Model Serializers ---
class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model."""
    class Meta:
        model = Tag
        fields = ('id', 'name', 'color', 'slug')
        read_only_fields = ('id', 'name', 'color', 'slug') # Tags are read-only via API

class IngredientSerializer(serializers.ModelSerializer):
    """Serializer for Ingredient model."""
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')
        read_only_fields = ('id', 'name', 'measurement_unit') # Ingredients are read-only via API

class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    """Serializer for reading ingredient amounts within a recipe."""
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeIngredientWriteSerializer(serializers.Serializer):
    """Serializer for writing ingredient amounts when creating/updating a recipe."""
    # Use Serializer, not ModelSerializer, as we don't directly map to RecipeIngredient fields
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.IntegerField(min_value=1, error_messages={'min_value': 'Amount must be at least 1.'})

    # No Meta class needed here as it's not a ModelSerializer


class RecipeReadSerializer(serializers.ModelSerializer):
    """Serializer for reading/listing Recipes."""
    tags = TagSerializer(many=True, read_only=True)
    author = CustomUserSerializer(read_only=True)
    # Use RecipeIngredientReadSerializer for the 'through' model
    ingredients = RecipeIngredientReadSerializer(
        source='recipeingredients', # Use the related_name from RecipeIngredient
        many=True,
        read_only=True
    )
    is_favorited = serializers.SerializerMethodField(read_only=True)
    is_in_shopping_cart = serializers.SerializerMethodField(read_only=True)
    # Use the standard ImageField URL for reading
    image = serializers.ImageField(read_only=True, use_url=True)

    class Meta:
        model = Recipe
        fields = ('id', 'tags', 'author', 'ingredients', 'is_favorited',
                  'is_in_shopping_cart', 'name', 'image', 'text',
                  'cooking_time')

    def _get_user_recipe_status(self, obj, related_model):
        """Helper to check if user has added recipe to Favorite/ShoppingCart."""
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        user = request.user
        return related_model.objects.filter(user=user, recipe=obj).exists()

    def get_is_favorited(self, obj):
        return self._get_user_recipe_status(obj, Favorite)

    def get_is_in_shopping_cart(self, obj):
        return self._get_user_recipe_status(obj, ShoppingCart)


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating Recipes."""
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )
    # Use the custom write serializer for ingredients
    ingredients = RecipeIngredientWriteSerializer(many=True)
    # Use Base64ImageField for writing
    image = Base64ImageField()
    author = CustomUserSerializer(read_only=True) # Author is set in the view
    # Make cooking_time writeable but also validate
    cooking_time = serializers.IntegerField(min_value=1, error_messages={'min_value': 'Cooking time must be at least 1 minute.'})

    class Meta:
        model = Recipe
        fields = ('id', 'tags', 'ingredients', 'name', 'image', 'text',
                  'cooking_time', 'author') # Author included for potential display after create
        read_only_fields = ('id', 'author')

    def validate_ingredients(self, ingredients):
        if not ingredients:
            raise serializers.ValidationError("At least one ingredient is required.")
        ingredient_ids = []
        for item in ingredients:
            # item['id'] is actually the Ingredient object here due to PrimaryKeyRelatedField
            ingredient = item['id']
            if ingredient in ingredient_ids:
                 raise serializers.ValidationError(f"Ingredient '{ingredient.name}' added more than once.")
            ingredient_ids.append(ingredient)
            # Amount validation happens in RecipeIngredientWriteSerializer
        return ingredients

    def validate_tags(self, tags):
        if not tags:
            raise serializers.ValidationError("At least one tag is required.")
        if len(tags) != len(set(tags)):
            raise serializers.ValidationError("Tags must be unique.")
        return tags

    def _add_ingredients_and_tags(self, recipe, ingredients_data, tags_data):
        """Helper to add ingredients and tags after recipe is created/updated."""
        # Clear existing ingredients before adding new ones (for update)
        RecipeIngredient.objects.filter(recipe=recipe).delete()
        recipe_ingredients = [
            RecipeIngredient(
                recipe=recipe,
                ingredient=item['id'], # item['id'] is the Ingredient instance
                amount=item['amount']
            ) for item in ingredients_data
        ]
        RecipeIngredient.objects.bulk_create(recipe_ingredients)
        recipe.tags.set(tags_data)

    @transaction.atomic # Ensure atomicity
    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')
        # Author is added from the request context in the view's perform_create
        recipe = Recipe.objects.create(**validated_data)
        self._add_ingredients_and_tags(recipe, ingredients_data, tags_data)
        return recipe

    @transaction.atomic # Ensure atomicity
    def update(self, instance, validated_data):
        # Pop ingredients and tags data if they exist in validated_data
        ingredients_data = validated_data.pop('ingredients', None)
        tags_data = validated_data.pop('tags', None)

        # Update simple fields using the parent's update method
        # This handles fields like name, text, cooking_time, image
        instance = super().update(instance, validated_data)

        # Update M2M/related fields only if new data was provided
        if ingredients_data is not None:
            # Clear existing and add new ones
            RecipeIngredient.objects.filter(recipe=instance).delete()
            recipe_ingredients = [
                RecipeIngredient(
                    recipe=instance,
                    ingredient=item['id'],
                    amount=item['amount']
                ) for item in ingredients_data
            ]
            RecipeIngredient.objects.bulk_create(recipe_ingredients)

        if tags_data is not None:
            instance.tags.set(tags_data)

        # No need to call instance.save() again, super().update() handles it.
        return instance

    def to_representation(self, instance):
        # Use the read serializer for representation after create/update
        # Pass the context from the write serializer to the read serializer
        return RecipeReadSerializer(instance, context=self.context).data


# --- User Interaction Serializers ---
class RecipeMinifiedSerializer(serializers.ModelSerializer):
    """Simplified serializer for recipes in lists like Favorites/ShoppingCart."""
    # Use standard ImageField URL for representation
    image = serializers.ImageField(read_only=True, use_url=True)

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')


class FollowSerializer(serializers.ModelSerializer):
    """Serializer for displaying subscriptions (users someone is following)."""
    # We are serializing the 'following' User object, not the Follow instance
    email = serializers.ReadOnlyField(source='following.email')
    id = serializers.ReadOnlyField(source='following.id')
    username = serializers.ReadOnlyField(source='following.username')
    first_name = serializers.ReadOnlyField(source='following.first_name')
    last_name = serializers.ReadOnlyField(source='following.last_name')
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        # The serializer represents the User being followed
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'recipes', 'recipes_count')

    def get_is_subscribed(self, obj):
        """Check if the request user is subscribed to this 'obj' (the 'following' user)."""
        # This should always be true when listing subscriptions, but good practice
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False # Should not happen in subscriptions view
        user = request.user
        # 'obj' here is the user being followed (the 'following' field in the Follow model)
        return Follow.objects.filter(user=user, following=obj).exists()

    def get_recipes(self, obj):
        """Get limited recipes for the subscribed author ('obj')."""
        request = self.context.get('request')
        limit_param = request.query_params.get('recipes_limit')
        recipes = obj.recipes.all() # 'obj' is the author (User model)
        if limit_param:
            try:
                limit = int(limit_param)
                recipes = recipes[:limit]
            except (ValueError, TypeError):
                pass # Ignore invalid limit
        # Use the minified serializer for recipes list
        return RecipeMinifiedSerializer(recipes, many=True, context=self.context).data

    def get_recipes_count(self, obj):
        """Count recipes for the subscribed author ('obj')."""
        return obj.recipes.count() # 'obj' is the author (User model)