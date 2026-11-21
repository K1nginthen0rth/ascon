@echo off
:: Piso com pares de nonces a distancia k (c, c+k), contador zero, texto-en.
:: Mesmo desenho do estudo principal (contador_zero_corpus_en), so muda k.
cd /d %~dp0\..\..
set PYTHONIOENCODING=utf-8
set KS=%*
if "%KS%"=="" set KS=2 3 4 8 16 64 256
set LOG=build\reduced_rounds\floor_v2\distancia_nonce.log
echo #### INICIO %DATE% %TIME% >> %LOG%
for %%K in (%KS%) do (
  python scripts\reduced_rounds\run_floor.py --algo ascon --arms texto-en aleatorio --contador zero --tag corpus_en --distancia %%K --rounds 1 2 3 4 5 8 12 >> %LOG% 2>&1
  python scripts\reduced_rounds\report_floor.py --dir build\reduced_rounds\floor_v2\contador_zero_dist%%K_corpus_en\ascon_floor\reports --csv build\reduced_rounds\floor_v2\contador_zero_dist%%K_corpus_en\ascon_floor\piso.csv >> %LOG% 2>&1
  python scripts\reduced_rounds\run_floor.py --algo gift --arms texto-en aleatorio --contador zero --tag corpus_en --distancia %%K --rounds 1 2 3 4 5 20 40 >> %LOG% 2>&1
  python scripts\reduced_rounds\report_floor.py --dir build\reduced_rounds\floor_v2\contador_zero_dist%%K_corpus_en\gift_floor\reports --csv build\reduced_rounds\floor_v2\contador_zero_dist%%K_corpus_en\gift_floor\piso.csv >> %LOG% 2>&1
  python scripts\reduced_rounds\run_floor.py --algo schwaemm --arms texto-en aleatorio --contador zero --tag corpus_en --distancia %%K --rounds 1 2 3 4 8 11 >> %LOG% 2>&1
  python scripts\reduced_rounds\report_floor.py --dir build\reduced_rounds\floor_v2\contador_zero_dist%%K_corpus_en\schwaemm_floor\reports --csv build\reduced_rounds\floor_v2\contador_zero_dist%%K_corpus_en\schwaemm_floor\piso.csv >> %LOG% 2>&1
  echo #### FIM k=%%K %DATE% %TIME% >> %LOG%
)
echo #### FIM %DATE% %TIME% >> %LOG%
