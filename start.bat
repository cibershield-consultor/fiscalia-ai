@echo off
REM ============================================================
REM  Fiscalía IA — Script de instalación y arranque
REM  Windows — Ejecutar como Administrador si hay problemas
REM ============================================================

echo.
echo  ================================================
echo   Fiscalia IA — Instalacion automatica
echo  ================================================
echo.

REM ── 1. Comprobar Docker ──────────────────────────────────
echo [1/4] Comprobando Docker...
docker --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo  ERROR: Docker no esta instalado.
    echo  Descargalo desde: https://www.docker.com/get-started
    echo  Instala Docker Desktop para Windows.
    echo.
    pause
    exit /b 1
)
echo  OK: Docker disponible.

REM ── 2. Crear .env si no existe ───────────────────────────
IF NOT EXIST "backend\.env" (
    echo.
    echo [2/4] Configurando variables de entorno...
    copy "backend\.env.example" "backend\.env" >nul

    echo.
    echo  =====================================================
    echo   IMPORTANTE: Necesitas una API key de OpenAI
    echo   Obtenla en: https://platform.openai.com/api-keys
    echo  =====================================================
    echo.
    set /p API_KEY="Pega tu OpenAI API Key (sk-...): "

    IF NOT "!API_KEY!"=="" (
        powershell -Command "(Get-Content backend\.env) -replace 'OPENAI_API_KEY=.*', 'OPENAI_API_KEY=!API_KEY!' | Set-Content backend\.env"
        echo  OK: API key guardada.
    ) ELSE (
        echo  AVISO: No introduciste API key. Edita backend\.env manualmente.
    )

    REM Generate random secret key
    FOR /F %%i IN ('powershell -Command "[System.Convert]::ToHexString([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))"') DO SET SECRET=%%i
    powershell -Command "(Get-Content backend\.env) -replace 'SECRET_KEY=.*', 'SECRET_KEY=!SECRET!' | Set-Content backend\.env"
) ELSE (
    echo [2/4] backend\.env ya existe. OK.
)

REM ── 3. Arrancar Docker Compose ───────────────────────────
echo.
echo [3/4] Construyendo e iniciando contenedores...
echo  (La primera vez puede tardar 1-2 minutos)
echo.

docker compose up --build -d
IF %ERRORLEVEL% NEQ 0 (
    docker-compose up --build -d
)

REM ── 4. Esperar y abrir ───────────────────────────────────
echo.
echo [4/4] Esperando a que el servidor arranque...
timeout /t 8 /nobreak >nul

echo.
echo  =====================================================
echo   Fiscalia IA esta en marcha!
echo.
echo   Aplicacion web:  http://localhost:3000
echo   API (Swagger):   http://localhost:8000/docs
echo.
echo   Para parar:      docker compose down
echo   Para ver logs:   docker compose logs -f
echo  =====================================================
echo.

start http://localhost:3000
pause
