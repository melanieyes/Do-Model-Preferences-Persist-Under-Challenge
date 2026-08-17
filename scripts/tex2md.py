"""Render the submission LaTeX to Markdown for co-author review.

Every number in the output comes from the generated *_stats.tex macros, so the
Markdown cannot drift from the analysis output the way a hand-typed copy would.
"""
import re
import pathlib

PAPER = pathlib.Path("/Users/coherenteyes/Does-It-Matter-to-a-Model-How-It-Is-Moved-/paper")

# ---------------------------------------------------------------- macros
macros = {}
for f in PAPER.glob("*_stats.tex"):
    for name, val in re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", f.read_text()):
        macros[name] = val


def expand_macros(s, rounds=4):
    for _ in range(rounds):
        new = re.sub(r"\\(\w+)\{\}", lambda m: macros.get(m.group(1), m.group(0)), s)
        new = re.sub(r"\\num\{([^}]*)\}", r"\1", new)
        if new == s:
            break
        s = new
    return s


# ---------------------------------------------------------------- bib
def split_authors(field):
    """Split on ' and ' at brace depth 0, so {Anthropic ... Team} stays whole."""
    out, buf, depth = [], "", 0
    for tok in re.split(r"(\{|\}|\s+and\s+)", field.replace("\n", " ")):
        if tok == "{":
            depth += 1
        elif tok == "}":
            depth -= 1
        if re.fullmatch(r"\s+and\s+", tok or "") and depth == 0:
            out.append(buf.strip())
            buf = ""
        else:
            buf += tok or ""
    out.append(buf.strip())
    return [a for a in out if a]


bib = {}
for entry in re.split(r"\n@", PAPER.joinpath("refs.bib").read_text())[1:]:
    key = re.search(r"\{([^,]+),", entry).group(1)
    year = re.search(r"year\s*=\s*\{(\d{4})\}", entry)
    authors = re.search(r"author\s*=\s*\{(.*?)\}\s*,\s*\n\s*(?:journal|title|book|year|note|url|how)", entry, re.S)
    if not authors:
        authors = re.search(r"author\s*=\s*\{(.*?)\}\s*,", entry, re.S)
    names = split_authors(authors.group(1)) if authors else []
    # {Braced Name} is a corporate author and is never split into first/last.
    surnames = [n.strip("{}") if n.startswith("{") else
                (n.split(",")[0].strip() if "," in n else n.split()[-1])
                for n in names if n]
    if not surnames:
        label = "Anon."
    elif len(surnames) == 1:
        label = surnames[0]
    elif len(surnames) == 2:
        label = f"{surnames[0]} and {surnames[1]}"
    else:
        label = f"{surnames[0]} et al."
    bib[key] = (label, year.group(1) if year else "n.d.")


def cite(keys, paren):
    parts = []
    for k in [k.strip() for k in keys.split(",")]:
        label, year = bib.get(k, (k, "n.d."))
        parts.append(f"{label}, {year}" if paren else f"{label} ({year})")
    return f"({'; '.join(parts)})" if paren else "; ".join(parts)


# ---------------------------------------------------------------- source
src = PAPER.joinpath("apart_submit.tex").read_text()
body = src[src.index(r"\begin{document}"):]
body = re.sub(r"\\input\{(sections/[^}]+)\}",
              lambda m: PAPER.joinpath(m.group(1) + ".tex").read_text(), body)
abstract = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", body, re.S).group(1)
body = body[body.index(r"\end{abstract}") + len(r"\end{abstract}"):]
body_src = body  # pre-conversion copy, for collecting \cite keys

# ---------------------------------------------------------------- numbering
fig_no, tab_no, sec_no = {}, {}, {}
n = 0
for m in re.finditer(r"\\begin\{figure\}.*?\\label\{([^}]+)\}.*?\\end\{figure\}", body, re.S):
    n += 1
    fig_no[m.group(1)] = n
n = 0
for m in re.finditer(r"\\begin\{table\}.*?\\label\{([^}]+)\}.*?\\end\{table\}", body, re.S):
    n += 1
    tab_no[m.group(1)] = n
