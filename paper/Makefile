.PHONY: all clean watch

all: main.pdf

main.pdf: main.tex refs.bib $(wildcard sections/*.tex)
	latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

watch:
	latexmk -pdf -pvc -interaction=nonstopmode main.tex

clean:
	latexmk -C
	rm -f main.bbl main.blg
