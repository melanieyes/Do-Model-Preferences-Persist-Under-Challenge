.PHONY: all clean watch

all: main.pdf

# latexmk where a full TeX Live exists; tectonic otherwise (it fetches what it needs).
main.pdf: main.tex refs.bib pair_stats.tex $(wildcard sections/*.tex)
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex; \
	else \
		tectonic -X compile main.tex; \
	fi

watch:
	latexmk -pdf -pvc -interaction=nonstopmode main.tex

clean:
	latexmk -C
	rm -f main.bbl main.blg
