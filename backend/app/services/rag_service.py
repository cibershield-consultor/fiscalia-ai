"""
FiscalIA — Motor RAG ligero (sin sentence-transformers, sin ChromaDB)
Búsqueda por TF-IDF + BM25 en memoria + web en tiempo real
RAM total: < 20MB
"""
import json
import math
import re
from datetime import datetime
from typing import Optional
import httpx

# ══════════════════════════════════════════════════════════════
#  BASE DE CONOCIMIENTO EN MEMORIA (sin BD vectorial)
# ══════════════════════════════════════════════════════════════

FISCAL_KNOWLEDGE_BASE = [
    {
        "id": "iva_tipos_2026",
        "text": """IVA España 2026 — Tipos impositivos vigentes:
Tipo general 21%: mayoría de bienes/servicios, ropa, electrónica, servicios profesionales, vehículos.
Tipo reducido 10%: hostelería, restauración, transporte viajeros, determinados alimentos, entradas eventos.
Tipo superreducido 4%: pan, leche, queso, huevos, frutas, verduras, libros, medicamentos, prótesis.
Exento 0%: exportaciones, operaciones intracomunitarias, servicios médicos, educativos, financieros, seguros.
Modelo 303: declaración trimestral. Plazos: 20 abril, 20 julio, 20 octubre, 30 enero.
Modelo 390: resumen anual IVA, hasta 30 enero año siguiente.
Criterio de caja: IVA cuando se cobra, no cuando se factura. Solicitar en modelo 036.
Recargo de equivalencia: comerciantes minoristas que no transformen productos.""",
        "keywords": ["iva", "impuesto valor añadido", "21%", "10%", "4%", "exento", "tipo", "303", "390", "trimestral", "factura"],
        "source": "AEAT", "url": "https://sede.agenciatributaria.gob.es/Sede/iva.html",
    },
    {
        "id": "irpf_tramos_2026",
        "text": """IRPF 2026 — Tramos estatales (sin cambios):
Hasta 12.450€: 19% | 12.450-20.200€: 24% | 20.200-35.200€: 30%
35.200-60.000€: 37% | 60.000-300.000€: 45% | Más de 300.000€: 47%
IMPORTANTE: Añadir tramo autonómico (varía por CCAA). País Vasco y Navarra tienen régimen foral.
Tipo efectivo siempre menor que el marginal.
Retenciones actividades económicas: 15% general, 7% primeros 2 años de actividad.
Modelo 130: pago fraccionado IRPF autónomos estimación directa, 20% rendimiento neto acumulado.
No obligatorio si más del 70% de ingresos llevan retención del 15%.
Modelo 100: declaración anual renta, campaña abril-junio.""",
        "keywords": ["irpf", "renta", "tramo", "tipo", "19%", "24%", "30%", "37%", "45%", "retención", "130", "100", "estimación directa"],
        "source": "AEAT", "url": "https://sede.agenciatributaria.gob.es/Sede/irpf.html",
    },
    {
        "id": "autonomos_cotizacion_2026",
        "text": """Cotización autónomos 2026 — Sistema por ingresos reales (desde 2023):
15 tramos según rendimientos netos mensuales:
< 670€: 200€/mes | 670-900€: 220€/mes | 900-1.166€: 260€/mes | 1.166-1.300€: 280€/mes
1.300-1.500€: 294€/mes | 1.500-1.700€: 294€/mes | 1.700-1.850€: 350€/mes | 1.850-2.030€: 370€/mes
2.030-2.330€: 390€/mes | 2.330-2.760€: 420€/mes | 2.760-3.190€: 460€/mes | 3.190-3.620€: 480€/mes
3.620-4.050€: 500€/mes | 4.050-6.000€: 530€/mes | > 6.000€: 590€/mes
Tarifa plana nuevos autónomos: 80€/mes primeros 12 meses.
Regularización anual: se ajusta al presentar la renta.
CNAE-2025: obligatorio actualizar código de actividad desde 1 enero 2026.""",
        "keywords": ["autónomo", "cuota", "cotización", "RETA", "seguridad social", "tarifa plana", "80€", "ingresos reales", "tramo", "CNAE"],
        "source": "TGSS", "url": "https://sede.seg-social.gob.es/wps/portal/sede/sede/Trabajadores/TrabajoAutonomo",
    },
    {
        "id": "gastos_deducibles",
        "text": """Gastos deducibles actividades económicas España 2026:
La deducibilidad depende del tipo de contribuyente y de que el gasto sea necesario para la actividad.
Para autónomos IRPF estimación directa:
- Cuota SS autónomo: 100% siempre deducible.
- Suministros local exclusivo (luz, agua, internet): 100%.
- Suministros vivienda habitual trabajo desde casa: 30% sobre % superficie afecta.
- Teléfono móvil uso exclusivo laboral: 100%. Uso mixto: 50%.
- Software y SaaS (Adobe, Notion, etc.): 100% si uso profesional.
- Formación relacionada con la actividad: 100%.
- Gestoría, asesoría, abogados: 100%.
- Marketing y publicidad: 100%.
- Dietas: máx. 26,67€/día España, 48,08€/día extranjero. Con justificante, fuera municipio habitual.
- Vehículo: solo 100% si uso exclusivo empresarial (muy difícil de justificar ante AEAT).
- Equipos informáticos: < 300€ gasto directo; > 300€ amortización 25%/año.
- Alquiler local: 100% (retener 19% IRPF al arrendador, Modelo 115).
Para empresas IS: gastos contabilizados relacionados con actividad son deducibles salvo limitaciones legales.""",
        "keywords": ["deducible", "gasto", "deducir", "teléfono", "suministros", "local", "vehículo", "formación", "dietas", "software", "gestoría"],
        "source": "AEAT", "url": "https://sede.agenciatributaria.gob.es/Sede/irpf/deducciones-gastos.html",
    },
    {
        "id": "modelos_plazos",
        "text": """Modelos fiscales España 2026 — Plazos:
TRIMESTRALES (T1 ene-mar, T2 abr-jun, T3 jul-sep, T4 oct-dic):
Modelo 303 (IVA): 20 abril, 20 julio, 20 octubre, 30 enero.
Modelo 130 (IRPF pago fraccionado autónomos): mismos plazos.
Modelo 111 (retenciones trabajo/actividades): mismos plazos.
Modelo 115 (retención alquileres): mismos plazos.
ANUALES:
Modelo 390 (resumen anual IVA): hasta 30 enero.
Modelo 190 (resumen retenciones): hasta 31 enero.
Modelo 347 (operaciones con terceros > 3.005,06€): febrero.
Modelo 100 (renta IRPF): campaña abril-junio.
Modelo 200 (Impuesto Sociedades): 25 días tras 6 meses del cierre.
CENSALES: Modelo 036/037: alta, modificación o baja en Hacienda.""",
        "keywords": ["modelo", "303", "130", "111", "115", "390", "190", "347", "100", "200", "036", "plazo", "trimestral", "anual", "declaración"],
        "source": "AEAT", "url": "https://sede.agenciatributaria.gob.es/Sede/Ayuda/calendario-contribuyente.html",
    },
    {
        "id": "novedades_2026",
        "text": """Novedades fiscales España 2026:
RDL 16/2025 (BOE 24/12/2025): DEROGADO por el Congreso el 27/01/2026. Sus medidas NO están vigentes.
Vigente: RDL 2/2026 y RDL 3/2026 (BOE 4/02/2026): prorrogan módulos 2026, deducción vehículos eléctricos, libre amortización renovables.
VERIFACTU (facturación verificable): Sociedades (IS) desde 1/1/2027. Autónomos (IRPF) desde 1/7/2027. Aplazado.
CNAE-2025: obligatorio actualizar código actividad en SS desde 1/1/2026. No hacerlo puede implicar cotización incorrecta.
Bizum y pagos digitales: desde 1/1/2026 mayor control AEAT. Cobros por servicios deben declararse.
Cuotas autónomos 2026: congeladas, mismas tablas que 2025.
IVA alimentos: tipo reducido en revisión, consultar BOE vigente.""",
        "keywords": ["novedad", "2026", "cambio", "verifactu", "CNAE", "RDL", "derogado", "bizum", "actualización", "normativa"],
        "source": "BOE/AEAT", "url": "https://www.boe.es/buscar/boe.php",
    },
    {
        "id": "impuesto_sociedades",
        "text": """Impuesto sobre Sociedades España 2026:
Tipo general: 25%.
Microempresas (INCN < 1M€): base 0-50.000€ al 19%, resto al 21%.
Entidades nueva creación (primeros 2 ejercicios con base positiva): 15%.
Cooperativas fiscalmente protegidas: 20%.
Entidades sin fines lucrativos (Ley 49/2002): 10%.
Limitación gastos financieros: 30% beneficio operativo (EBITDA fiscal). Mínimo deducible 1M€.
Amortizaciones según tablas reglamentarias. Libertad amortización I+D y elementos < 300€.
Gastos no deducibles: multas, sanciones, donativos sin amparo legal.
Modelo 200: autoliquidación anual. 25 días tras 6 meses del cierre.
Modelo 202: pagos fraccionados (obligatorio si cuota > 6.000€).""",
        "keywords": ["sociedades", "SL", "SA", "empresa", "25%", "IS", "impuesto", "200", "202", "microempresa", "15%"],
        "source": "AEAT", "url": "https://sede.agenciatributaria.gob.es/Sede/impuesto-sociedades.html",
    },
    {
        "id": "pgc_pymes",
        "text": """Plan General Contable PYMEs (RD 1515/2007) — Cuentas principales:
GASTOS (grupo 6): 600-602 Compras existencias | 621 Arrendamientos y cánones | 622 Reparaciones
623 Servicios profesionales independientes (gestores, abogados, consultores)
624 Transportes | 625 Seguros | 626 Servicios bancarios
627 Publicidad, propaganda y relaciones públicas
628 Suministros (electricidad, agua, gas, internet, teléfono fijo)
629 Otros servicios (SaaS, suscripciones, servicios varios)
640 Sueldos y salarios | 642 Seguridad Social empresa | 680-681 Amortizaciones
INGRESOS (grupo 7): 700 Ventas mercaderías | 705 Prestaciones servicios
740 Subvenciones explotación | 760 Ingresos financieros
Facturas: número, fecha, datos emisor/receptor, descripción, base imponible, tipo y cuota IVA.""",
        "keywords": ["PGC", "plan contable", "cuenta", "628", "623", "627", "629", "640", "705", "contabilidad", "asiento", "factura"],
        "source": "BOE", "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2007-19966",
    },
    {
        "id": "tipos_contribuyentes",
        "text": """Tipos de contribuyentes España — Diferencias fiscales:
AUTÓNOMO (trabajador por cuenta propia): tributa IRPF (estimación directa o módulos), no IS.
Cotiza RETA. Emite facturas con IVA. Modelos: 036/037, 303, 130, 390, 100.
EMPRESA (SL, SA, cooperativa): tributa IS, no IRPF. Trabajadores en Régimen General SS.
Modelos: 200, 202, 303, 390, 111, 190, 347.
TRABAJADOR CUENTA AJENA: tributa IRPF mediante retenciones nómina. NO cobra IVA.
No presenta 303 ni 130. Puede presentar 100 (declaración renta). Gastos deducibles muy limitados.
PROFESIONAL CON RETENCIÓN: autónomo con retención 15% (7% primeros 2 años). Puede estar exento de M.130.
SOCIEDAD CIVIL/COMUNIDAD DE BIENES: atribución de rentas a socios. Cada socio tributa en su IRPF.""",
        "keywords": ["autónomo", "empresa", "trabajador", "asalariado", "SL", "SA", "comunidad bienes", "sociedad civil", "cuenta ajena", "perfil"],
        "source": "AEAT", "url": "https://sede.agenciatributaria.gob.es",
    },
    # ── LGSS — Ley General Seguridad Social ──────────────────────
    {
        "id": "lgss_autonomos_reta",
        "text": """Ley General de la Seguridad Social (RDL 8/2015) — Autónomos y RETA:
El Régimen Especial de Trabajadores Autónomos (RETA) está regulado en el Título IV de la LGSS.
Están obligados a cotizar en el RETA: trabajadores por cuenta propia con actividad habitual, socios de
comunidades de bienes y sociedades civiles que ejerzan actividad, administradores de sociedades con
participación ≥ 25% (o ≥33% sin funciones de dirección), familiares colaboradores del autónomo hasta 2º grado.
Prestaciones del RETA: incapacidad temporal (IT) desde el 4º día (contingencias profesionales desde el 1º),
maternidad/paternidad, riesgo durante embarazo, cese de actividad ("paro del autónomo"), jubilación,
incapacidad permanente, viudedad, orfandad y prestación por fallecimiento.
Cese de actividad: se puede solicitar si se acreditan pérdidas del 10% en el ejercicio anterior
(excluido el primero), ejecución judicial o administrativa, fuerza mayor, divorcio o separación con
pérdida de la gestión del negocio, violencia de género o discapacidad sobrevenida.
IMPORTANTE: desde enero 2023 el sistema de cotización es por ingresos reales con regularización anual.
Ley: RDL 8/2015 — https://www.boe.es/buscar/act.php?id=BOE-A-2015-11724
TGSS: https://sede.seg-social.gob.es/wps/portal/sede/sede/Trabajadores/TrabajoAutonomo""",
        "keywords": ["LGSS", "seguridad social", "RETA", "autónomo", "cese actividad", "prestación", "IT", "baja", "jubilación", "cotizar", "ley general"],
        "source": "LGSS/TGSS", "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11724",
    },
    {
        "id": "lgss_regimen_general",
        "text": """Ley General de la Seguridad Social — Régimen General (trabajadores por cuenta ajena):
El Régimen General es el régimen ordinario para trabajadores asalariados. Regula bases y tipos de cotización.
Tipos cotización 2026 (aproximados, verificar en BOE vigente):
- Contingencias comunes: empresa 23,60% + trabajador 4,70% = 28,30% total.
- Desempleo (contrato indefinido): empresa 5,50% + trabajador 1,55%.
- FOGASA: empresa 0,20%.
- Formación profesional: empresa 0,60% + trabajador 0,10%.
- Horas extraordinarias: cotización adicional.
Bases de cotización: mínima (SMI) y máxima (actualizada anualmente por RDL).
SMI 2025-2026: 1.184€/mes (14 pagas). Base mínima cotización: equivalente al SMI.
Prestación por desempleo: se genera cotizando al menos 360 días en los últimos 6 años. Cuantía 70% base reguladora los primeros 180 días, 50% el resto.
IT (baja laboral): 60% base reguladora días 4-20, 75% desde día 21. Empresa abona días 4-15, INSS desde día 16.
Fuente: LGSS RDL 8/2015 — https://www.boe.es/buscar/act.php?id=BOE-A-2015-11724
SEPE: https://www.sepe.es/HomeSepe/Prestaciones/que-prestaciones-hay/Prestacion-contributiva.html""",
        "keywords": ["régimen general", "asalariado", "nómina", "cotización", "empresa", "desempleo", "paro", "FOGASA", "baja", "IT", "SMI", "contrato"],
        "source": "LGSS/SEPE", "url": "https://www.sepe.es/HomeSepe/Prestaciones/que-prestaciones-hay/Prestacion-contributiva.html",
    },
    # ── DGT — Dirección General de Tributos ───────────────────
    {
        "id": "dgt_consultas_vinculantes",
        "text": """Dirección General de Tributos (DGT) — Consultas vinculantes:
La DGT es el órgano del Ministerio de Hacienda que interpreta la normativa tributaria.
Sus consultas vinculantes tienen efecto vinculante para TODA la Administración tributaria (art. 89 LGT).
Esto significa que si la DGT ha respondido a una consulta sobre tu situación concreta, Hacienda
no puede aplicar un criterio distinto durante una inspección.

Consultas vinculantes relevantes frecuentes:
- Gastos deducibles en estimación directa: criterios sobre suministros, vehículo, teléfono.
- Tratamiento fiscal de dietas y gastos de representación.
- Deducibilidad de cuotas RETA como gasto de actividad (100% deducible, DGT V1847-05).
- Actividades exentas de IVA (formación, sanidad, financieros).
- Aplicación del 15% IS a entidades de nueva creación.
- Tributación de socios administradores (IRPF vs. IS).

Cómo consultar: La base de datos completa de consultas vinculantes está disponible en la web del Ministerio de Hacienda.
IMPORTANTE: Cada consulta se aplica al caso concreto analizado. Casos similares pueden tener tratamiento diferente.
Fuente DGT: https://www.hacienda.gob.es/es-ES/Normativa%20y%20doctrina/Doctrina/paginas/consultasdgt.aspx
AEAT consultas: https://sede.agenciatributaria.gob.es/Sede/normativa-criterios-interpretativos/doctrina-criterios-interpretativos/consultas-direccion-general-tributos.html""",
        "keywords": ["DGT", "consulta vinculante", "dirección general tributos", "hacienda", "interpretación", "criterio", "inspección", "vinculante"],
        "source": "DGT/Ministerio Hacienda", "url": "https://www.hacienda.gob.es/es-ES/Normativa%20y%20doctrina/Doctrina/paginas/consultasdgt.aspx",
    },
    # ── Ministerio de Hacienda / Ley General Tributaria ───────
    {
        "id": "lgt_ley_general_tributaria",
        "text": """Ley General Tributaria (Ley 58/2003) — Marco normativo básico:
La LGT establece los principios y normas básicas del sistema tributario español.
Conceptos clave para contribuyentes:
- Prescripción tributaria: 4 años desde la finalización del plazo de presentación de la declaración.
  Hacienda no puede reclamar deudas con más de 4 años de antigüedad (salvo interrupción).
- Comprobación e inspección: AEAT puede comprobar declaraciones dentro del período no prescrito.
- Infracciones y sanciones: leves (< 3.000€ o sin ocultación) 50%, graves 50-100%, muy graves 100-150%.
- Recargos por presentación fuera de plazo (sin requerimiento previo): 1% por mes hasta 12 meses,
  después 15% + intereses de demora (4,0625% en 2026).
- Derecho a aplazamiento/fraccionamiento de deudas tributarias: solicitar antes del vencimiento.
- Reducción por conformidad: 30% en actas de inspección si se acepta la propuesta.
- Reducción por pronto pago: 25% adicional sobre sanción reducida si se paga en plazo.
Fuente: BOE — https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186
Hacienda: https://www.hacienda.gob.es""",
        "keywords": ["LGT", "prescripción", "4 años", "inspección", "sanción", "recargo", "infracción", "aplazamiento", "ley tributaria", "hacienda"],
        "source": "BOE/Hacienda", "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186",
    },
    # ── ICAC — Contabilidad ────────────────────────────────────
    {
        "id": "icac_contabilidad",
        "text": """ICAC — Instituto de Contabilidad y Auditoría de Cuentas:
El ICAC es el organismo oficial que regula la contabilidad y auditoría en España. Depende del Ministerio de Hacienda.
Principales marcos contables en España:
- PGC 2007 (RD 1514/2007): para empresas en general.
- PGC PYMEs (RD 1515/2007): simplificado, para empresas con ≤2 de: activo ≤4M€, cifra negocios ≤8M€, ≤50 trabajadores.
- Microempresas: pueden usar criterios simplificados del PGC PYMEs.
- NIIF/IFRS: obligatorio para grupos cotizados.

Obligaciones contables:
- Llevar contabilidad ordenada (Código de Comercio art. 25): libro diario y libro de inventarios.
- Autónomos en estimación directa simplificada: libros registro de ingresos, gastos, bienes de inversión.
- Autónomos en módulos: solo libro registro de bienes de inversión.
- Sociedades mercantiles: contabilidad completa + depósito de cuentas en Registro Mercantil.
- Plazo depósito cuentas anuales: dentro de los 7 meses siguientes al cierre del ejercicio.

Resoluciones ICAC: interpretaciones sobre aplicación del PGC, con efecto orientativo.
Fuente ICAC: https://www.icac.gob.es
Normativas: https://www.icac.gob.es/contabilidad/normativas/nacionales""",
        "keywords": ["ICAC", "contabilidad", "PGC", "auditoría", "balance", "cuenta anual", "registro", "libro diario", "depósito", "microempresa"],
        "source": "ICAC", "url": "https://www.icac.gob.es/contabilidad/normativas/nacionales",
    },
    # ── SEPE — Desempleo y prestaciones ───────────────────────
    {
        "id": "sepe_prestaciones",
        "text": """SEPE — Servicio Público de Empleo Estatal:
El SEPE gestiona las prestaciones por desempleo y formación en España.
Prestación contributiva por desempleo ("paro"):
- Requisito: cotización mínima 360 días en los últimos 6 años.
- Duración: proporcional a días cotizados (de 2 meses por 360 días a 24 meses por 2.160+ días).
- Cuantía: 70% de la base reguladora los primeros 180 días, 50% a partir del día 181.
- Base reguladora: media de las bases de cotización por contingencias profesionales de los últimos 180 días.
- Tope máximo: entre 1,75 y 2,25 veces el IPREM según hijos a cargo.
- IPREM 2026: 600€/mes (verificar actualización anual).

Subsidio por desempleo: para quienes agotan la prestación contributiva o no la generaron.
Renta Activa de Inserción (RAI): colectivos en especial dificultad.
Cese de actividad autónomos: gestionado también a través del SEPE en coordinación con TGSS.

IMPORTANTE: Compatibilidad desempleo con trabajo a tiempo parcial o inicio de actividad como autónomo
tiene reglas específicas. Consultar en SEPE antes de iniciar cualquier actividad.
Fuente SEPE: https://www.sepe.es/HomeSepe/Prestaciones/que-prestaciones-hay/Prestacion-contributiva.html""",
        "keywords": ["SEPE", "paro", "desempleo", "prestación", "subsidio", "RAI", "baja", "contributiva", "días cotizados", "IPREM", "360 días"],
        "source": "SEPE", "url": "https://www.sepe.es/HomeSepe/Prestaciones/que-prestaciones-hay/Prestacion-contributiva.html",
    },
    # ── Ley de Autónomos ──────────────────────────────────────
    {
        "id": "ley_autonomos_estatuto",
        "text": """Ley del Estatuto del Trabajo Autónomo (Ley 20/2007):
El LETA es la norma básica que regula los derechos y obligaciones de los trabajadores autónomos en España.
Derechos fundamentales del autónomo según el LETA:
- Derecho a afiliarse y crear asociaciones de autónomos.
- Derecho a la formación profesional.
- Derecho a la conciliación familiar: tarifa plana mantenida en excedencias y permisos de maternidad/paternidad.
- Derecho a interrupción de actividad por IT, maternidad, paternidad, riesgo embarazo.
- TRADE (Trabajador Autónomo Económicamente Dependiente): autónomo que obtiene al menos 75% ingresos
  de un único cliente. Tiene derecho a 18 días hábiles de vacaciones, indemnización por extinción
  injustificada del contrato, y cobertura por accidente de trabajo desde el primer día.

Autónomo societario: socio que trabaja en su propia SL y cotiza en el RETA.
Familiar colaborador: cónyuge o familiar hasta 2º grado que trabaja en el negocio del autónomo.
Puede cotizar con bonificaciones (puede acceder a tarifa plana de 80€/mes).

Modificaciones recientes: Ley de Reformas Urgentes del Trabajo Autónomo (Ley 6/2017) introdujo:
cambios en altas y bajas (hasta 3 veces/año sin coste el mismo día del cambio de tramo),
deducción de gastos de suministros en vivienda habitual (30%), deducción de gastos de manutención.
Fuente BOE: https://www.boe.es/buscar/act.php?id=BOE-A-2007-13409""",
        "keywords": ["LETA", "estatuto autónomo", "TRADE", "familiar colaborador", "autónomo societario", "derechos", "ley autónomos", "20/2007", "6/2017"],
        "source": "BOE", "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2007-13409",
    },
    # ── Haciendas Forales ─────────────────────────────────────
    {
        "id": "haciendas_forales",
        "text": """Haciendas Forales — País Vasco y Navarra:
España tiene territorios con régimen fiscal especial: País Vasco (Álava, Gipuzkoa, Bizkaia) y Navarra.
Estos territorios recaudan sus propios impuestos mediante el Concierto Económico (PV) y el Convenio Económico (Navarra).
Diferencias fiscales principales respecto al régimen común:
- Gestionan y recaudan IRPF, IS, IVA y otros tributos de forma independiente.
- Tipos y deducciones pueden diferir: por ejemplo, IS en PV puede ser diferente al 25% general.
- Los autónomos y empresas con domicilio en estos territorios tributan ante las Haciendas Forales,
  no ante la AEAT estatal.
- Hacienda Foral de Álava: https://www.araba.eus/hacienda
- Hacienda Foral de Gipuzkoa: https://www.gipuzkoa.eus/hacienda
- Hacienda Foral de Bizkaia: https://www.bizkaia.eus/ogasuna
- Hacienda Foral de Navarra: https://www.hacienda.navarra.es
IMPORTANTE: Si el usuario opera en el País Vasco o Navarra, la normativa puede diferir significativamente.
Siempre indicar que consulten su Hacienda Foral correspondiente.""",
        "keywords": ["País Vasco", "Navarra", "foral", "concierto económico", "Gipuzkoa", "Bizkaia", "Álava", "hacienda foral", "régimen foral"],
        "source": "Haciendas Forales", "url": "https://www.hacienda.navarra.es",
    },
    {
        "id": "facturacion_requisitos",
        "text": """Facturación en España — Requisitos legales (RD 1619/2012):
Toda factura debe incluir obligatoriamente:
1. Número y serie (correlativa).
2. Fecha de expedición.
3. Nombre y apellidos/razón social del emisor.
4. NIF del emisor.
5. Datos del destinatario (si es empresa o pide factura).
6. Descripción de los bienes o servicios.
7. Base imponible.
8. Tipo impositivo de IVA aplicado.
9. Cuota de IVA.
10. Total de la factura.
Factura simplificada (ticket): para importes < 400€ IVA incluido o comercio al por menor.
Factura electrónica: legalmente equivalente a papel si garantiza autenticidad e integridad.
VERIFACTU obligatorio: empresas IS desde 1/1/2027, autónomos IRPF desde 1/7/2027.""",
        "keywords": ["factura", "requisito", "obligatorio", "NIF", "IVA", "número", "serie", "emisor", "receptor", "simplificada", "electrónica"],
        "source": "AEAT/BOE", "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2012-14696",
    },
]

