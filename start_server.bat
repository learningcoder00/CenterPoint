@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================================
REM CenterPoint visualization server launcher for Windows CMD (no WSL/Bash).
REM Examples:
REM   start_server.bat
REM   start_server.bat --port 8082
REM   start_server.bat --config configs\baseline.py --checkpoint work_dirs\epoch_20.pth
REM
REM The launcher auto-activates the `centerpoint` conda env (override with
REM   set CENTERPOINT_CONDA_ENV=other-env-name
REM or skip with:
REM   set CENTERPOINT_SKIP_ACTIVATE=1
REM ). If activation fails it falls back to CENTERPOINT_PYTHON / PATH lookup.
REM ============================================================================

cd /d "%~dp0"
if errorlevel 1 exit /b 1
if not exist work_dirs mkdir work_dirs

set "CONFIG="
set "CHECKPOINT="
set "PORT=8081"
set "HOST=0.0.0.0"

:parse_args
if "%~1"=="" goto args_done
if /i "%~1"=="-h" goto show_help
if /i "%~1"=="--help" goto show_help
if /i "%~1"=="--config" (
  set "CONFIG=%~2"
  shift & shift
  goto parse_args
)
if /i "%~1"=="--checkpoint" (
  set "CHECKPOINT=%~2"
  shift & shift
  goto parse_args
)
if /i "%~1"=="--port" (
  set "PORT=%~2"
  shift & shift
  goto parse_args
)
if /i "%~1"=="--host" (
  set "HOST=%~2"
  shift & shift
  goto parse_args
)
echo Unknown option: %~1
exit /b 1

:show_help
echo Usage: %~nx0 [--config path] [--checkpoint path] [--port N] [--host addr]
exit /b 0

:args_done

echo =====================================================
echo    CenterPoint Clip Visualization Server ^(CMD^)
echo =====================================================

echo.
echo [0/5] Activating conda env...
call :activate_conda

echo.
echo [1/5] Checking dependencies...

set "PYTHON_BIN="
call :pick_python
if not defined PYTHON_BIN (
  echo [ERROR] No Python with torch and cv2 ^(opencv^).
  echo   Run: conda activate centerpoint
  echo   Or:  set CENTERPOINT_PYTHON=C:\path\to\centerpoint\python.exe
  exit /b 1
)
echo   OK Python: !PYTHON_BIN!
for /f "delims=" %%V in ('"!PYTHON_BIN!" -c "import torch; print(torch.__version__)" 2^>nul') do echo   OK torch %%V
for /f "delims=" %%V in ('"!PYTHON_BIN!" -c "import cv2; print(cv2.__version__)" 2^>nul') do echo   OK cv2 %%V

where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo [ERROR] ffmpeg not found. Install ffmpeg and add to PATH.
  exit /b 1
)

where java >nul 2>&1
if errorlevel 1 (
  echo [ERROR] java not found. Install JDK 17+ and add to PATH.
  exit /b 1
)

where mvn >nul 2>&1
if errorlevel 1 (
  echo [ERROR] mvn not found. Install Maven and add to PATH.
  exit /b 1
)

echo   Building backend JAR...
pushd backend
call mvn package -DskipTests -q
if errorlevel 1 (
  popd
  echo [ERROR] mvn package failed.
  exit /b 1
)
popd
set "JAR=%CD%\backend\target\centerpoint-viz-1.0.0.jar"
if not exist "!JAR!" (
  echo [ERROR] JAR missing: !JAR!
  exit /b 1
)

echo.
echo [2/5] Building frontend...
where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] node not found.
  exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm not found.
  exit /b 1
)
if not exist "%CD%\frontend\package.json" (
  echo [ERROR] frontend\package.json missing.
  exit /b 1
)
pushd frontend
if not exist node_modules (
  echo   npm install ^(first run^)...
  call npm install
  if errorlevel 1 (
    popd
    exit /b 1
  )
)
call npm run build
if errorlevel 1 (
  popd
  exit /b 1
)
popd

echo.
echo [3/5] Checking project files...

