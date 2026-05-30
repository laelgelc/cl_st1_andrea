#!/usr/bin/env python3
from pathlib import Path

# Paths
index_file = Path("index_keywords.txt")
out_dir = Path("sas")
out_dir.mkdir(exist_ok=True)

def sas_escape(s: str) -> str:
    # SAS escapes a double-quote inside a quoted string by doubling it.
    return s.replace('"', '""')

# Read index_keywords.txt
with index_file.open("r", encoding="utf-8") as f:
    lines = [line.strip().split(maxsplit=1) for line in f if line.strip()]
    items = [(f"v{idx}", sas_escape(keyword)) for idx, keyword in lines]

# (1) Full format with keyword and ID
with (out_dir / "word_labels_full_format.sas").open("w", encoding="utf-8") as f:
    f.write("PROC FORMAT library=work ;\n")
    f.write("  VALUE  $lexlabelsfull\n")
    for varname, word in items:
        f.write(f'"{varname}" = "{word} ({varname})"\n')
    f.write(";\nrun;\nquit;\n")

# (2) Short format with just keyword
with (out_dir / "word_labels_format.sas").open("w", encoding="utf-8") as f:
    f.write("PROC FORMAT library=work ;\n")
    f.write("  VALUE  $lexlabels\n")
    for varname, word in items:
        f.write(f'"{varname}" = "{word}"\n')
    f.write(";\nrun;\nquit;\n")