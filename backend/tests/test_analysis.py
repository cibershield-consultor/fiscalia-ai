"""
Tests unitarios para el motor de cálculo fiscal de Fiscalía IA.
Ejecutar: pytest tests/ -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.analysis_service import (
    calcular_irpf,
    calcular_tipo_efectivo,
    calcular_iva,
    calcular_cuota_autonomo,
    calcular_pago_fraccionado_130,
    generar_resumen_trimestral,
    get_trimestre_actual,
)


# ── IRPF ────────────────────────────────────────────────────

class TestIRPF:

    def test_base_cero(self):
        assert calcular_irpf(0) == 0.0

    def test_base_negativa(self):
        assert calcular_irpf(-1000) == 0.0

    def test_primer_tramo(self):
        # 10.000 × 0.19 = 1.900
        assert calcular_irpf(10_000) == pytest.approx(1_900.0)

    def test_dos_tramos(self):
        # 12.450 × 0.19 + 2.550 × 0.24
        esperado = 12_450 * 0.19 + 2_550 * 0.24
        assert calcular_irpf(15_000) == pytest.approx(esperado, rel=1e-3)

    def test_base_40000(self):
        # Tramos: 12450×0.19 + 7750×0.24 + 15000×0.30 + 4800×0.37
        esperado = 12_450*0.19 + 7_750*0.24 + 15_000*0.30 + 4_800*0.37
        assert calcular_irpf(40_000) == pytest.approx(esperado, rel=1e-3)

    def test_tipo_efectivo_positivo(self):
        tipo = calcular_tipo_efectivo(40_000)
        assert 0 < tipo < 40  # tipo efectivo siempre menor que marginal

    def test_tipo_efectivo_cero(self):
        assert calcular_tipo_efectivo(0) == 0.0


# ── IVA ─────────────────────────────────────────────────────

class TestIVA:

    def test_iva_general(self):
        r = calcular_iva(1_000, "general")
        assert r["cuota"] == 210.0
        assert r["total"] == 1_210.0

    def test_iva_reducido(self):
        r = calcular_iva(1_000, "reducido")
        assert r["cuota"] == 100.0

    def test_iva_superreducido(self):
        r = calcular_iva(1_000, "superreducido")
        assert r["cuota"] == 40.0

    def test_iva_exento(self):
        r = calcular_iva(1_000, "exento")
        assert r["cuota"] == 0.0
        assert r["total"] == 1_000.0

    def test_iva_tipo_invalido_usa_general(self):
        r = calcular_iva(1_000, "desconocido")
        assert r["cuota"] == 210.0


# ── Cuota Autónomo ───────────────────────────────────────────

class TestCuotaAutonomo:

    def test_ingresos_muy_bajos(self):
        cuota = calcular_cuota_autonomo(500)
        assert cuota == 200  # tramo mínimo

    def test_ingresos_altos(self):
        cuota = calcular_cuota_autonomo(5_000)
        assert cuota == 530

    def test_ingresos_muy_altos(self):
        cuota = calcular_cuota_autonomo(10_000)
        assert cuota == 590  # máximo


# ── Modelo 130 ───────────────────────────────────────────────

class TestModelo130:

    def test_sin_retenciones(self):
        pago = calcular_pago_fraccionado_130(10_000, 2_000, 0)
        # (10000 - 2000) × 0.20 = 1600
        assert pago == pytest.approx(1_600.0)

    def test_con_retenciones(self):
        pago = calcular_pago_fraccionado_130(10_000, 2_000, 1_200)
        # 1600 - 1200 = 400
        assert pago == pytest.approx(400.0)

    def test_resultado_negativo_retorna_cero(self):
        pago = calcular_pago_fraccionado_130(5_000, 1_000, 2_000)
        # 800 - 2000 = -1200 → 0
        assert pago == 0.0

    def test_sin_ingresos(self):
        pago = calcular_pago_fraccionado_130(0, 0, 0)
        assert pago == 0.0


# ── Resumen Trimestral ───────────────────────────────────────

class TestResumenTrimestral:

    def test_resumen_completo(self):
        resumen = generar_resumen_trimestral(
            trimestre=2,
            año=2024,
            ingresos=15_000,
            gastos=5_000,
            gastos_deducibles=4_000,
            retenciones_soportadas=2_250,
        )
        assert resumen.trimestre == 2
        assert resumen.beneficio == 10_000.0
        assert resumen.margen_pct == pytest.approx(66.67, rel=1e-2)
        assert resumen.iva_repercutido == pytest.approx(3_150.0)
        assert resumen.modelo_130 == 0.0  # retenciones superan el 20%

    def test_alerta_resultado_negativo(self):
        resumen = generar_resumen_trimestral(
            trimestre=1,
            año=2024,
            ingresos=1_000,
            gastos=5_000,
            gastos_deducibles=5_000,
        )
        assert resumen.alerta is not None
        assert "negativo" in resumen.alerta.lower()

    def test_plazo_declaracion_presente(self):
        resumen = generar_resumen_trimestral(1, 2024, 10_000, 2_000, 2_000)
        assert "303" in resumen.plazo_declaracion
        assert "130" in resumen.plazo_declaracion


# ── Trimestre Actual ─────────────────────────────────────────

class TestTrimestre:

    def test_trimestre_valido(self):
        t = get_trimestre_actual()
        assert t in [1, 2, 3, 4]
