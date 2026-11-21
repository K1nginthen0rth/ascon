@echo off
:: Tamanho x representacao: atributos sobre 80 B e bits crus sobre 64 KB.
cd /d %~dp0\..\..
set PYTHONIOENCODING=utf-8
set L=build\reduced_rounds\floor_v2\representacao.log
echo #### INICIO %DATE% %TIME% >> %L%
python scripts\reduced_rounds\run_representacao.py atributos80 --jobs 6 >> %L% 2>&1
echo #### FIM atributos80 >> %L%
python scripts\reduced_rounds\run_representacao.py bits64k >> %L% 2>&1
echo #### FIM %DATE% %TIME% >> %L%