# Headings carry one or more stacked \label lines; every one of them resolves to
# the number of the heading it sits under.
# Walk headings and labels in document order. A label may sit on its own line
# well below its heading; it still belongs to the heading it falls under.
sec, sub = 0, 0
num, title = "0", ""
for m in re.finditer(r"\\(section|subsection)\*?\{([^}]*)\}|\\label\{([^}]+)\}", body):
    if m.group(3):
        if m.group(3) not in fig_no and m.group(3) not in tab_no:
            sec_no.setdefault(m.group(3), (num, title))
        continue
    title = m.group(2)
    if m.group(1) == "section":
        sec, sub = sec + 1, 0
        num = str(sec)
    else:
        sub += 1
        num = f"{sec}.{sub}"


def ref(label):
    if label in fig_no:
        return f"Figure {fig_no[label]}"
    if label in tab_no:
        return f"Table {tab_no[label]}"
    if label in sec_no:
        return f"Section {sec_no[label][0]} ({sec_no[label][1]})"
    return f"[{label}]"


# ---------------------------------------------------------------- blocks
def do_figure(m):
    block = m.group(0)
    img = re.search(r"\\includegraphics\[[^\]]*\]\{([^}]+)\}", block)
    cap = re.search(r"\\caption\{(.*?)\}\s*\n\s*\\label", block, re.S)
    lab = re.search(r"\\label\{([^}]+)\}", block)
    num = fig_no.get(lab.group(1), "?") if lab else "?"
    out = f"\n![Figure {num}](figures/{img.group(1)})\n" if img else "\n"
    if cap:
        out += f"\n**Figure {num}.** {inline(cap.group(1))}\n"
    return out


