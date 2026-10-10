@echo off
setlocal
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul
if errorlevel 1 exit /b 1
set DISTUTILS_USE_SDK=1
set MSSdk=1
set PYTHONIOENCODING=utf-8
"c:\Users\nycol\Documents\Mestrado\ascon\.venv\Scripts\python.exe" -u "C:\Users\nycol\Documents\Mestrado\ascon\scripts\reduced_rounds\exp_contador\escala.py" %*
