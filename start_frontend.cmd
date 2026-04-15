@echo off
setlocal

set "ROOT=G:\RGSX\CenterPoint"
set "NPM=G:\Program Files\nodejs\npm.cmd"
set "FRONTEND=frontend"
set "HOST=127.0.0.1"
set "PORT=5173"

cd /d "%ROOT%\%FRONTEND%"

echo ====================================================
echo   CenterPoint Frontend Start
echo ====================================================
echo.
echo Frontend dev server: http://%HOST%:%PORT%
echo This window will stay open while Vite is running.
echo Press Ctrl+C to stop the frontend server.
echo.

"%NPM%" run dev -- --host %HOST% --port %PORT%

echo.
echo Frontend server stopped.
pause
