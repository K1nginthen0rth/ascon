@echo off
:: Segunda etapa do tamanho x representacao: bits crus sobre 64 KB.
cd /d %~dp0\..\..
set PYTHONIOENCODING=utf-8
set L=build\reduced_rounds\floor_v2\representacao.log
echo #### INICIO bits64k %DATE% %TIME% >> %L%
python scripts\reduced_rounds\run_representacao.py bits64k >> %L% 2>&1
echo #### FIM bits64k %DATE% %TIME% >> %L%
