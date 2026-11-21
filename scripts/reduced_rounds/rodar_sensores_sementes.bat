@echo off
:: 1) Piso com dados de sensores (Intel Berkeley Lab), mesmo desenho do estudo principal.
:: 2) Estudo principal com 5 sementes (dados, separacao e modelos), em modo full
::    (validacao cruzada de 5 dobras por chave + teste final).
cd /d %~dp0\..\..
set PYTHONIOENCODING=utf-8
set L=build\reduced_rounds\floor_v2\sensores_sementes.log
echo #### INICIO %DATE% %TIME% >> %L%
python scripts\reduced_rounds\run_floor.py --algo ascon --arms sensor aleatorio --contador zero --tag sensores --rounds 1 2 3 4 5 8 12 >> %L% 2>&1
python scripts\reduced_rounds\run_floor.py --algo gift --arms sensor aleatorio --contador zero --tag sensores --rounds 1 2 3 4 5 20 40 >> %L% 2>&1
python scripts\reduced_rounds\run_floor.py --algo schwaemm --arms sensor aleatorio --contador zero --tag sensores --rounds 1 2 3 4 8 11 >> %L% 2>&1
echo #### FIM sensores >> %L%
for %%S in ("0 999004 42 7" "1 1001 101 11" "2 1002 102 12" "3 1003 103 13" "4 1004 104 14") do (
  for /f "tokens=1-4" %%a in (%%S) do (
    python scripts\reduced_rounds\run_floor.py --algo ascon --arms texto-en aleatorio --contador zero --tag corpus_en_s%%a --seed-gen %%b --seed-split %%c --seed-model %%d --mode full --rounds 1 2 3 4 8 12 >> %L% 2>&1
    python scripts\reduced_rounds\run_floor.py --algo gift --arms texto-en aleatorio --contador zero --tag corpus_en_s%%a --seed-gen %%b --seed-split %%c --seed-model %%d --mode full --rounds 1 2 3 4 20 40 >> %L% 2>&1
    python scripts\reduced_rounds\run_floor.py --algo schwaemm --arms texto-en aleatorio --contador zero --tag corpus_en_s%%a --seed-gen %%b --seed-split %%c --seed-model %%d --mode full --rounds 1 2 3 8 11 >> %L% 2>&1
    echo #### FIM semente %%a >> %L%
  )
)
echo #### FIM %DATE% %TIME% >> %L%
