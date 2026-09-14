%%
%
% ARQUIVO: seminario.cls
%
% VERSÃO: 1.1
% DATA: Abril de 2016
% AUTOR: Coordenação PPgSC
% 
%  Arquivo cls (classe de documento) com a formatação principal do relatório de Avaliação de Trabalho de Dissertação.
%
%%

\NeedsTeXFormat{LaTeX2e}[1995/12/01]
\ProvidesClass{seminario}

% -----
% OPÇÕES DA CLASSE DO DOCUMENTO
% -----
\newif\if@titlepage
\@titlepagetrue
\newif\if@append
\@appendfalse
\newif\if@appendformat
\@appendformatfalse
\newif\if@annexformat
\@annexformatfalse
\newif\if@abrevia
\@abreviafalse
\newif\if@simbo
\@simbofalse

% -----
% TIPOS DE PAPEL
% -----
\DeclareOption{a4paper}        {\setlength\paperheight{297mm} \setlength\paperwidth{210mm}}
\DeclareOption{a5paper}        {\setlength\paperheight{210mm} \setlength\paperwidth{148mm}}
\DeclareOption{b5paper}        {\setlength\paperheight{250mm} \setlength\paperwidth{176mm}}
\DeclareOption{letterpaper}    {\setlength\paperheight{11in} \setlength\paperwidth{8.5in}}
\DeclareOption{legalpaper}     {\setlength\paperheight{14in} \setlength\paperwidth{8.5in}}
\DeclareOption{executivepaper} {\setlength\paperheight{10.5in} \setlength\paperwidth{7.25in}}
\DeclareOption{landscape}      {\setlength\@tempdima{\paperheight} \setlength\paperheight{\paperwidth} \setlength\paperwidth{\@tempdima}}
\DeclareOption{titlepage}	   {\@titlepagetrue}

% -----
% TAMANHO DE FONTE
% -----
\newcommand\@ptsize{}
\DeclareOption{10pt}{\renewcommand\@ptsize{0}}
\DeclareOption{11pt}{\renewcommand\@ptsize{1}}
\DeclareOption{12pt}{\renewcommand\@ptsize{2}}

% -----
% NÚMERO DE COLUNAS
% -----
\newif\if@restonecol
\DeclareOption{onecolumn}{\@twocolumnfalse}
\DeclareOption{twocolumn}{\@twocolumntrue}

% -----
% TIPO DE IMPRESSÃO
% -----
\newif\if@openright
\DeclareOption{oneside}{\@twosidefalse \@mparswitchfalse}
\DeclareOption{twoside}{\@twosidetrue  \@mparswitchtrue}

% -----
% APRESENTAÇÃO DE EQUAÇÕES
% -----
\DeclareOption{leqno}{\input{leqno.clo}} % Posicionar a numeração das equações à esquerda
\DeclareOption{fleqn}{\input{fleqn.clo}} % Posicionar as equações a uma indentação fixa da margem esquerda

% -----
% ESTILO DO DOCUMENTO
% -----
\DeclareOption{draft}{\setlength\overfullrule{5pt}}
\DeclareOption{final}{\setlength\overfullrule{0pt}}
\DeclareOption{openright}{\@openrighttrue}
\DeclareOption{openany}{\@openrightfalse}

% -----
% OPÇÕES PADRÃO DO DOCUMENTO
% -----
\ExecuteOptions{a4paper,12pt,oneside,titlepage,onecolumn,final,openany}
\ProcessOptions
\input{size1\@ptsize.clo}
\setlength\lineskip{1\p@}
\setlength\normallineskip{1\p@}
\renewcommand\baselinestretch{}
\setlength\parskip{0\p@ \@plus \p@}
\@lowpenalty   51
\@medpenalty  151
\@highpenalty 301

