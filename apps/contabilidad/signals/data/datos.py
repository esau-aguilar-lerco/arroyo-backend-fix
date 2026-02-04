
# Lista de regímenes fiscales del SAT (catálogo actualizado)
REGIMENES_FISCALES = [
    {"codigo": "601", "nombre": "GENERAL DE LEY PERSONAS MORALES"},
    {"codigo": "603", "nombre": "PERSONAS MORALES CON FINES NO LUCRATIVOS"},
    {"codigo": "605", "nombre": "SUELDOS Y SALARIOS E INGRESOS ASIMILADOS A SALARIOS"},
    {"codigo": "606", "nombre": "ARRENDAMIENTO"},
    {"codigo": "607", "nombre": "RÉGIMEN DE ENAJENACIÓN O ADQUISICIÓN DE BIENES"},
    {"codigo": "608", "nombre": "DEMÁS INGRESOS"},
    {"codigo": "610", "nombre": "RESIDENTES EN EL EXTRANJERO SIN ESTABLECIMIENTO PERMANENTE EN MÉXICO"},
    {"codigo": "611", "nombre": "INGRESOS POR DIVIDENDOS (SOCIOS Y ACCIONISTAS)"},
    {"codigo": "612", "nombre": "PERSONAS FÍSICAS CON ACTIVIDADES EMPRESARIALES Y PROFESIONALES"},
    {"codigo": "614", "nombre": "INGRESOS POR INTERESES"},
    {"codigo": "615", "nombre": "RÉGIMEN DE LOS INGRESOS POR OBTENCIÓN DE PREMIOS"},
    {"codigo": "616", "nombre": "SIN OBLIGACIONES FISCALES"},
    {"codigo": "620", "nombre": "SOCIEDADES COOPERATIVAS DE PRODUCCIÓN QUE OPTAN POR DIFERIR SUS INGRESOS"},
    {"codigo": "621", "nombre": "INCORPORACIÓN FISCAL (RIF, AHORA RESICO)"},
    {"codigo": "622", "nombre": "ACTIVIDADES AGRÍCOLAS, GANADERAS, SILVÍCOLAS Y PESQUERAS"},
    {"codigo": "623", "nombre": "OPCIONAL PARA GRUPOS DE SOCIEDADES"},
    {"codigo": "624", "nombre": "COORDINADOS"},
    {"codigo": "625", "nombre": "RÉGIMEN DE LAS ACTIVIDADES EMPRESARIALES CON INGRESOS A TRAVÉS DE PLATAFORMAS TECNOLÓGICAS"},
    {"codigo": "626", "nombre": "RÉGIMEN SIMPLIFICADO DE CONFIANZA (RESICO PERSONAS FÍSICAS)"},
    {"codigo": "628", "nombre": "HIDROCARBUROS"},
    {"codigo": "629", "nombre": "DE LOS REGÍMENES FISCALES PREFERENTES Y DE LAS EMPRESAS MULTINACIONALES"},
    {"codigo": "630", "nombre": "ENAJENACIÓN DE ACCIONES EN BOLSA DE VALORES"},
]



METODOS_PAGO = [
    {'nombre': 'EFECTIVO', 'tipo': 'EFECTIVO', 'is_credito': False},
    {'nombre': 'TARJETA DE CRÉDITO', 'tipo': 'TC', 'is_credito': False},
    {'nombre': 'TARJETA DE DÉBITO', 'tipo': 'TD', 'is_credito': False},
    {'nombre': 'CHEQUE', 'tipo': 'CHEQUE', 'is_credito': False},
    {'nombre': 'DEPÓSITO', 'tipo': 'DEPÓSITO', 'is_credito': False},
    {'nombre': 'CREDITO', 'tipo': 'CRE', 'is_credito': True},
]


# Lista de unidades SAT más comunes (Catálogo c_ClaveUnidad del SAT)
UNIDADES_SAT = [
    {'clave': 'H87', 'nombre': 'PIEZA'},
    {'clave': 'KGM', 'nombre': 'KILOGRAMO'},
    {'clave': 'E48', 'nombre': 'UNIDAD DE SERVICIO'},
    {'clave': 'ACT', 'nombre': 'ACTIVIDAD'},
    {'clave': 'XBX', 'nombre': 'CAJA'},
    {'clave': 'LTR', 'nombre': 'LITRO'},
    {'clave': 'MTR', 'nombre': 'METRO'},
    {'clave': 'XPK', 'nombre': 'PAQUETE'},
    {'clave': 'HUR', 'nombre': 'HORA'},
    {'clave': 'TNE', 'nombre': 'TONELADA'},
    {'clave': 'DAY', 'nombre': 'DÍA'},
    {'clave': 'XKI', 'nombre': 'KIT'},
    {'clave': 'SET', 'nombre': 'CONJUNTO'},
    {'clave': 'GRM', 'nombre': 'GRAMO'},
    {'clave': 'MTK', 'nombre': 'METRO CUADRADO'},
    {'clave': 'MTQ', 'nombre': 'METRO CÚBICO'},
    {'clave': 'CMT', 'nombre': 'CENTÍMETRO'},
    {'clave': 'MLT', 'nombre': 'MILILITRO'},
    {'clave': 'XUN', 'nombre': 'UNIDAD'},
    {'clave': 'MON', 'nombre': 'MES'},
]