# ── BM25-like scoring (lightweight keyword search) ────────────

def _tokenize(text: str) -> list[str]:
    """Simple Spanish tokenizer — lowercase, remove accents, split words."""
    text = text.lower()
    # Normalize accents
    replacements = {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ü":"u","ñ":"n"}
    for a, b in replacements.items():
        text = text.replace(a, b)
    return re.findall(r'\b\w{2,}\b', text)


def _score_document(query_tokens: list[str], doc: dict) -> float:
    """Score document relevance using keyword + BM25-inspired scoring."""
    score = 0.0
    doc_text = (doc["text"] + " " + " ".join(doc.get("keywords", []))).lower()
    doc_tokens = _tokenize(doc_text)

    # Token frequency in document
    token_freq = {}
    for t in doc_tokens:
        token_freq[t] = token_freq.get(t, 0) + 1

    doc_len = len(doc_tokens)
    avg_len = 300  # approximate average doc length

    for qt in query_tokens:
        # BM25 parameters
        k1, b = 1.5, 0.75
        tf = token_freq.get(qt, 0)
        if tf > 0:
            # BM25 term score
            tf_score = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_len))
            score += tf_score

        # Bonus for keyword match (pre-defined important terms)
        if qt in [k.lower() for k in doc.get("keywords", [])]:
            score += 2.0

    # Normalize by query length
    if query_tokens:
        score /= len(query_tokens)

    return score