def do_table(m):
    block = m.group(0)
    cap = re.search(r"\\caption\{(.*?)\}\s*\n\s*\\label", block, re.S)
    lab = re.search(r"\\label\{([^}]+)\}", block)
    num = tab_no.get(lab.group(1), "?") if lab else "?"
    inner = re.search(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}", block, re.S).group(1)
    inner = re.sub(r"\\(top|mid|bottom)rule", "", inner)
    rows = []
    for raw in inner.split(r"\\"):
        raw = raw.strip()
        if not raw:
            continue
        cells = [inline(" ".join(c.split())) for c in raw.split("&")]
        rows.append(cells)
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    out = ["", "| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    for r in rows[1:]:
        out.append("| " + " | ".join(r) + " |")
    out.append("")
    out.append(f"**Table {num}.** {inline(cap.group(1))}" if cap else "")
    return "\n".join(out) + "\n"


def inline(s):
    s = expand_macros(s)
    s = re.sub(r"\\citet\{([^}]*)\}", lambda m: cite(m.group(1), False), s)
    s = re.sub(r"\\citep\{([^}]*)\}", lambda m: cite(m.group(1), True), s)
    s = re.sub(r"\\(?:ref|autoref)\{([^}]*)\}", lambda m: ref(m.group(1)), s)
    s = re.sub(r"\\texttt\{([^}]*)\}", r"`\1`", s)
    s = re.sub(r"\\(?:emph|textit)\{([^}]*)\}", r"*\1*", s)
    s = re.sub(r"\\textbf\{([^}]*)\}", r"**\1**", s)
    s = re.sub(r"\\(?:footnote|thanks)\{([^}]*)\}", r" [\1]", s)
    s = re.sub(r"\$\\Delta\$", "Δ", s)
    s = s.replace(r"\Delta", "Δ").replace(r"\times", "×").replace(r"\pm", "±")
    s = re.sub(r"\$([^$]*)\$", r"\1", s)
    s = s.replace("---", "—").replace("--", "–")
    s = s.replace("``", '"').replace("''", '"')
    s = re.sub(r"\\[%#&_$]", lambda m: m.group(0)[1], s)
    s = s.replace("~", " ").replace(r"\,", " ").replace(r"\ ", " ")
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    return re.sub(r"[ \t]+", " ", s).strip()


body = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", do_figure, body, flags=re.S)
body = re.sub(r"\\begin\{table\}.*?\\end\{table\}", do_table, body, flags=re.S)
body = re.sub(r"\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}",
              lambda m: "\n`" + inline(m.group(1)) + "`\n", body, flags=re.S)
body = re.sub(r"\\begin\{(itemize|enumerate)\}|\\end\{(itemize|enumerate)\}", "", body)
body = re.sub(r"(?m)^\s*\\item\s*", "- ", body)
body = re.sub(r"\\(clearpage|newpage|maketitle|bibliographystyle\{[^}]*\}|bibliography\{[^}]*\}"
              r"|end\{document\}|appendix|setcounter\{[^}]*\}\{[^}]*\})", "", body)

out = []
for para in re.split(r"\n\s*\n", body):
    para = para.strip()
    if not para or para.startswith("%"):
        continue
    para = "\n".join(l for l in para.split("\n") if not l.strip().startswith("%"))
    if not para.strip():
        continue
    m = re.match(r"\\section\*?\{(.*?)\}(.*)", para, re.S)
    if m:
        rest = re.sub(r"\\label\{[^}]*\}", "", m.group(2)).strip()
        out.append("## " + inline(m.group(1)))
        if rest:
            out.append(inline(rest))
        continue
    m = re.match(r"\\subsection\*?\{(.*?)\}(.*)", para, re.S)
    if m:
        rest = re.sub(r"\\label\{[^}]*\}", "", m.group(2)).strip()
        out.append("### " + inline(m.group(1)))
        if rest:
            out.append(inline(rest))
        continue
    m = re.match(r"\\paragraph\{(.*?)\}(.*)", para, re.S)
    if m:
        out.append("**" + inline(m.group(1)) + "** " + inline(m.group(2)))
        continue
    if para.startswith("|") or para.startswith("![") or para.startswith("**Figure") \
            or para.startswith("**Table") or para.startswith("- "):
        out.append(expand_macros(para) if para.startswith(("|", "![", "**")) else inline(para))
        continue
    out.append(inline(para))

# ---------------------------------------------------------------- references
# BibTeX prints only cited works, so the Markdown list must match the PDF's.
cited = set()
for keys in re.findall(r"\\cite[a-z]*\{([^}]*)\}", src + body_src):
    cited.update(k.strip() for k in keys.split(","))

refs = []
for key, (label, year) in bib.items():
    if key not in cited:
        continue
    entry = re.search(r"@\w+\{" + re.escape(key) + r",(.*?)\n\}", PAPER.joinpath("refs.bib").read_text(), re.S).group(1)

    def field(name):
        m = re.search(name + r"\s*=\s*\{(.*?)\}\s*(?:,|\n\s*\})", entry, re.S)
        return " ".join(m.group(1).split()) if m else ""

    authors = field("author")
    names = split_authors(authors) if authors else []
    apa = []
    for nm in names:
        if nm.startswith("{"):          # corporate author — printed verbatim
            apa.append(nm.strip("{}"))
            continue
        if "," in nm:
            last, first = [p.strip() for p in nm.split(",", 1)]
        else:
            parts = nm.split()
            last, first = parts[-1], " ".join(parts[:-1])
        initials = " ".join(p[0] + "." for p in first.split() if p)
        apa.append(f"{last}, {initials}".strip().rstrip(","))
    who = ", ".join(apa[:-1]) + ", and " + apa[-1] if len(apa) > 1 else (apa[0] if apa else "")
    venue = field("journal") or field("booktitle") or field("note") or field("howpublished")
    url = field("url")
    line = f"{who} ({year}). {field('title')}."
    if venue:
        line += f" {venue}."
    if url:
        line += f" {url}"
    line = line.replace("{", "").replace("}", "").replace(", and others", ", et al.")
    refs.append((who or field("title"), line))

# ---------------------------------------------------------------- write
head = [
    "# Do Model Preferences Persist Under Challenge?",
    "",
    "Melanie Bui (Fulbright University Vietnam) · Haein Kong (Rutgers University)",
    "",
    "Apart Research Digital Mind Hackathon, 2026",
    "",
    "> Markdown rendering of `paper/apart_submit.tex`, generated by "
    "`scripts/tex2md.py`. The PDF is the submission artifact; every number here is "
    "substituted from the generated `*_stats.tex` macros, so the two cannot diverge.",
    "",
    "## Abstract",
    "",
    inline(abstract),
    "",
]
text = "\n".join(head) + "\n" + "\n\n".join(out)
text += "\n\n## References\n\n" + "\n\n".join(f"{i}. {line}" for i, (_, line) in enumerate(sorted(refs, key=lambda r: r[0].lower()), 1))
text = re.sub(r"\n{3,}", "\n\n", text) + "\n"
PAPER.joinpath("apart_submit.md").write_text(text)
print(f"wrote apart_submit.md — {len(text.split())} words, {text.count(chr(10))} lines")
leftover = sorted(set(re.findall(r"\\[a-zA-Z]+", text)))
print("leftover latex:", leftover if leftover else "none")
