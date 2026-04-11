@echo off
setlocal

set "ROOT=G:\RGSX\CenterPoint"
set "NPM=G:\Program Files\nodejs\npm.cmd"
set "FRONTEND=tools\frontend-vue"

cd /d "%ROOT%\%FRONTEND%"

echo ====================================================
echo   CenterPoint Frontend Build
echo ====================================================

"%NPM%" install
if errorlevel 1 goto :fail

"%NPM%" run build
if errorlevel 1 goto :fail

echo.
echo Frontend build done.
pause
exit /b 0

:fail
echo.
echo Frontend build failed.
pause
exit /b 1