REM Skip auto-generation if any clips_meta*.json exists (e.g. mini train/val or scheme B).
dir /b "clip_preview\clips_meta*.json" >nul 2>&1
if not errorlevel 1 goto skip_clip_meta_generate

REM Bootstrap only when clip_preview has no meta JSON yet
if exist "data\nuScenes\infos_val_10sweeps_withvelo_filter_True.pkl" (
  echo   Generating clip_preview\clips_meta.json ...
  set "PYTHONPATH=%CD%"
  "!PYTHON_BIN!" tools\generate_clip_preview.py
  if errorlevel 1 exit /b 1
  goto skip_clip_meta_generate
)
if exist "data\nuscenes_mini\infos_val_10sweeps_withvelo_filter_True.pkl" (
  echo   Generating clip_preview\clips_meta_mini_val.json ^(nuScenes mini^)...
  set "PYTHONPATH=%CD%"
  "!PYTHON_BIN!" tools\generate_clip_preview.py --infos data/nuscenes_mini/infos_val_10sweeps_withvelo_filter_True.pkl --meta-filename clips_meta_mini_val.json
  if errorlevel 1 exit /b 1
  goto skip_clip_meta_generate
)
echo [ERROR] No clip_preview\clips_meta*.json and no known infos .pkl under data\nuScenes or data\nuscenes_mini.
echo   Generate manually, e.g.:
echo   python tools/generate_clip_preview.py --infos path\to\infos.pkl --meta-filename clips_meta_my.json
exit /b 1

:skip_clip_meta_generate

echo.
echo [4/5] Checking port !PORT!...
call :port_busy !PORT!
if errorlevel 1 (
  echo   Port !PORT! busy, trying next...
  set /a PORT+=1
  call :port_busy !PORT!
  if errorlevel 1 (
    echo [ERROR] Ports busy. Use --port
    exit /b 1
  )
)

echo.
echo [5/5] Starting server...
echo   http://127.0.0.1:!PORT!
echo.

set "PYTHONPATH=%CD%;%PYTHONPATH%"
java -jar "!JAR!" ^
  --app.config="!CONFIG!" ^
  --app.checkpoint="!CHECKPOINT!" ^
  --app.python-executable="!PYTHON_BIN!" ^
  --app.project-root="%CD%" ^
  --server.address=!HOST! ^
  --server.port=!PORT!

exit /b %errorlevel%

REM ---------------------------------------------------------------------------
REM Activate conda env `centerpoint` (override via CENTERPOINT_CONDA_ENV).
REM Non-fatal: prints a warning on failure and lets :pick_python try fallbacks.
:activate_conda
if /i "%CENTERPOINT_SKIP_ACTIVATE%"=="1" (
  echo   Skipping conda activate ^(CENTERPOINT_SKIP_ACTIVATE=1^).
  exit /b 0
)
if not defined CENTERPOINT_CONDA_ENV set "CENTERPOINT_CONDA_ENV=centerpoint"

if /i "%CONDA_DEFAULT_ENV%"=="!CENTERPOINT_CONDA_ENV!" (
  echo   conda env "!CENTERPOINT_CONDA_ENV!" already active.
  exit /b 0
)

set "CONDA_ROOT="
if defined CONDA_EXE (
  for %%F in ("!CONDA_EXE!") do set "_CONDA_BIN_DIR=%%~dpF"
  if defined _CONDA_BIN_DIR (
    set "_CONDA_BIN_DIR=!_CONDA_BIN_DIR:~0,-1!"
    for %%G in ("!_CONDA_BIN_DIR!") do set "CONDA_ROOT=%%~dpG"
    if defined CONDA_ROOT set "CONDA_ROOT=!CONDA_ROOT:~0,-1!"
  )
  set "_CONDA_BIN_DIR="
)
if not defined CONDA_ROOT (
  for %%P in (
    "%USERPROFILE%\miniconda3"
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\miniforge3"
    "%USERPROFILE%\mambaforge"
    "%USERPROFILE%\AppData\Local\miniconda3"
    "%USERPROFILE%\AppData\Local\anaconda3"
    "C:\ProgramData\miniconda3"
    "C:\ProgramData\anaconda3"
  ) do (
    if exist "%%~P\Scripts\activate.bat" (
      if not defined CONDA_ROOT set "CONDA_ROOT=%%~P"
    )
  )
)

