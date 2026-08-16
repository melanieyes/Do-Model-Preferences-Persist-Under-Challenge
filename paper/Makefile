.PHONY: all clean watch

all: apart_submit.pdf main_v2.pdf

# latexmk where a full TeX Live exists; tectonic otherwise (it fetches what it needs).
main.pdf: main.tex refs.bib $(wildcard *_stats.tex) $(wildcard sections/*.tex)
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex; \
	else \
		tectonic -X compile main.tex; \
	fi

# The submission artifact. main.tex stays the single source — this is a copy of
# its output, never a second document. Both PDFs are committed.
apart_submit.pdf: main.pdf
	cp main.pdf apart_submit.pdf
	@echo "submission artifact -> paper/apart_submit.pdf" 

watch:
	latexmk -pdf -pvc -interaction=nonstopmode main.tex

main_v2.pdf: main_v2.tex expl_stats.tex warmth_stats.tex expl_table1.tex
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error main_v2.tex; \
	else \
		tectonic -X compile main_v2.tex; \
	fi

clean:
	latexmk -C
	rm -f main.bbl main.blg apart_submit.pdf