def search_knowledge_base(query: str, n_results: int = 3) -> list[dict]:
    """Search in-memory knowledge base using BM25-like scoring."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return FISCAL_KNOWLEDGE_BASE[:n_results]

    scored = []
    for doc in FISCAL_KNOWLEDGE_BASE:
        score = _score_document(query_tokens, doc)
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:n_results]]


# ══════════════════════════════════════════════════════════════
#  FUENTES WEB EN TIEMPO REAL
# ══════════════════════════════════════════════════════════════

async def search_boe_realtime(query: str, max_results: int = 2) -> list[dict]:
    """Search BOE API for recent legislation."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://www.boe.es/api/api.php",
                params={"op": "search", "query": query, "lang": "es", "numres": max_results, "sort": "date"}
            )
            if r.status_code == 200:
                data = r.json()
                items = data.get("response", {}).get("results", {}).get("result", [])
                if isinstance(items, dict): items = [items]
                results = []
                for item in items[:max_results]:
                    results.append({
                        "text": f"BOE {item.get('fecha_publicacion','')}: {item.get('titulo','')}",
                        "source": "BOE",
                        "url": f"https://www.boe.es/buscar/doc.php?id={item.get('identificador','')}",
                    })
                return results
    except Exception:
        pass
    return []


def get_aeat_references(query: str) -> list[dict]:
    """Return relevant official references based on query keywords."""
    q = query.lower()
    refs = []

    # AEAT pages
    aeat_pages = [
        (["iva","303","390","repercutido","soportado","factura"], "AEAT — IVA",
         "https://sede.agenciatributaria.gob.es/Sede/iva.html"),
        (["irpf","renta","100","130","retención","tramo","estimación directa"], "AEAT — IRPF",
         "https://sede.agenciatributaria.gob.es/Sede/irpf.html"),
        (["sociedad","IS","200","202","empresa","25%"], "AEAT — Impuesto Sociedades",
         "https://sede.agenciatributaria.gob.es/Sede/impuesto-sociedades.html"),
        (["plazo","calendario","fecha","modelo","presentar","trimestral"], "AEAT — Calendario contribuyente",
         "https://sede.agenciatributaria.gob.es/Sede/Ayuda/calendario-contribuyente.html"),
        (["deducible","gasto","deducir","gastos"], "AEAT — Deducciones y gastos",
         "https://sede.agenciatributaria.gob.es/Sede/irpf/deducciones-gastos.html"),
        (["autónomo","036","alta","baja","empresario"], "AEAT — Autónomos",
         "https://sede.agenciatributaria.gob.es/Sede/autonomos.html"),
    ]
    for keywords, title, url in aeat_pages:
        if any(k in q for k in keywords):
            refs.append({"source": "AEAT", "title": title, "url": url})

    # DGT — consultas vinculantes
    if any(k in q for k in ["consulta","vinculante","dgt","criterio","interpretación","hacienda dice"]):
        refs.append({"source": "DGT", "title": "DGT — Consultas vinculantes",
                     "url": "https://www.hacienda.gob.es/es-ES/Normativa%20y%20doctrina/Doctrina/paginas/consultasdgt.aspx"})

    # LGT — prescripción, sanciones
    if any(k in q for k in ["prescripción","sanción","infracción","recargo","aplazamiento","4 años","inspección"]):
        refs.append({"source": "BOE/Hacienda", "title": "Ley General Tributaria (LGT)",
                     "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186"})

    # ICAC — contabilidad
    if any(k in q for k in ["contabilidad","icac","pgc","balance","cuentas anuales","registro mercantil","auditoría"]):
        refs.append({"source": "ICAC", "title": "ICAC — Normativas contables",
                     "url": "https://www.icac.gob.es/contabilidad/normativas/nacionales"})

    # SEPE — desempleo
    if any(k in q for k in ["paro","desempleo","sepe","prestación","subsidio","contributiva","inem"]):
        refs.append({"source": "SEPE", "title": "SEPE — Prestaciones por desempleo",
                     "url": "https://www.sepe.es/HomeSepe/Prestaciones/que-prestaciones-hay/Prestacion-contributiva.html"})

    # LGSS
    if any(k in q for k in ["lgss","ley general seguridad social","cese actividad","reta","prestación autónomo","jubilación autónomo"]):
        refs.append({"source": "LGSS/TGSS", "title": "Ley General Seguridad Social",
                     "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11724"})

    # Ley Autónomos LETA
    if any(k in q for k in ["letra","trade","familiar colaborador","estatuto autónomo","ley autónomos"]):
        refs.append({"source": "BOE", "title": "Estatuto Trabajador Autónomo (LETA)",
                     "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2007-13409"})

    # Haciendas Forales
    if any(k in q for k in ["país vasco","navarra","foral","bizkaia","gipuzkoa","álava","concierto"]):
        refs.append({"source": "Haciendas Forales", "title": "Régimen Foral — País Vasco/Navarra",
                     "url": "https://www.hacienda.navarra.es"})

    if not refs:
        refs.append({"source": "AEAT", "title": "AEAT — Sede electrónica",
                     "url": "https://sede.agenciatributaria.gob.es"})
    return refs[:3]  # Return up to 3 references


