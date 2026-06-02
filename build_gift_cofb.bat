@echo off
echo Compilando GIFT-COFB via cffi (MSVC x64)...
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64
if errorlevel 1 (
    echo ERRO: vcvarsall.bat nao encontrado.
    echo Instale Visual Studio 2022 Build Tools.
    exit /b 1
)
python src\crypto\_gift_cofb_cffi_build.py
if errorlevel 1 (
    echo ERRO: Compilacao cffi falhou.
    exit /b 1
)
echo OK: GIFT-COFB compilado com sucesso.
