.PHONY: all clean watch

# main.tex is the single source. apart_submit.pdf is the submission artifact and
# is a copy of its output — never a second document.
all: apart_submit.pdf

# latexmk where a full TeX Live exists; tectonic otherwise (it fetches what it needs).
main.pdf: main.tex refs.bib $(wildcard *_stats.tex) $(wildcard *_table1.tex) $(wildcard sections/*.tex)
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex; \
	else \
		tectonic -X compile main.tex; \
	fi

apart_submit.pdf: main.pdf
	cp main.pdf apart_submit.pdf
	@echo "submission artifact -> paper/apart_submit.pdf"

watch:
	latexmk -pdf -pvc -interaction=nonstopmode main.tex

clean:
	latexmk -C || true
	rm -f main.aux main.bbl main.blg main.log main.out main.fls main.fdb_latexmk
