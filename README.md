# ⚖️ Fiscalía IA — Asesor Fiscal para Autónomos en España

> Plataforma completa de asesoramiento fiscal con IA para autónomos españoles.
> Chat inteligente · Gestión de facturas · Dashboard financiero · Análisis fiscal automático.

---

## ⚡ Instalación con un solo comando

### Requisito único: Docker Desktop

Descárgalo aquí → https://www.docker.com/get-started
- **Windows/macOS**: Docker Desktop (instalador gráfico, 2 clics)
- **Ubuntu/Debian**: `sudo apt install docker.io docker-compose-plugin`

Una vez instalado Docker, **no necesitas Python, pip ni nada más.**

---

### macOS / Linux

```bash
# 1. Dar permisos al script (solo la primera vez)
chmod +x start.sh

# 2. Ejecutar
./start.sh
```

### Windows

```
Doble clic en start.bat
(o clic derecho → "Ejecutar como administrador" si hay problemas)
```

El script automáticamente:
1. ✅ Comprueba que Docker está instalado
2. ✅ Te pide tu API key de OpenAI y la guarda
3. ✅ Descarga Python e instala todas las dependencias
4. ✅ Arranca backend + frontend
5. ✅ Abre el navegador en http://localhost:3000

---

## 🌐 URLs una vez arrancado

| Servicio | URL |
|---------|-----|
| **Aplicación web** | http://localhost:3000 |
| **API + Swagger docs** | http://localhost:8000/docs |
| **Backend directo** | http://localhost:8000 |

---

## 🔑 API Key de OpenAI

Necesitas una cuenta en OpenAI y crear una API key:

1. Ve a https://platform.openai.com/api-keys
2. Clic en "Create new secret key"
3. Cópiala (empieza por `sk-...`)
4. El script `start.sh` te la pedirá automáticamente

También puedes editarla manualmente en `backend/.env`:
```env
OPENAI_API_KEY=sk-tu-clave-aqui
```

Coste estimado: **~$3-8/mes** con uso normal (100 consultas/día con GPT-4.1 mini).

---

## 🔧 Comandos útiles

```bash
# Arrancar
./start.sh

# Parar (conserva los datos)
./stop.sh
# o: docker compose down

# Ver logs en tiempo real
docker compose logs -f

# Ver logs solo del backend
docker compose logs -f backend

# Reiniciar solo el backend (tras cambios en el código)
docker compose restart backend

# Reconstruir tras cambios en requirements.txt
docker compose up --build -d

# Borrar todo (¡incluidos los datos!)
docker compose down -v
```

---

## 🗂 Estructura del Proyecto

```
fiscalia/
├── start.sh / start.bat       ← Instalación con un clic
├── stop.sh                    ← Parar la aplicación
├── docker-compose.yml         ← Orquestación de servicios
├── nginx.conf                 ← Proxy frontend → backend
├── backend/
│   ├── Dockerfile             ← Imagen Python + dependencias
│   ├── requirements.txt       ← Dependencias Python
│   ├── .env.example           ← Plantilla de configuración
│   └── app/
│       ├── main.py            ← FastAPI app
│       ├── core/              ← Config, BD, seguridad
│       ├── models/            ← Tablas de base de datos
│       ├── routers/           ← Endpoints API
│       └── services/          ← IA, cálculos fiscales
└── frontend/
    └── index.html             ← SPA completa
```

---

## 🏗 Arquitectura Docker

```
Usuario (navegador)
        │
        ▼
  nginx :3000          ← sirve index.html
        │
        │  /api/*  →  proxy_pass
        ▼
  FastAPI :8000        ← Python + lógica IA
        │
        ├── SQLite (fiscalia.db)   ← base de datos
        ├── uploads/               ← facturas subidas
        └── OpenAI API             ← chat + clasificación
```

Los datos (base de datos y facturas) se guardan en **volúmenes Docker**,
por lo que persisten aunque pares o reinicies los contenedores.

---

## 🧠 Funcionalidades

### Chat IA Fiscal
- Asesor especializado en normativa española 2024-2025
- IVA, IRPF, gastos deducibles, modelos tributarios
- Historial de conversaciones persistente
- Preguntas rápidas predefinidas

### Dashboard Financiero
- KPIs: ingresos, gastos, beneficio, IVA a pagar
- Gráfico de barras mensual
- Resumen fiscal automático (Modelo 303, 130)
- Insights generados por IA

### Gestión de Facturas
- CRUD completo de facturas
- Clasificación automática por IA (categoría + deducibilidad)
- Subida de archivos PDF/imagen
- Filtros por tipo y fecha

### Calculadora Fiscal
- Tramos IRPF 2024 (19% al 47%)
- Cuotas autónomo por tramos de ingresos
- Cálculo Modelo 130 (pago fraccionado)
- Calendario fiscal con plazos

---

## 🌍 Publicar en Internet (opcional)

Para que otros accedan desde fuera de tu ordenador:

### Opción A — Railway (gratis, más fácil)
```bash
# Instalar Railway CLI
npm install -g @railway/cli
railway login
railway up
```

### Opción B — VPS (DigitalOcean, Hetzner ~5€/mes)
```bash
# En el servidor
git clone tu-repo
cd fiscalia
./start.sh
```

### Opción C — Render.com (gratis con limitaciones)
Conecta tu repositorio GitHub y despliega automáticamente.

---

## ⚠️ Aviso Legal

Esta herramienta es de apoyo informativo y no sustituye el asesoramiento
de un gestor o asesor fiscal colegiado. Para decisiones fiscales importantes,
consulta siempre con un profesional habilitado.

---

*Fiscalía IA · 2025 · Hecho para autónomos españoles*
