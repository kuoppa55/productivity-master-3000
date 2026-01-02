@echo off
:: Change directory to the folder where this script is located
cd /d "%~dp0"

:: Run the python script using the VENV python executable
start "" "..\venv\Scripts\pythonw.exe" "main.pyw"

exit