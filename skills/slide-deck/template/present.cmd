@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 発表スライドを起動します...
node "%~dp0serve.mjs"
pause
