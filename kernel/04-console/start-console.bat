@echo off
rem ============================================================================
rem  Hubcore Console - double-click to start.
rem  Starts the local service and opens the page in your browser.
rem  No token to copy. Closing this window stops the service.
rem ============================================================================
setlocal
cd /d "%~dp0"

rem --- find a Python: py launcher first, then python / python3 ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY where python3 >nul 2>nul && set "PY=python3"
if not defined PY (
    echo.
    echo   Python not found.
    echo   Install Python 3.10+ with "Add to PATH" checked, then double-click again.
    echo.
    pause
    exit /b 1
)

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

title Hubcore Console (closing this window stops the service)

echo.
echo   Starting console, your browser will open the page...
echo   Close this window to stop the console.
echo.

rem -u = unbuffered, so you see the packager output live
%PY% -u run.py %*
set "RC=%ERRORLEVEL%"

echo.
if not "%RC%"=="0" (
    echo   Console exited with code %RC%.
    echo   The lines above say why. Press any key to close.
    pause >nul
)
endlocal