if not defined CONDA_ROOT (
  echo   [WARN] conda installation not found in standard locations.
  echo          Falling back to CENTERPOINT_PYTHON / PATH lookup.
  exit /b 0
)
if not exist "!CONDA_ROOT!\envs\!CENTERPOINT_CONDA_ENV!" (
  echo   [WARN] conda env "!CENTERPOINT_CONDA_ENV!" not found under "!CONDA_ROOT!\envs".
  echo          Create it with: conda create -n !CENTERPOINT_CONDA_ENV! python=3.9
  echo          Falling back to CENTERPOINT_PYTHON / PATH lookup.
  exit /b 0
)

echo   Activating "!CENTERPOINT_CONDA_ENV!" from "!CONDA_ROOT!"...
call "!CONDA_ROOT!\Scripts\activate.bat" "!CENTERPOINT_CONDA_ENV!"
if errorlevel 1 (
  echo   [WARN] conda activate "!CENTERPOINT_CONDA_ENV!" failed; using fallback.
  exit /b 0
)
if not defined CONDA_PREFIX (
  echo   [WARN] activate returned 0 but CONDA_PREFIX not set; using fallback.
  exit /b 0
)
if not exist "!CONDA_PREFIX!\python.exe" (
  echo   [WARN] env "!CENTERPOINT_CONDA_ENV!" has no python.exe at "!CONDA_PREFIX!\python.exe".
  echo          This env looks empty; the launcher will fall back to base / PATH Python.
  echo          Recreate it with:
  echo            conda create -n !CENTERPOINT_CONDA_ENV! python=3.9 -y
  echo            conda activate !CENTERPOINT_CONDA_ENV!
  echo            pip install -r requirements.txt
  exit /b 0
)
echo   OK conda env: !CONDA_DEFAULT_ENV!
echo      prefix    : !CONDA_PREFIX!
exit /b 0

REM ---------------------------------------------------------------------------
:pick_python
if defined CENTERPOINT_PYTHON (
  "!CENTERPOINT_PYTHON!" -c "import torch,cv2" >nul 2>&1 && (
    set "PYTHON_BIN=!CENTERPOINT_PYTHON!"
    exit /b 0
  )
)
if defined CONDA_PREFIX (
  if exist "!CONDA_PREFIX!\python.exe" (
    "!CONDA_PREFIX!\python.exe" -c "import torch,cv2" >nul 2>&1 && (
      set "PYTHON_BIN=!CONDA_PREFIX!\python.exe"
      exit /b 0
    )
  )
)
for %%P in (
  "%USERPROFILE%\miniconda3\envs\centerpoint\python.exe"
  "%USERPROFILE%\anaconda3\envs\centerpoint\python.exe"
  "%USERPROFILE%\miniforge3\envs\centerpoint\python.exe"
  "%USERPROFILE%\mambaforge\envs\centerpoint\python.exe"
  "%USERPROFILE%\AppData\Local\miniconda3\envs\centerpoint\python.exe"
  "%USERPROFILE%\AppData\Local\anaconda3\envs\centerpoint\python.exe"
) do (
  if exist "%%~P" (
    "%%~P" -c "import torch,cv2" >nul 2>&1 && (
      set "PYTHON_BIN=%%~P"
      exit /b 0
    )
  )
)
for /f "delims=" %%i in ('where python 2^>nul') do (
  "%%i" -c "import torch,cv2" >nul 2>&1 && (
    set "PYTHON_BIN=%%i"
    exit /b 0
  )
)
exit /b 1

REM ---------------------------------------------------------------------------
REM exit /b 1 = port busy ; exit /b 0 = port free
:port_busy
netstat -ano | findstr /C:":%~1 " | findstr LISTENING >nul 2>&1
if errorlevel 1 exit /b 0
exit /b 1
