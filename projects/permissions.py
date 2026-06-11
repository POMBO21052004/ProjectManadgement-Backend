from rest_framework import permissions

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission personnalisée : seul le propriétaire ou un admin peut modifier/supprimer
    """
    
    def has_object_permission(self, request, view, obj):
        # Les admins ont tous les droits
        if request.user.is_admin or request.user.is_superuser:
            return True
        
        # Le propriétaire peut modifier sa propre tâche
        return obj.user == request.user


class IsAdminUser(permissions.BasePermission):
    """
    Permission : seuls les admins peuvent accéder
    """
    
    def has_permission(self, request, view):
        return request.user and (request.user.is_admin or request.user.is_superuser)

