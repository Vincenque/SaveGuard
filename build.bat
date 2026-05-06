@echo off
:: Variables and parameters
set SCRIPT_NAME=SaveGuard.py
set BASE_NAME=SaveGuard

echo [%DATE% %TIME%] Starting build process...

:: Extract version from latest git commit
:: It takes the first word (token) before a space or hyphen
for /f "tokens=1 delims=- " %%i in ('git log -1 --format^="%%s"') do set RAW_VERSION=%%i

:: Format version (V0.06 -> v-0-06)
set FORMATTED_VERSION=%RAW_VERSION:V=v-%
set FORMATTED_VERSION=%FORMATTED_VERSION:.=-%
set FINAL_NAME=%BASE_NAME%_%FORMATTED_VERSION%

echo [%DATE% %TIME%] Detected version: %RAW_VERSION%. Output filename will be: %FINAL_NAME%.exe

echo [%DATE% %TIME%] Running PyInstaller...
python -m PyInstaller --onefile --noconsole --name %FINAL_NAME% %SCRIPT_NAME%

echo [%DATE% %TIME%] Moving executable to current directory...
move dist\%FINAL_NAME%.exe .

echo [%DATE% %TIME%] Cleaning up temporary files...
rmdir /S /Q build
rmdir /S /Q dist
del /Q %FINAL_NAME%.spec

echo [%DATE% %TIME%] Build complete!
pause