\setcounter{topnumber}{2}
\renewcommand\topfraction{.7}
\setcounter{bottomnumber}{1}
\renewcommand\bottomfraction{.3}
\setcounter{totalnumber}{3}
\renewcommand\textfraction{.2}
\renewcommand\floatpagefraction{.5}
\setcounter{dbltopnumber}{2}
\renewcommand\dbltopfraction{.7}
\renewcommand\dblfloatpagefraction{.5}

% -----
% ESTILO DAS PÁGINAS
% -----
\if@twoside
    \def\ps@headings{%
        \let\@oddfoot\@empty\let\@evenfoot\@empty
        \def\@evenhead{\thepage\hfil\slshape\leftmark}%
        \def\@oddhead{{\slshape\rightmark}\hfil\thepage}%
        \let\@mkboth\markboth
        \def\chaptermark##1{%
            \markboth {\MakeUppercase{%
            \ifnum \c@secnumdepth >\m@ne \@chapapp\ \thechapter. \ \fi
            ##1}}{}}%
        \def\sectionmark##1{%
            \markright {\MakeUppercase{%
            \ifnum \c@secnumdepth >\z@ \thesection. \ \fi
        ##1}}}}
\else
    \def\ps@headings{%
        \let\@oddfoot\@empty
        \def\@oddhead{{\slshape\rightmark}\hfil\thepage}%
        \let\@mkboth\markboth
        \def\chaptermark##1{%
            \markright {\MakeUppercase{%
            \ifnum \c@secnumdepth >\m@ne \@chapapp\ \thechapter. \ \fi
            ##1}}}}
\fi

\def\ps@myheadings{%
    \let\@oddfoot\@empty\let\@evenfoot\@empty
    \def\@evenhead{\thepage\hfil\slshape\leftmark}%
    \def\@oddhead{{\slshape\rightmark}\hfil\thepage}%
    \let\@mkboth\@gobbletwo
    \let\chaptermark\@gobble
    \let\sectionmark\@gobble}
\def\ssp{\def\baselinestretch{1.0}\large\normalsize}
\def\dsp{\def\baselinestretch{1.37}\large\normalsize}


% -----
% ELEMENTOS DO TEXTO (CAPÍTULO, SEÇÃO, SUBSEÇÃO, ETC.)
% -----
\newcommand*\chaptermark[1]{}
\setcounter{secnumdepth}{3}

\newcounter {part}
\newcounter {chapter}
\newcounter {section}[chapter]
\newcounter {subsection}[section]
\newcounter {subsubsection}[subsection]
\newcounter {paragraph}[subsubsection]
\newcounter {subparagraph}[paragraph]

\renewcommand\thepart {\@Roman\c@part}
\renewcommand\thechapter {\@arabic\c@chapter}
\renewcommand\thesection {\thechapter.\@arabic\c@section}
\renewcommand\thesubsection   {\thesection.\@arabic\c@subsection}
\renewcommand\thesubsubsection{\thesubsection .\@arabic\c@subsubsection}
\renewcommand\theparagraph    {\thesubsubsection.\@arabic\c@paragraph}
\renewcommand\thesubparagraph {\theparagraph.\@arabic\c@subparagraph}

\newcommand\nomecapitulo{CAP{\'I}TULO}
\newcommand\@chapapp{\nomecapitulo}

\newcommand\part{
	\if@openright \cleardoublepage \else \clearpage \fi
	\thispagestyle{plain}
	\if@twocolumn \onecolumn \@tempswatrue \else \@tempswafalse \fi
	\null\vfil
	\secdef\@part\@spart}

\def\@part[#1]#2{
	\ifnum \c@secnumdepth >-2\relax
		\refstepcounter{part}%
		\addcontentsline{toc}{part}{\thepart\hspace{1em}#1}%
	\else
		\addcontentsline{toc}{part}{#1}%
	\fi
	\markboth{}{} {
		\centering
		\interlinepenalty \@M
		\normalfont
		\ifnum \c@secnumdepth >-2\relax
			\huge\bfseries \nomeparte~\thepart
			\par
			\vskip 20\p@
		\fi
		\Huge \bfseries #2\par}
	\@endpart}

\def\@spart#1{
    {  \centering
	   \interlinepenalty \@M
       \normalfont
       \Huge \bfseries #1\par}
    \@endpart}

\def\@endpart{
	\vfil\newpage
	\if@twoside
		\null
		\thispagestyle{empty}%
		\newpage
	\fi
	\if@tempswa
		\twocolumn
	\fi}

\newcommand\chapter{
    \if@openright \cleardoublepage \else \clearpage \fi
    \thispagestyle{plain}%
    \global\@topnum\z@
    \@afterindenttrue
    \dsp
    \secdef\@chapter\@schapter}

\def\@chapter[#1]#2{
    \ifnum \c@secnumdepth >\m@ne
        \if@append \refstepcounter{section} \else \refstepcounter{chapter} \fi%
        \typeout{\@chapapp\space\thechapter.}%
        {
            \def\\{ }%
            \if@append
                \addcontentsline{toc}{section}{\protect\numberline{\thesection\ }\uppercase{\@chapapp \space \@arabic\c@section}:\space#1}
            \else
                \if@appendformat
                    \addcontentsline{toc}{chapter}{\protect\numberline{\thechapter\ }\textbf\nomeindiceapendice}
                \else
                    \if@annexformat
                        \addcontentsline{toc}{chapter}{\protect\numberline{\thechapter\ }\textbf\nomeindiceanexo}
                    \else
                        \addcontentsline{toc}{chapter}{\protect\numberline{\thechapter\ }\bf#1}
                    \fi
                \fi
            \fi
        }%
    \else
        {
            \def\\{ }  % allow \\ in title
            \addcontentsline{toc}{chapter}{#1}
        }%
    \fi
    \chaptermark{#1}%
    \addtocontents{lof}{\protect\addvspace{10\p@}}%
    \addtocontents{lot}{\protect\addvspace{10\p@}}%
    \if@twocolumn \@topnewpage[\@makechapterhead{#2}] \else \@makechapterhead{#2} \@afterheading \fi}

\def\@makechapterhead#1{%
    {
        \parindent \z@ \raggedright \normalfont
        \interlinepenalty\@M
        \if@append 
%            \thesection \space \@chapapp \space \@arabic\c@section: \space \MakeUppercase{#1} \par \nobreak% 
            \@chapapp \space \@arabic\c@section: \space \MakeUppercase{#1} \par \nobreak% 
        \else 
            \bfseries \thechapter \space \MakeUppercase{#1} \par \nobreak%
        \fi
            \vskip 3\baselineskip
        \dsp
    }}

\def\@schapter#1{
	\if@twocolumn
		\@topnewpage[\@makeschapterhead{#1}]%
	\else
		\@makeschapterhead{#1}%
		\@afterheading
	\fi}

\def\@makeschapterhead#1{
	\parindent \z@ 
	\normalfont
	\hbox to\textwidth{\bfseries \hfill
	\MakeUppercase{#1}\hfill}
	\nobreak
	\vskip 20\p@
	\dsp}

\newcommand\section{
    \@startsection {section}{1}{\z@}
        {-3.5ex \@plus -1ex \@minus -.2ex}
        {2.3ex \@plus.2ex}
        {\normalfont\MakeUppercase}}

\newcommand\subsection{
    \@startsection{subsection}{2}{\z@}
    {-3.25ex\@plus -1ex \@minus -.2ex}
    {1.5ex \@plus .2ex}
    {\normalfont\MakeUppercase}}

\newcommand\subsubsection{
    \@startsection{subsubsection}{3}{\z@}
    {-3.25ex\@plus -1ex \@minus -.2ex}
    {1.5ex \@plus .2ex}
    {\normalfont\normalsize\MakeUppercase}}

\newcommand\paragraph{
    \@startsection{paragraph}{4}{\z@}
    {3.25ex \@plus1ex \@minus.2ex}
    {-1em}
    {\normalfont\normalsize}}

\newcommand\subparagraph{
    \@startsection{subparagraph}{5}{\parindent}
    {3.25ex \@plus1ex \@minus .2ex}
    {-1em}%
    {\normalfont\normalsize}}


% -----
% DEFINIÇÕES DE LISTAS
% -----
\if@twocolumn \setlength\leftmargini  {2em} \else \setlength\leftmargini  {2.5em} \fi

\leftmargin  \leftmargini
\setlength\leftmarginii  {2.2em}
\setlength\leftmarginiii {1.87em}
\setlength\leftmarginiv  {1.7em}

\if@twocolumn \setlength\leftmarginv  {.5em} \setlength\leftmarginvi {.5em} \else \setlength\leftmarginv  {1em} \setlength\leftmarginvi {1em} \fi

\setlength  \labelsep  {.5em}
\setlength  \labelwidth{\leftmargini}
\addtolength\labelwidth{-\labelsep}
\@beginparpenalty -\@lowpenalty
\@endparpenalty   -\@lowpenalty
\@itempenalty     -\@lowpenalty

\renewcommand\theenumi{\@arabic\c@enumi}
\renewcommand\theenumii{\@alph\c@enumii}
\renewcommand\theenumiii{\@roman\c@enumiii}
\renewcommand\theenumiv{\@Alph\c@enumiv}
\newcommand{\labelenumi}{\alph{enumi})}
\newcommand\labelenumii{\arabic{enumii})}
\newcommand\labelenumiii{\theenumiii.}
\newcommand\labelenumiv{\theenumiv.}
\renewcommand\p@enumii{\theenumi}
\renewcommand\p@enumiii{\theenumi(\theenumii)}
\renewcommand\p@enumiv{\p@enumiii\theenumiii}

\newcommand\labelitemi{\textbullet}
\newcommand\labelitemii{\normalfont\bfseries \textendash}
\newcommand\labelitemiii{\textasteriskcentered}
\newcommand\labelitemiv{\textperiodcentered}

\newenvironment{description}
    {\list{}{
        \labelwidth\z@ \itemindent-\leftmargin
        \let\makelabel\descriptionlabel}}
    {\endlist}

\newcommand*\descriptionlabel[1]{\hspace\labelsep \normalfont\bfseries #1}


% -----
% DEFINIÇÕES DE CITAÇÕES LONGAS
% -----
\newenvironment{verse}
    {\let\\\@centercr
     \list{}{
        \itemsep      \z@
        \itemindent   -1.5em%
        \listparindent\itemindent
        \rightmargin  \leftmargin
        \advance\leftmargin 1.5em}%
     \item\relax}
    {\endlist}

\newenvironment{quotation}
    {\list{}{
        \listparindent 1.5em%
        \itemindent    \listparindent
        \rightmargin   \leftmargin
        \parsep        \z@ \@plus\p@}%
     \item\relax}
    {\endlist}

\newenvironment{quote}
    {\list{}{\rightmargin\leftmargin} \item\relax}
    {\endlist}


% -----
% DEFINIÇÕES DE TIPOS DE TEOREMAS
% -----
\newcounter{teorema}[chapter]
\newenvironment{thm}[1][]{\refstepcounter{teorema}\par\medskip
   \textbf{Teorema~\theteorema. #1} \rmfamily\itshape}

\newcounter{problema}[chapter]
\newenvironment{probl}[1][]{\refstepcounter{problema}\par\medskip
   \textbf{Problema~\theproblema. #1} \rmfamily\itshape}

\newcounter{questao}[chapter]
\newenvironment{qpesq}[1][]{\refstepcounter{questao}\par\medskip
   \textbf{Quest\~{a}o de Pesquisa~\thequestao. #1} \rmfamily\itshape}

\newcounter{hipotese}[chapter]
\newenvironment{hipo}[1][]{\refstepcounter{hipotese}\par\medskip
   \textbf{Hip\'{o}tese~\thehipotese. #1} \rmfamily\itshape}

\newcounter{proposicao}[chapter]
\newenvironment{prop}[1][]{\refstepcounter{proposicao}\par\medskip
   \textbf{Proposi\c{c}\~{a}o~\theproposicao. #1} \rmfamily}

\newcounter{definicao}[chapter]
\newenvironment{defn}[1][]{\refstepcounter{definicao}\par\medskip
   \textbf{Defini\c{c}\~{a}o~\thedefinicao. #1} \rmfamily\itshape}

\newcounter{exemplo}[chapter]
\newenvironment{exmp}[1][]{\refstepcounter{exemplo}\par\medskip
   \textbf{Exemplo~\theexemplo. #1} \rmfamily}

\newcounter{nota}[chapter]
\newenvironment{nota}[1][]{\refstepcounter{nota}\par\medskip
   \textbf{Nota~\thenota. #1} \rmfamily}

\newcounter{tarefaok}[chapter]
\newenvironment{tarefac}[1][]{\refstepcounter{tarefaok}\par\medskip
   \textbf{Tarefa~\thetarefaok. #1} \rmfamily\itshape}

\newcounter{tarefanok}[chapter]
\newenvironment{tarefanc}[1][]{\refstepcounter{tarefanok}\par\medskip
   \textbf{Tarefa~\thetarefanok. #1} \rmfamily\itshape}


% -----
% NUMERAÇÃO DAS EQUAÇÕES POR CAPÍTULO
% -----
\@addtoreset {equation}{chapter}
\renewcommand\theequation
  {\ifnum \c@chapter>\z@ \thechapter.\fi \@arabic\c@equation}


% -----
% DEFINIÇÕES DE FIGURAS E TABELAS
% -----
\setlength\arraycolsep{5\p@}
\setlength\tabcolsep{6\p@}
\setlength\arrayrulewidth{.4\p@}
\setlength\doublerulesep{2\p@}
\setlength\tabbingsep{\labelsep}
\skip\@mpfootins = \skip\footins
\setlength\fboxsep{3\p@}
\setlength\fboxrule{.4\p@}

\newcommand\nomefigura{FIG.}
\newcommand\nometabela{TAB.}

\newcounter{figure}[chapter]
\renewcommand \thefigure {\ifnum \c@chapter>\z@ \thechapter.\fi \@arabic\c@figure}
\def\fps@figure{tbp}
\def\ftype@figure{1}
\def\ext@figure{lof}
\def\fnum@figure{\nomefigura~\thefigure}
\newenvironment{figure}
    {\ssp\@float{figure}}
    {\end@float\dsp}
\newenvironment{figure*}
    {\ssp\@dblfloat{figure}}
    {\end@dblfloat\dsp}

\newcounter{table}[chapter]
\renewcommand \thetable {\ifnum \c@chapter>\z@ \thechapter.\fi \@arabic\c@table}
\def\fps@table{tbp}
\def\ftype@table{2}
\def\ext@table{lot}
\def\fnum@table{\nometabela~\thetable}
\newenvironment{table}
    {\ssp\@float{table}}
    {\end@float\dsp}
\newenvironment{table*}
    {\ssp\@dblfloat{table}}
    {\end@dblfloat\dsp}

% -----
% DEFINIÇÕES DE RÓTULOS DE FIGURAS E TABELAS
% -----
\newlength\abovecaptionskip
\newlength\belowcaptionskip
\setlength\abovecaptionskip{10\p@}
\setlength\belowcaptionskip{0\p@}

\long\def\@makecaption#1#2{
    \vskip\abovecaptionskip
    \sbox\@tempboxa{#1: #2}
    \ifdim \wd\@tempboxa >\hsize
        #1: #2\par
    \else
        \global \@minipagefalse
        \hb@xt@\hsize{\hfil\box\@tempboxa\hfil}%
    \fi
    \vskip\belowcaptionskip}


% -----
% DEFINIÇÕES DE TYPEFACE
% -----
\DeclareOldFontCommand{\rm}{\normalfont\rmfamily}{\mathrm}
\DeclareOldFontCommand{\sf}{\normalfont\sffamily}{\mathsf}
\DeclareOldFontCommand{\tt}{\normalfont\ttfamily}{\mathtt}
\DeclareOldFontCommand{\bf}{\normalfont\bfseries}{\mathbf}
\DeclareOldFontCommand{\it}{\normalfont\itshape}{\mathit}
\DeclareOldFontCommand{\sl}{\normalfont\slshape}{\@nomath\sl}
\DeclareOldFontCommand{\sc}{\normalfont\scshape}{\@nomath\sc}
\DeclareRobustCommand*\cal{\@fontswitch\relax\mathcal}
\DeclareRobustCommand*\mit{\@fontswitch\relax\mathnormal}


% -----
% DADOS DA PROPOSTA DE DISSERTAÇÃO
% -----
\def\autor#1{\gdef\@autor{#1}}
\def\codigoautor#1{\gdef\@codigoautor{#1}}
\def\postoautor#1{\gdef\@postoautor{#1}}

\def\titulo#1{\gdef\@titulo{#1}}
\def\titantigo#1{\gdef\@titantigo{#1}}
\def\dataapresentacao#1#2#3{\gdef\@dia{#1} \gdef\@mes{#2} \gdef\@ano{#3}}

\def\area#1{\gdef\@area{#1}}
\def\linha#1{\gdef\@linha{#1}}

\def\orientador#1#2{\gdef\@orientador{#1} \gdef\@titorientador{#2}}
\def\postoorientador#1{\gdef\@postoorientador{#1}}
\gdef\@titA{}

\def\coorientador#1#2{\gdef\@coorientador{#1} \gdef\@titcoorientador{#2}}
\def\postocoorientador#1{\gdef\@postocoorientador{#1}}
\gdef\@titB{}

\def\coord#1#2{\gdef\@coord{#1} \gdef\@titcoord{#2}}
\def\postocoord#1{\gdef\@postocoord{#1}}
\gdef\@titC{}

\def\chefe#1{\gdef\@chefe{#1}}
\def\postochefe#1{\gdef\@postochefe{#1}}


% -----
% FUNÇÕES AUXILIARES
% -----
\newcommand\preparatitulos{
    \ifnum\pdfstrcmp{\@titorientador}{P}=0\gdef\@titA{Ph.D.}
    \else\ifnum\pdfstrcmp{\@titorientador}{D}=0\gdef\@titA{D.Sc.}
    \else\ifnum\pdfstrcmp{\@titorientador}{DC}=0\gdef\@titA{D.Sc.}
    \else\ifnum\pdfstrcmp{\@titorientador}{D.C.}=0\gdef\@titA{D.Sc.}
    \else\ifnum\pdfstrcmp{\@titorientador}{D.C}=0\gdef\@titA{D.Sc.}
    \else\ifnum\pdfstrcmp{\@titorientador}{DC.}=0\gdef\@titA{D.Sc.}
    \else\ifnum\pdfstrcmp{\@titorientador}{}=0\else\gdef\@titA{\@titorientador}\fi\fi\fi\fi\fi\fi\fi

	\ifdefined \@coorientador
        \ifnum\pdfstrcmp{\@titcoorientador}{P}=0\edef\@titB{Ph.D.}
        \else\ifnum\pdfstrcmp{\@titcoorientador}{D}=0\edef\@titB{D.Sc.}
        \else\ifnum\pdfstrcmp{\@titcoorientador}{DC}=0\edef\@titB{D.Sc.}
        \else\ifnum\pdfstrcmp{\@titcoorientador}{D.C.}=0\edef\@titB{D.Sc.}
        \else\ifnum\pdfstrcmp{\@titcoorientador}{D.C}=0\edef\@titB{D.Sc.}
        \else\ifnum\pdfstrcmp{\@titcoorientador}{DC.}=0\edef\@titB{D.Sc.}
        \else\ifnum\pdfstrcmp{\@titcoorientador}{}=0\else\edef\@titB{\@titcoorientador}\fi\fi\fi\fi\fi\fi\fi
    \fi

    \ifnum\pdfstrcmp{\@titcoord}{P}=0\gdef\@titC{Ph.D.}
    \else\ifnum\pdfstrcmp{\@titcoord}{D}=0\gdef\@titC{D.Sc.}
    \else\ifnum\pdfstrcmp{\@titcoord}{DC}=0\gdef\@titC{D.Sc.}
    \else\ifnum\pdfstrcmp{\@titcoord}{D.C.}=0\gdef\@titC{D.Sc.}
    \else\ifnum\pdfstrcmp{\@titcoord}{D.C}=0\gdef\@titC{D.Sc.}
    \else\ifnum\pdfstrcmp{\@titcoord}{DC.}=0\gdef\@titC{D.Sc.}
    \else\ifnum\pdfstrcmp{\@titcoord}{}=0\else\gdef\@titC{\@titcoord}\fi\fi\fi\fi\fi\fi\fi
}


% -----
% CAPA
% -----
\newcommand\makecapa{
    \thispagestyle{empty}
    \noindent
    \begin{center}

        \begin{large}
            \textbf{MINIST\'{E}RIO DA DEFESA\\}
            \textbf{EX\'{E}RCITO BRASILEIRO\\}
            \textbf{DEPARTAMENTO DE CI\^{E}NCIA E TECNOLOGIA\\}
            \textbf{INSTITUTO MILITAR DE ENGENHARIA\\}
            \textbf{CURSO DE MESTRADO EM SISTEMAS E COMPUTA\c{C}\~{A}O}

            \vspace{2cm}
            \textbf{RELAT\'{O}RIO DE ACOMPANHAMENTO DE TRABALHO DE DISSERTA\c{C}\~{A}O DE MESTRADO}

            \vspace{4.5cm}
            \textbf{\MakeUppercase{\@autor}}

            \vspace{4.5cm}
            \textbf{\MakeUppercase{\@titulo}}

            \vspace{5cm}
            \textbf{Rio de Janeiro\\}
            \textbf{\@ano}
        \end{large}
    \end{center}
    \newpage
}



% -----
% TITULO
% -----
\newcommand\maketitle{
    \thispagestyle{plain}
    \chapter{T\'{i}tulo do Trabalho de Disserta\c{c}\~{a}o}
        \begin{flushleft}
            \textbf{T\'{i}tulo Atual do Trabalho de Disserta\c{c}\~{a}o:}\\
            \@titulo \\

            \ifdefined \@titantigo
                \vspace{0.7cm}
                \textbf{T\'{i}tulo Anterior do Trabalho de Disserta\c{c}\~{a}o:}\\
                \@titantigo \\
            \fi

            \vspace{0.7cm}
            \textbf{\'{A}rea de Concentra\c{c}\~{a}o:}\\
            \@area \\

            \vspace{0.7cm}
            \textbf{Linha de Pesquisa:}\\
            \@linha \\
        \end{flushleft}
    \newpage
}


% -----
% REFERÊNCIAS BIBLIOGRÁFICAS
% -----
\newcommand\nomebibliografia{REFER\^ENCIAS BIBLIOGR\'AFICAS}

\newdimen\bibindent
\setlength\bibindent{1.5em}

\newenvironment{thebibliography}[1] {}

\newenvironment{thethesisbibliography}[1] {
    \chapter{
        \nomebibliografia
        \@mkboth{\MakeUppercase\nomebibliografia}{\MakeUppercase\nomebibliografia}
    }
    \ssp \list{}{}
} {\def\@noitemerr {\@latex@warning{Empty `thethesisbibliography' environment}} \endlist}

\newcommand\newblock{\hskip .11em\@plus.33em\@minus.07em}
\let\@openbib@code\@empty

\renewenvironment{thethesisbibliography}[1] {
    \chapter{
        \nomebibliografia
        \@mkboth{\MakeUppercase\nomebibliografia}{\MakeUppercase\nomebibliografia}
    }
    \list{\@biblabel{\@arabic\c@enumiv}} {
        \settowidth\labelwidth{\@biblabel{#1}}
        \leftmargin=20pt
        \itemindent=-20pt
        \@openbib@code
        \usecounter{enumiv}%
        \let\p@enumiv\@empty
        \renewcommand\theenumiv{\@arabic\c@enumiv}
    }
    \sloppy
    \clubpenalty4000
    \@clubpenalty \clubpenalty
    \widowpenalty4000%
    \sfcode`\.\@m
} {\def\@noitemerr {\@latex@warning{Empty `thethesisbibliography' environment}} \endlist}


% -----
% ASSINATURAS
% -----
\def\@approvalspace{2cm}
\newcommand\makeassinaturas{
    \newpage
    \begingroup
        \noindent
        \vspace{5mm}
        \begin{center}

            $\:\overline{\makebox[10cm][c]{\ifdefined \@postoautor {\@postoautor}\fi ~{\@autor} {(\@codigoautor)}}}\:$ \\
            Aluno\\
            \vspace{\@approvalspace}

            $\:\overline{\makebox[10cm][c]{\ifdefined \@postoorientador {\@postoorientador}\fi ~{\@orientador,}~{\@titA}}}\:$ \\
            Orientador\\
            \vspace{\@approvalspace}

            \ifdefined \@coorientador
                $\:\overline{\makebox[10cm][c]{\ifdefined \@postocoorientador {\@postocoorientador}\fi ~{\@coorientador,}~{\@titB}}}\:$ \\
                Co-orientador\\
                \vspace{\@approvalspace}
            \fi

            $\:\overline{\makebox[10cm][c]{\ifdefined \@postocoord {\@postocoord}\fi ~{\@coord,}~{\@titC}}}\:$ \\
            Coordenador de P\'{o}s-gradua\c{c}\~{a}o\\
        \end{center}

        \vspace{\@approvalspace}
        \noindent
        Declaro que o presente Relat\'{o}rio de Acompanhamento de Trabalho de Disserta\c{c}\~{a}o foi apresentado segundo as NICPG/IME em \@dia \:de\:\@mes \:de\:\@ano.

        \vspace{\@approvalspace}
        \begin{center}
            $\:\overline{\makebox[10cm][c]{\ifdefined \@postochefe {\@postochefe}\fi ~{\@chefe}}}\:$ \\
            CHEFE da SE/8\\
        \end{center}

    \endgroup
    \newpage
}


% -----
% GERAÇÃO DAS PÁGINAS DO DOCUMENTO
% -----

\setlength\columnsep{10\p@}
\setlength\columnseprule{0\p@}

\pagestyle{plain}
\pagenumbering{arabic}
\if@twoside \else \raggedbottom \fi
\if@twocolumn \twocolumn \sloppy \flushbottom \else \onecolumn \fi

\newenvironment{frontmatter} {
    \if@twocolumn \@restonecolfalse \else \@restonecoltrue \fi
    \columnseprule \z@
    \columnsep 35\p@
    \onecolumn
    \setcounter{page}{2}
    \renewcommand{\thepage}{\arabic{page}}
} {\newpage}
\endinput

% -----
% FIM
% -----
