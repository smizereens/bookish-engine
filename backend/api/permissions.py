from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object (e.g., recipe) to edit it.
    Read access is allowed to anyone (authenticated or not).
    Assumes the model instance has an `author` attribute.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request (GET, HEAD, OPTIONS).
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed if the user is authenticated
        # and is the author of the object.
        # Ensure obj has 'author' attribute before comparing.
        return (
            request.user and
            request.user.is_authenticated and
            hasattr(obj, 'author') and
            obj.author == request.user
        )

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow read access to anyone, but write/delete
    access only to admin users (is_staff=True).
    """
    def has_permission(self, request, view):
        # Read permissions are allowed to any request (GET, HEAD, OPTIONS).
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to admin users.
        return request.user and request.user.is_staff

# Example of a permission that requires authentication for any access
class IsAuthenticated(permissions.BasePermission):
    """
    Allows access only to authenticated users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

# Example of a permission that allows full access only to admin users
class IsAdminUser(permissions.BasePermission):
    """
    Allows access only to admin users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_staff