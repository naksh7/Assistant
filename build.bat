@echo off
echo Building Voice Assistant Executable...
echo.

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
)

REM Run the build script
python build_exe.py

echo.
echo Build process completed!
pause
