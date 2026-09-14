use strict;
use warnings;

# O MiKTeX 25.x imprime um aviso ("major issue: voce ainda nao checou
# atualizacoes") em stderr e retorna exit code 1 em toda chamada de
# pdflatex/bibtex/makeindex, mesmo quando a compilacao em si funciona sem
# nenhum erro real de conteudo. Isso faz o latexmk (e por consequencia a
# extensao LaTeX Workshop) interpretar cada passada como falha e parar a
# cadeia automatica de pdflatex -> bibtex -> pdflatex -> pdflatex antes de
# terminar. force_mode manda o latexmk seguir em frente mesmo diante desse
# "erro", que nao é real.
$force_mode = 1;
