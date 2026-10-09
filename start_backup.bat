
@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo       BACKUP SERWEROW PUMA I EDICTA
echo ========================================
echo.

if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
) else if exist "%~dp0venv\Scripts\python.exe" (
    "%~dp0venv\Scripts\python.exe" "%~dp0main.py"
) else (
    py "%~dp0main.py"
)

set "RC=%ERRORLEVEL%"

echo.
echo ========================================
if "%RC%"=="0" (
    echo PIPELINE ZAKONCZONY SUKCESEM
) else (
    echo BLAD: PIPELINE ZAKONCZYL SIE KODEM %RC%
)
echo ========================================
echo.
pause

exit /b %RC%