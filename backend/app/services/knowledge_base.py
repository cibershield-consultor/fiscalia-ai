"""
Base de conocimiento fiscal estática para Fiscalía IA.
Datos de referencia rápida (sin IA) para respuestas instantáneas.
"""

GASTOS_DEDUCIBLES = {
    "cuota_autonomo": {
        "nombre": "Cuota de autónomo (Seguridad Social)",
        "porcentaje": 100,
        "condicion": "Siempre deducible",
        "modelo": "Modelo 130 (gasto actividad económica)",
    },
    "suministros_local": {
        "nombre": "Suministros de local de trabajo exclusivo",
        "porcentaje": 100,
        "condicion": "El local debe ser exclusivamente de trabajo",
        "modelo": "Modelo 130",
    },
    "suministros_vivienda": {
        "nombre": "Suministros de vivienda habitual (trabajo desde casa)",
        "porcentaje": 30,
        "condicion": "Se aplica sobre la parte proporcional de la vivienda usada para trabajar",
        "modelo": "Modelo 130",
        "nota": "Solo si el espacio está destinado exclusivamente a la actividad",
    },
    "telefono_exclusivo": {
        "nombre": "Teléfono móvil de uso exclusivo laboral",
        "porcentaje": 100,
        "condicion": "Solo si el teléfono es exclusivamente profesional",
        "modelo": "Modelo 303 (IVA) + Modelo 130 (IRPF)",
    },
    "telefono_mixto": {
        "nombre": "Teléfono móvil de uso mixto",
        "porcentaje": 50,
        "condicion": "Uso mixto (personal y profesional)",
        "modelo": "Modelo 303 (50% IVA) + Modelo 130 (50% IRPF)",
    },
    "material_oficina": {
        "nombre": "Material de oficina y fungible",
        "porcentaje": 100,
        "condicion": "Relacionado con la actividad",
        "modelo": "Modelo 303 + 130",
    },
    "software": {
        "nombre": "Software, licencias, suscripciones SaaS",
        "porcentaje": 100,
        "condicion": "Relacionado con la actividad profesional",
        "modelo": "Modelo 303 + 130",
        "ejemplos": "Adobe, Notion, Figma, GitHub, Slack",
    },
    "formacion": {
        "nombre": "Formación y cursos",
        "porcentaje": 100,
        "condicion": "Directamente relacionada con la actividad",
        "modelo": "Modelo 130",
    },
    "asesoria": {
        "nombre": "Asesoría, gestoría, abogados",
        "porcentaje": 100,
        "condicion": "Por servicios relacionados con la actividad",
        "modelo": "Modelo 303 + 130",
    },
    "publicidad": {
        "nombre": "Publicidad y marketing",
        "porcentaje": 100,
        "condicion": "Relacionado con la actividad",
        "modelo": "Modelo 303 + 130",
    },
    "dietas": {
        "nombre": "Dietas y gastos de manutención",
        "porcentaje": 100,
        "condicion": "Con límites diarios: 26,67€/día España, 48,08€/día extranjero",
        "modelo": "Modelo 130",
        "nota": "Deben estar justificadas con ticket o factura y realizarse fuera del municipio habitual",
    },
    "vehiculo": {
        "nombre": "Vehículo",
        "porcentaje": 100,
        "condicion": "SOLO si uso exclusivo empresarial (muy difícil de justificar)",
        "modelo": "Modelo 303 + 130",
        "nota": "Para uso mixto, Hacienda generalmente no acepta la deducción parcial de autónomos persona física",
    },
    "equipos": {
        "nombre": "Equipos informáticos",
        "porcentaje": 100,
        "condicion": "Si < 300€: gasto directo. Si > 300€: amortización (25%/año)",
        "modelo": "Modelo 303 + 130",
    },
    "alquiler_local": {
        "nombre": "Alquiler de local u oficina",
        "porcentaje": 100,
        "condicion": "Local dedicado a la actividad",
        "modelo": "Modelo 115 (retención 19%) + 303 + 130",
    },
    "seguros": {
        "nombre": "Seguros relacionados con la actividad",
        "porcentaje": 100,
        "condicion": "Seguro de responsabilidad civil, seguro del local, etc.",
        "modelo": "Modelo 130",
    },
}

