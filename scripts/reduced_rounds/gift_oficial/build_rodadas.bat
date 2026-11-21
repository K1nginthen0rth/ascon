@echo off
:: Compila a implementação de referência oficial do GIFT-COFB (pacote de
:: submissão da rodada final do NIST) com o número de rodadas da cifra de
:: bloco exposto como a variável `gift_rounds` (padrão 40). A única mudança no
:: gift128.c oficial é o limite do laço: `round<gift_rounds` no lugar de `round<40`.
:: Fontes em build\reduced_rounds\_gift_oficial_rodadas\src (gitignored).
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64 >nul
set DISTUTILS_USE_SDK=1
set MSSdk=1
set D=%~dp0..\..\..\build\reduced_rounds\_gift_oficial_rodadas
python -I "%~dp0build_rodadas.py" "%D%\src" "%D%" "%D%\inc"
