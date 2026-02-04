from rest_framework import permissions

class SmartModelPermission(permissions.BasePermission):
    """
    Clase de permisos inteligente con soporte para configuración avanzada
    """
    
    def __init__(self, model_name, app_label='erp', custom_permissions=None):
        self.model_name = model_name
        self.app_label = app_label
        self.custom_permissions = custom_permissions or {}
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Verificar permisos custom primero
        if hasattr(view, 'action') and view.action in self.custom_permissions:
            required_perm = self.custom_permissions[view.action]
            return request.user.has_perm(required_perm)

        # Mapeo estándar
        standard_permissions = {
            'GET': f'{self.app_label}.can_view_{self.model_name}',
            'HEAD': f'{self.app_label}.can_view_{self.model_name}',
            'OPTIONS': f'{self.app_label}.can_view_{self.model_name}',
            'POST': f'{self.app_label}.can_create_{self.model_name}',
            'PUT': f'{self.app_label}.can_update_{self.model_name}',
            'PATCH': f'{self.app_label}.can_update_{self.model_name}',
            'DELETE': f'{self.app_label}.can_delete_{self.model_name}',
        }

        required_permission = standard_permissions.get(request.method)
        return required_permission and request.user.has_perm(required_permission)

def model_permission(model_name, **kwargs):
    """Devuelve una clase de permiso personalizada lista para usar en DRF"""
    class DynamicModelPermission(SmartModelPermission):
        def __init__(self):
            super().__init__(model_name, **kwargs)
    return DynamicModelPermission