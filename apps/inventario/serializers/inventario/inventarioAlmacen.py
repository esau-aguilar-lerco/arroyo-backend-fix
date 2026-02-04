from rest_framework import serializers


class InventarioProductoViewSerializer(serializers.Serializer):
    """
    Serializer para representar un producto en el inventario.
    Incluye información del producto y su cantidad disponible.
    """
    producto_id = serializers.IntegerField(
        help_text="ID único del producto",
        read_only=True
    )
    producto_nombre = serializers.CharField(
        help_text="Nombre completo del producto",
        read_only=True,
        max_length=150
    )
    producto_clave = serializers.CharField(
        help_text="Clave o código del producto",
        read_only=True,
        max_length=30,
        allow_blank=True
    )
    producto_unidad = serializers.CharField(
        help_text="Nombre de la unidad de medida del producto",
        read_only=True,
        allow_blank=True
    )
    producto_unidad_clave = serializers.CharField(
        help_text="Clave SAT de la unidad de medida",
        read_only=True,
        allow_blank=True
    )
    cantidad_disponible = serializers.IntegerField(
        help_text="Cantidad total disponible en el almacén (suma de todos los lotes)",
        read_only=True
    )


class InventarioAlmacenViewSerializer(serializers.Serializer):
    """
    Serializer para representar el inventario completo de un almacén.
    Incluye información del almacén y lista de productos ordenados por cantidad descendente.
    """
    almacen_id = serializers.IntegerField(
        help_text="ID único del almacén",
        read_only=True
    )
    almacen_nombre = serializers.CharField(
        help_text="Nombre del almacén",
        read_only=True,
        max_length=200
    )
    encargado_nombre = serializers.CharField(
        help_text="Nombre completo del encargado del almacén",
        read_only=True,
        allow_blank=True
    )
    productos = InventarioProductoViewSerializer(
        many=True,
        help_text="Lista de productos en el almacén ordenados por cantidad disponible (mayor a menor)",
        read_only=True
    )