@echo off
:: Busca de hiperparametros com a selecao na RODADA DO PISO (e nao no piso+1),
:: para ver se o ajuste melhora o F1 e a AUC no piso. Saida em
:: build\reduced_rounds\floor_v2\metodo_ml_piso\. Arvores e LR em sequencia;
:: o SVM roda em paralelo, um processo por algoritmo, como na busca original.
cd /d %~dp0\..\..
set PYTHONIOENCODING=utf-8
set L=build\reduced_rounds\floor_v2
echo #### INICIO %DATE% %TIME% > %L%\metodo_ml_piso_arvores.log
start "" /b cmd /c "python scripts\reduced_rounds\metodo_ml.py --algo ascon --modelos SVM --celula-selecao piso > %L%\metodo_ml_piso_svm_ascon.log 2>&1"
start "" /b cmd /c "python scripts\reduced_rounds\metodo_ml.py --algo gift --modelos SVM --celula-selecao piso > %L%\metodo_ml_piso_svm_gift.log 2>&1"
start "" /b cmd /c "python scripts\reduced_rounds\metodo_ml.py --algo schwaemm --modelos SVM --celula-selecao piso > %L%\metodo_ml_piso_svm_schwaemm.log 2>&1"
for %%A in (ascon gift schwaemm) do (
  python scripts\reduced_rounds\metodo_ml.py --algo %%A --modelos LR RF XGB --celula-selecao piso >> %L%\metodo_ml_piso_arvores.log 2>&1
)
echo #### FIM arvores >> %L%\metodo_ml_piso_arvores.log
