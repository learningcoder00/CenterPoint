@echo off
setlocal

set "ROOT=G:\RGSX\CenterPoint"
set "JAVA=D:\Program Files\Java\jdk-22\bin\java.exe"
set "CONFIG=configs\nusc\voxelnet\nusc_centerpoint_voxelnet_0075voxel_fix_bn_z.py"
set "CHECKPOINT=work_dirs\epoch_20.pth"
set "JAR=backend\target\centerpoint-viz-1.0.0.jar"
set "PORT=8081"

cd /d "%ROOT%"

echo ====================================================
echo   CenterPoint Backend Start
echo ====================================================

echo Open http://127.0.0.1:%PORT%/clips
echo Backend logs will stay in the new terminal window.

if not exist "%JAR%" (
  echo [ERROR] Missing jar: %JAR%
  pause
  exit /b 1
)

start "CenterPoint Backend" cmd /k ""%JAVA%" -jar "%ROOT%\%JAR%" --app.project-root="%ROOT%" --app.config="%CONFIG%" --app.checkpoint="%CHECKPOINT%" --server.port=%PORT%"

echo Backend window launched and will remain open.
echo If you also need a frontend dev server, run start_frontend.cmd
pause
