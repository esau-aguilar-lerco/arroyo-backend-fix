from django.contrib import admin
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib.auth.hashers import make_password
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import Group, Permission
from django import forms
from .models import Usuario


class UsuarioCreationForm(UserCreationForm):
    """Form para crear nuevos usuarios"""
    class Meta:
        model = Usuario
        fields = ('username', 'email', 'nombre', 'apellido_paterno', 'apellido_materno')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UsuarioChangeForm(UserChangeForm):
    """Form para editar usuarios existentes"""
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={'placeholder': 'Dejar vacío para mantener la contraseña actual'}),
        required=False,
        help_text="Dejar vacío para mantener la contraseña actual. Si desea cambiarla, ingrese la nueva contraseña."
    )
    
    class Meta:
        model = Usuario
        fields = '__all__'

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password and len(password) < 6:
            raise forms.ValidationError("La contraseña debe tener al menos 6 caracteres.")
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioChangeForm
    add_form = UsuarioCreationForm
    
    # Configuración de la lista
    list_display = ('username', 'nombre', 'apellido_paterno', 'apellido_materno', 'email', 'is_active', 'is_staff', 'access_to_app', 'get_created_at')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'access_to_app', 'groups', 'created_at')
    search_fields = ('username', 'nombre', 'apellido_paterno', 'apellido_materno', 'email')
    ordering = ('-created_at',)
    
    # Configuración de fieldsets (tabs)
    fieldsets = (
        ('Información de Acceso', {
            'fields': ('username', 'password', 'email'),
            'description': 'Credenciales de acceso al sistema'
        }),
        ('Información Personal', {
            'fields': ('nombre', 'apellido_paterno', 'apellido_materno', 'telefono_1', 'telefono_2'),
            'description': 'Datos personales del usuario'
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'access_to_app', 'groups', 'user_permissions'),
            'classes': ('collapse',),
            'description': 'Configuración de permisos y accesos'
        }),
        ('Información del Sistema', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',),
            'description': 'Información de auditoría del sistema'
        }),
        ('Fechas Importantes', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
            'description': 'Fechas relevantes del usuario'
        }),
        ('Asignaciones', {
            'fields': ('almacen', 'sucursal'),
            'classes': ('collapse',),
            'description': 'Asignaciones del usuario'
        })
    )
    
    # Fieldsets para crear usuario
    add_fieldsets = (
        ('Información de Acceso', {
            'fields': ('username', 'email', 'password1', 'password2'),
            'description': 'Credenciales de acceso al sistema'
        }),
        ('Información Personal', {
            'fields': ('nombre', 'apellido_paterno', 'apellido_materno', 'telefono_1'),
            'description': 'Datos personales del usuario'
        }),
        ('Permisos Básicos', {
            'fields': ('is_active', 'access_to_app'),
            'description': 'Configuración básica de accesos'
        }),
    )
    
    # Campos de solo lectura
    readonly_fields = ('created_at', 'updated_at', 'last_login', 'date_joined', 'get_created_by', 'get_updated_by')
    
    # Configurar filtros horizontales para mejor UX
    filter_horizontal = ('groups', 'user_permissions')
    
    def get_readonly_fields(self, request, obj=None):
        """Campos de solo lectura dinámicos"""
        readonly = list(self.readonly_fields)
        
        # Si es edición, agregar campos de auditoría
        if obj:
            readonly.extend(['created_by', 'updated_by'])
        
        return readonly
    
    def save_model(self, request, obj, form, change):
        """Sobrescribir save_model para manejar auditoría"""
        if not change:  # Si es creación
            obj.created_by = request.user
        else:  # Si es edición
            obj.updated_by = request.user
        
        super().save_model(request, obj, form, change)
    
    def get_created_by(self, obj):
        """Mostrar quien creó el usuario"""
        return obj.get_created_by
    get_created_by.short_description = 'Creado por'
    
    def get_updated_by(self, obj):
        """Mostrar quien actualizó el usuario"""
        return obj.get_updated_by
    get_updated_by.short_description = 'Actualizado por'


# Personalizar el admin de grupos para mejorar la gestión de permisos
class CustomGroupAdmin(GroupAdmin):
    """Admin personalizado para grupos con mejor gestión de permisos"""
    list_display = ('name', 'get_permission_count', 'get_user_count')
    search_fields = ('name',)
    filter_horizontal = ('permissions',)
    
    # Organizar permisos por aplicación
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "permissions":
            # Ordenar permisos por app y luego por modelo
            kwargs["queryset"] = Permission.objects.select_related('content_type').order_by(
                'content_type__app_label', 
                'content_type__model', 
                'codename'
            )
        return super().formfield_for_manytomany(db_field, request, **kwargs)
    
    def get_permission_count(self, obj):
        """Mostrar cantidad de permisos asignados"""
        return obj.permissions.count()
    get_permission_count.short_description = 'Permisos'
    
    def get_user_count(self, obj):
        """Mostrar cantidad de usuarios en el grupo"""
        return obj.user_set.count()
    get_user_count.short_description = 'Usuarios'

    # Agregar acciones personalizadas
    actions = ['duplicate_group']
    
    def duplicate_group(self, request, queryset):
        """Duplicar grupos seleccionados"""
        for group in queryset:
            # Crear copia del grupo
            new_group = Group.objects.create(name=f"{group.name} (Copia)")
            # Copiar permisos
            new_group.permissions.set(group.permissions.all())
            
        self.message_user(request, f"Se duplicaron {queryset.count()} grupo(s) exitosamente.")
    duplicate_group.short_description = "Duplicar grupos seleccionados"


# Personalizar el admin de permisos para mejor visualización
class CustomPermissionAdmin(admin.ModelAdmin):
    """Admin personalizado para permisos con mejor organización"""
    list_display = ('name', 'codename', 'content_type', 'get_app_label')
    list_filter = ('content_type__app_label', 'content_type__model')
    search_fields = ('name', 'codename', 'content_type__model')
    ordering = ('content_type__app_label', 'content_type__model', 'codename')
    
    def get_app_label(self, obj):
        """Mostrar la aplicación del permiso"""
        return obj.content_type.app_label
    get_app_label.short_description = 'Aplicación'
    
    # Hacer readonly para evitar modificaciones accidentales
    readonly_fields = ('codename', 'content_type')


# Registrar los admins personalizados
# Primero desregistrar los originales si existen
admin.site.unregister(Group)
try:
    admin.site.unregister(Permission)
except admin.sites.NotRegistered:
    pass

# Registrar los nuevos admins
admin.site.register(Group, CustomGroupAdmin)
admin.site.register(Permission, CustomPermissionAdmin)