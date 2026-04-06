\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{JNCCtemplate}[2024 JNCC Paper Template]

\LoadClass[12pt]{article}

\RequirePackage{times}
\RequirePackage{hyperref}
\RequirePackage{amsmath}
\RequirePackage{graphicx}
\RequirePackage{booktabs}
\RequirePackage{geometry}

\geometry{
    a4paper,
    left=25mm,
    right=25mm,
    top=30mm,
    bottom=30mm
}

\def\@authors{}
\def\@affiliation{}
\def\@email{}

\newcommand{\authors}[1]{\def\@authors{#1}}
\newcommand{\affiliation}[1]{\def\@affiliation{#1}}
\newcommand{\email}[1]{\def\@email{#1}}

\renewenvironment{document}{\begin{document}}{\end{document}}

\def\@maketitle{
    \newpage
    \null
    \vskip 2em
    \begin{center}%
        \let \footnote \thanks
        {\LARGE \@title \par}%
        \vskip 1.5em%
        {\large
            \lineskip .5em%
            \@authors \par%
            \vskip 0.5em%
            {\it \@affiliation} \par%
            {\tt \@email} \par%
        }%
    \end{center}%
    \par
    \vskip 1.5em
}

\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    citecolor=black,
    urlcolor=black
}

\endinput
