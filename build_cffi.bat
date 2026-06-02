@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
if errorlevel 1 exit /b 1
"c:\Users\nycol\Documents\Mestrado\ascon\.venv\Scripts\python.exe" "C:\Users\nycol\Documents\Mestrado\ascon\src\crypto\_ascon_cffi_build.py"
