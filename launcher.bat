@echo off
title InvesTrack Pro Launcher
cd /d "%~dp0"

echo =========================================
echo     Starting InvesTrack Pro
echo     Detecting Python installation...
echo =========================================
echo.

REM 1) Try default python
python --version >nul 2>&1
IF %ERRORLEVEL%==0 (
    echo Python found: using "python"
    python -m streamlit run app.py
    goto end
)

REM 2) Try py launcher
py --version >nul 2>&1
IF %ERRORLEVEL%==0 (
    echo Python found: using "py"
    py -m streamlit run app.py
    goto end
)

REM 3) Try common install paths
set PYTHON_CANDIDATE=

for %%P in (
    "C:\Program Files\Python311\python.exe"
    "C:\Program Files\Python312\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Microsoft\WindowsApps\python.exe"
    "C:\Users\%USERNAME%\AppData\Local\Python\bin\python.exe"
) do (
    if exist %%P (
        set PYTHON_CANDIDATE=%%P
    )
)

if defined PYTHON_CANDIDATE (
    echo Python found at %PYTHON_CANDIDATE%
    %PYTHON_CANDIDATE% -m streamlit run app.py
    goto end
)

echo.
echo ERROR: Python not found.
echo Please install Python from https://www.python.org/downloads/
echo Or ensure python.exe is in your PATH.
echo.
pause
exit

:end
echo.
echo InvesTrack Pro closed.
pause
exit
