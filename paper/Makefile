.PHONY: all clean watch

# apart_submit.tex is the single source and apart_submit.pdf is the submission
# artifact, built directly from it. There is no main.tex and no main.pdf: the two
# were the same document compiled once and copied, which meant every rebuild
# produced two files that had to be kept in step by hand.
all: apart_submit.pdf

# latexmk where a full TeX Live exists; tectonic otherwise (it fetches what it needs).
apart_submit.pdf: apart_submit.tex refs.bib $(wildcard *_stats.tex) $(wildcard *_table1.tex) $(wildcard sections/*.tex)
	@if command -v latexmk >/dev/null 2>&1; then \
		latexmk -pdf -interaction=nonstopmode -halt-on-error apart_submit.tex; \
	else \
		tectonic -X compile apart_submit.tex; \
	fi
	@echo "submission artifact -> paper/apart_submit.pdf"

watch:
	latexmk -pdf -pvc -interaction=nonstopmode apart_submit.tex

clean:
	latexmk -C || true
	rm -f apart_submit.aux apart_submit.bbl apart_submit.blg apart_submit.log \
	      apart_submit.out apart_submit.fls apart_submit.fdb_latexmk