MODELOS_FISCALES = {
    "036": {
        "nombre": "Modelo 036",
        "descripcion": "Declaración censal — Alta, modificación o baja en la actividad",
        "plazo": "Antes de iniciar la actividad o al producirse cambios",
        "quien": "Todos los autónomos y empresas",
    },
    "037": {
        "nombre": "Modelo 037",
        "descripcion": "Declaración censal simplificada (versión reducida del 036)",
        "plazo": "Antes de iniciar la actividad",
        "quien": "Personas físicas con actividad simple",
    },
    "130": {
        "nombre": "Modelo 130",
        "descripcion": "Pago fraccionado IRPF — 20% del rendimiento neto",
        "plazo": "Trimestral: 20 abril, 20 julio, 20 octubre, 30 enero",
        "quien": "Autónomos en estimación directa (sin retención en todas las facturas)",
        "nota": "No obligatorio si más del 70% de ingresos llevan retención del 15%",
    },
    "303": {
        "nombre": "Modelo 303",
        "descripcion": "Autoliquidación del IVA — Diferencia entre IVA repercutido y soportado",
        "plazo": "Trimestral: 20 abril, 20 julio, 20 octubre, 30 enero",
        "quien": "Todos los autónomos sujetos a IVA",
    },
    "390": {
        "nombre": "Modelo 390",
        "descripcion": "Declaración anual resumen de IVA",
        "plazo": "Hasta el 30 de enero del año siguiente",
        "quien": "Todos los que presentan el Modelo 303",
    },
    "347": {
        "nombre": "Modelo 347",
        "descripcion": "Declaración anual de operaciones con terceros (> 3.005,06€)",
        "plazo": "Febrero del año siguiente",
        "quien": "Quien tenga operaciones con clientes/proveedores > 3.005,06€/año",
    },
    "111": {
        "nombre": "Modelo 111",
        "descripcion": "Retenciones e ingresos a cuenta del IRPF (trabajadores o profesionales)",
        "plazo": "Trimestral: mismos plazos que el 130",
        "quien": "Quien tenga empleados o pague a profesionales con retención",
    },
    "190": {
        "nombre": "Modelo 190",
        "descripcion": "Resumen anual de retenciones (empleados y profesionales)",
        "plazo": "Hasta el 31 de enero del año siguiente",
        "quien": "Quien presente el Modelo 111",
    },
    "100": {
        "nombre": "Modelo 100",
        "descripcion": "Declaración de la Renta (IRPF anual)",
        "plazo": "Entre abril y junio del año siguiente",
        "quien": "Todos los autónomos con ingresos > 1.000€ o con derecho a devolución",
    },
    "115": {
        "nombre": "Modelo 115",
        "descripcion": "Retención sobre alquileres de inmuebles urbanos (19%)",
        "plazo": "Trimestral",
        "quien": "Quien paga alquiler de local de negocio",
    },
    "200": {
        "nombre": "Modelo 200",
        "descripcion": "Impuesto de Sociedades",
        "plazo": "25 días después de 6 meses desde el cierre del ejercicio",
        "quien": "Sociedades Limitadas (SL) y Sociedades Anónimas (SA)",
    },
}

TIPOS_IVA_INFO = {
    "21_general": {
        "tipo": "21%",
        "nombre": "General",
        "aplica_a": [
            "Mayoría de servicios profesionales",
            "Productos industriales",
            "Ropa y calzado",
            "Electrodomésticos",
            "Vehículos",
        ],
    },
    "10_reducido": {
        "tipo": "10%",
        "nombre": "Reducido",
        "aplica_a": [
            "Hostelería y restauración",
            "Transporte de viajeros",
            "Productos hortofrutícolas",
            "Gafas y lentillas",
            "Servicios veterinarios",
            "Viviendas de protección oficial",
        ],
    },
    "4_superreducido": {
        "tipo": "4%",
        "nombre": "Superreducido",
        "aplica_a": [
            "Pan, leche, queso, huevos, frutas, verduras",
            "Libros, periódicos y revistas",
            "Medicamentos de uso humano",
            "Vehículos para discapacitados",
        ],
    },
    "0_exento": {
        "tipo": "0%",
        "nombre": "Exento / 0%",
        "aplica_a": [
            "Exportaciones fuera de la UE",
            "Entregas intracomunitarias",
            "Servicios médicos y sanitarios",
            "Servicios educativos reglados",
            "Servicios financieros",
            "Operaciones de seguro",
        ],
    },
}

AUTONOMOS_NOVEDADES_2024_2025 = [
    "Sistema de cotización por ingresos reales (vigente desde 2023, consolida en 2024-2025)",
    "15 tramos de cotización según rendimientos netos previstos",
    "Tarifa plana de 80€/mes para nuevos autónomos durante los primeros 12 meses",
    "Deducción por plan de pensiones: límite de 1.500€/año (desde 2023)",
    "IVA 0% en alimentos básicos ampliado (aceite, pasta) hasta revisión",
    "Reducción por inicio de actividad: 20% primeros 2 años con rendimiento positivo",
]
