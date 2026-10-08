@echo off
REM Caminhos neurais do estudo de piso (redes de neural_floor.py).
REM
REM Pergunta: com um modelo mais forte que os classicos, o piso sobe?
REM Cenario: contador zero (o que define o piso da tese). Rodadas: uma abaixo do
REM piso, o piso, a seguinte e a especificacao completa como controle.
REM Representacoes: xor (mesma entrada dos classicos) e par (os dois
REM criptogramas lado a lado, que so as redes conseguem usar).
REM
REM Uso, a partir da raiz do repositorio:
REM     scripts\reduced_rounds\rodar_piso_neural.bat            (modo sweep, ~5 h)
REM     scripts\reduced_rounds\rodar_piso_neural.bat full       (CV de 5 folds, ~6x mais lento)
REM Para nao morrer ao fechar o VSCode, lancar destacado:
REM     powershell Start-Process scripts\reduced_rounds\rodar_piso_neural.bat -WindowStyle Hidden
REM
REM Saidas: build\reduced_rounds\floor_v2\contador_zero_neural\ e
REM contador_zero_par_neural\, um <algo>_floor\ por algoritmo. Piso com
REM report_floor.py --dir <...>\<algo>_floor\reports --csv <...>\piso.csv
REM
REM Modelos: ResNet_Gohr e MLP_Shen. CNN1D_bytes e Transformer_bytes existem
REM mas ficam de fora por padrao: no teste em dados reais a CNN1D nao separou o
REM par (F1 0,44) e as duas levam varios minutos por ajuste. Para incluir,
REM acrescente os nomes em MODELOS.

cd /d %~dp0\..\..
set PYTHONIOENCODING=utf-8
set MODO=%1
if "%MODO%"=="" set MODO=sweep
set MODELOS=ResNet_Gohr MLP_Shen
set LOG=build\reduced_rounds\floor_v2\piso_neural_%MODO%.log
if not exist build\reduced_rounds\floor_v2 mkdir build\reduced_rounds\floor_v2
call :main > "%LOG%" 2>&1
exit /b

:main
echo #### INICIO %DATE% %TIME%  modo=%MODO%  modelos=%MODELOS%
for %%R in (xor par) do (
  echo #### %%R: ASCON
  .venv\Scripts\python.exe -u scripts\reduced_rounds\run_floor.py --contador zero --representacao %%R --tag neural --arms texto aleatorio --mode %MODO% --models %MODELOS% --algo ascon --politica ambos --rounds 1 2 3 4 12
  echo #### %%R: SCHWAEMM
  .venv\Scripts\python.exe -u scripts\reduced_rounds\run_floor.py --contador zero --representacao %%R --tag neural --arms texto aleatorio --mode %MODO% --models %MODELOS% --algo schwaemm --politica ambos --rounds 1 2 3 11
  echo #### %%R: GRAIN
  .venv\Scripts\python.exe -u scripts\reduced_rounds\run_floor.py --contador zero --representacao %%R --tag neural --arms texto aleatorio --mode %MODO% --models %MODELOS% --algo grain --rounds 1 24 28 29 30 32 256
  echo #### %%R: GIFT
  .venv\Scripts\python.exe -u scripts\reduced_rounds\run_floor.py --contador zero --representacao %%R --tag neural --arms texto aleatorio --mode %MODO% --models %MODELOS% --algo gift --rounds 1 2 3 4 40
)
echo #### FIM %DATE% %TIME%
exit /b
