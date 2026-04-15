@echo off
setlocal

set "ROOT=G:\RGSX\CenterPoint"
set "NPM=G:\Program Files\nodejs\npm.cmd"
set "FRONTEND=frontend"

cd /d "%ROOT%\%FRONTEND%"
if errorlevel 1 goto :cd_fail

echo ====================================================
echo   CenterPoint Frontend Build
echo ====================================================
echo Project: %ROOT%\%FRONTEND%
echo.
echo [1/2] Installing frontend dependencies...

call "%NPM%" install
if errorlevel 1 goto :fail

echo.
echo [2/2] Building frontend dist...
call "%NPM%" run build
if errorlevel 1 goto :fail

echo.
echo ====================================================
echo Frontend build finished successfully.
echo You can now refresh http://127.0.0.1:8081/clips to check the latest UI.
echo Press any key to close this window.
echo ====================================================
pause
exit /b 0

:cd_fail
echo.
echo [ERROR] Failed to enter frontend directory:
echo %ROOT%\%FRONTEND%
echo Press any key to close this window.
pause
exit /b 1

:fail
echo.
echo ====================================================
echo Frontend build failed.
echo Please scroll up to check the error details above.
echo Press any key to close this window.
echo ====================================================
pause
exit /b 1
