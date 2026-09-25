# Bug Report: Empty Loading-Word Lines Can Capture the Next Score Line

## Summary

The function `parse_score_details` that parses `score_details.txt` can incorrectly capture the next line after an empty loading-word list.

When a line such as:

```plain text
f1 neg words (N=0):
```


has no words after the colon, the parser may incorrectly treat the following line:

```plain text
f2 score: 13
```


as a loading word.

This produces incorrect output such as:

```plain text
Loading words (f1_neg), N=1: f2 score: 13
```


instead of the correct output:

```plain text
Loading words (f1_neg), N=0:
```


## Affected Code Pattern

The bug occurs in regex patterns like this:

```python
re.search(rf"f{f} neg words \(N=\d+\):\s*(.*)", block)
```


and similarly:

```python
re.search(rf"f{f} pos words \(N=\d+\):\s*(.*)", block)
```


The problem is the use of:

```python
\s*
```


immediately after the colon.

## Root Cause

In Python regular expressions, `\s` matches all whitespace characters, including:

- spaces
- tabs
- carriage returns
- newlines

Therefore, this pattern:

```python
:\s*(.*)
```


does not only consume spaces after the colon. It can also consume the newline after an empty loading-word line.

Given this input:

```plain text
f1 neg words (N=0): 

f2 score: 13
```


the regex can behave as follows:

1. Match `f1 neg words (N=0):`
2. Use `\s*` to consume:
   - the trailing space after the colon
   - the newline
   - the blank line
3. Let `(.*)` capture the next non-empty line:

```plain text
f2 score: 13
```


As a result, `f2 score: 13` is incorrectly parsed as if it were a loading word for `f1_neg`.

## Example of Incorrect Behavior

Source score details:

```plain text
text ID: t004077
filename: to/to_em_71.txt

f1 score: 2
f1 pos words (N=2): que, um
f1 neg words (N=0): 

f2 score: 13
f2 pos words (N=13): cursar, portaria, jovens, oferta, ofertar, legislação, conformidade, itinerário, vigente, tocantins, flexível, série, currículo
f2 neg words (N=0):
```


Incorrect parsed output:

```plain text
Loading words (f1_neg), N=1: f2 score: 13
```


Expected parsed output:

```plain text
Loading words (f1_neg), N=0:
```


## Impact

This bug affects cases where a `pos words` or `neg words` line has `N=0` and is followed by another non-empty line.

The practical effects are:

- Incorrect loading-word lists in generated example files.
- Misleading interpretation materials.
- False appearance that a score line is a key lemma.
- Inflated loading-word counts, e.g. `N=1` instead of `N=0`.
- Possible downstream interpretation errors if the generated examples are used for qualitative analysis or prompt generation.

The bug is especially likely to appear when parsing factor-pole combinations with no loading key lemmas.

## Affected Regex

Problematic form:

```python
rf"f{f} neg words \(N=\d+\):\s*(.*)"
```


Safer form:

```python
rf"^f{f} neg words \(N=\d+\):[ \t]*(.*)$"
```


Likewise for positive words:

```python
rf"^f{f} pos words \(N=\d+\):[ \t]*(.*)$"
```


## Recommended Fix

Replace `\s*` after the colon with `[ \t]*`, and anchor the regex to a single line using `^`, `$`, and `re.MULTILINE`.

Recommended implementation:

```python
def parse_score_details(path=SCORE_DETAILS):
    out = {}
    txt = path.read_text()
    blocks = txt.split("=============================================")

    for b in blocks:
        m = re.search(r"^text ID:[ \t]*(t\d+)[ \t]*$", b, flags=re.MULTILINE)
        if not m:
            continue

        tid = m.group(1)
        out[tid] = {}

        for f in range(1, 8):
            mp = re.search(
                rf"^f{f} pos words \(N=\d+\):[ \t]*(.*)$",
                b,
                flags=re.MULTILINE,
            )
            mn = re.search(
                rf"^f{f} neg words \(N=\d+\):[ \t]*(.*)$",
                b,
                flags=re.MULTILINE,
            )

            pos = mp.group(1).split(",") if mp else []
            neg = mn.group(1).split(",") if mn else []

            out[tid][f"f{f}_pos"] = [w.strip() for w in pos if w.strip()]
            out[tid][f"f{f}_neg"] = [w.strip() for w in neg if w.strip()]

    return out
```


## Why This Fix Works

The replacement:

```python
[ \t]*
```


matches only horizontal whitespace:

- spaces
- tabs

It does **not** match newlines.

Therefore, when the parser sees:

```plain text
f1 neg words (N=0): 

f2 score: 13
```


it captures only the empty text after the colon on the same line. It does not advance to the next line.

Adding anchors also makes the parser stricter:

```python
^
```


ensures the match starts at the beginning of a line.

```python
$
```


ensures the match ends at the end of that same line.

```python
flags=re.MULTILINE
```


makes `^` and `$` apply to individual lines inside the block rather than only to the full block.

## Validation Test Case

A minimal test case should confirm that empty loading-word lists remain empty.

```python
import re

block = """
text ID: t004077
filename: to/to_em_71.txt

f1 score: 2
f1 pos words (N=2): que, um
f1 neg words (N=0): 

f2 score: 13
f2 pos words (N=13): cursar, portaria
f2 neg words (N=0): 
"""

bad = re.search(r"f1 neg words \(N=\d+\):\s*(.*)", block)
good = re.search(
    r"^f1 neg words \(N=\d+\):[ \t]*(.*)$",
    block,
    flags=re.MULTILINE,
)

print("Bad parse:", bad.group(1))
print("Good parse:", repr(good.group(1)))
```


Expected output:

```plain text
Bad parse: f2 score: 13
Good parse: ''
```


## Recommended Follow-Up

1. Replace all score-detail parsing regexes of the form `:\s*(.*)` with `:[ \t]*(.*)$` where line-local parsing is intended.
2. Add a regression test for `N=0` loading-word lines.
3. Regenerate affected example files.
4. Optionally scan generated outputs for suspicious loading words containing strings like:
   - `score:`
   - `f2 score`
   - `f3 score`
   - `f4 score`
   - etc.

## Status

The bug is confirmed and the fix is straightforward: prevent `\s*` from consuming newlines by using `[ \t]*` and line anchors.