def get_tgss_references(query: str) -> list[dict]:
    """Return relevant TGSS page references."""
    q = query.lower()
    if any(k in q for k in ["autónomo","cuota","cotiz","RETA","tarifa plana","alta","baja","inem"]):
        return [{"source": "TGSS", "title": "TGSS — Autónomos",
                 "url": "https://sede.seg-social.gob.es/wps/portal/sede/sede/Trabajadores/TrabajoAutonomo"}]
    return []


# ══════════════════════════════════════════════════════════════
#  MOTOR RAG PRINCIPAL
# ══════════════════════════════════════════════════════════════

async def retrieve_context(query: str, n_results: int = 3) -> list[dict]:
    """
    Retrieve relevant context combining:
    1. In-memory BM25 knowledge base (instant, 0MB extra RAM)
    2. BOE real-time API (optional, graceful fallback)
    3. AEAT/TGSS reference links
    """
    all_context = []

    # 1. Knowledge base search (instant)
    kb_docs = search_knowledge_base(query, n_results)
    for doc in kb_docs:
        all_context.append({
            "text": doc["text"],
            "source": doc["source"],
            "url": doc.get("url", ""),
            "relevance": 1.0,
        })

    # 2. BOE real-time (non-blocking, best-effort)
    try:
        boe_results = await search_boe_realtime(query, max_results=1)
        all_context.extend([{**r, "relevance": 0.6} for r in boe_results])
    except Exception:
        pass

    # 3. AEAT references
    for ref in get_aeat_references(query):
        # Only add if not already covered
        if not any(ref["url"] in c.get("url","") for c in all_context):
            all_context.append({"text": ref["title"], "source": ref["source"],
                               "url": ref["url"], "relevance": 0.5})

    # 4. TGSS references
    for ref in get_tgss_references(query):
        all_context.append({"text": ref["title"], "source": ref["source"],
                            "url": ref["url"], "relevance": 0.5})

    return all_context[:5]


def format_context_for_prompt(context_docs: list[dict]) -> tuple[str, list[dict]]:
    """Format docs into prompt string + references."""
    if not context_docs:
        return "", []
    parts, references = [], []
    for i, doc in enumerate(context_docs, 1):
        parts.append(f"[Fuente {i} — {doc['source']}]\n{doc['text']}")
        if doc.get("url"):
            references.append({"num": i, "source": doc["source"], "url": doc["url"]})
    return "\n\n".join(parts), references


async def initialize_knowledge_base():
    """No-op — knowledge base is in-memory, always ready."""
    print(f"[RAG] Base de conocimiento cargada: {len(FISCAL_KNOWLEDGE_BASE)} documentos (BM25 en memoria)")
