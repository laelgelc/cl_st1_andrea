# Development Specification: `cca_results_extract.py`

## 1. Purpose

Develop a Python programme named **`cca_results_extract.py`** to extract the first two canonical-structure tables from a SAS HTML output file and save them as JSON files.

The programme must target the **selected section** titled:

```text
Canonical Structure
```

Within that section, it must scrape the first two relevant tables:

1. **Correlations Between the VAR Variables and Their Canonical Variables**
   - Output file: `cca_var.json`

2. **Correlations Between the WITH Variables and Their Canonical Variables**
   - Output file: `cca_with.json`

The programme should ignore earlier CCA coefficient tables and any later cross-correlation tables.

---

## 2. Input

### 2.1 Required input

The programme must accept one SAS HTML results file as input.

Example:

```bash
python cca_results_extract.py tv_commercials_cca-results.html
```

### 2.2 Optional output directory

The programme should optionally accept an output directory.

Example:

```bash
python cca_results_extract.py tv_commercials_cca-results.html --output-dir results
```

If no output directory is supplied, the JSON files should be written to the current working directory.

---

## 3. Output

The programme must produce two JSON files:

```text
cca_var.json
cca_with.json
```

### 3.1 `cca_var.json`

This file must contain the table titled:

```text
Correlations Between the VAR Variables and Their Canonical Variables
```

Expected logical structure:

```json
[
  {
    "Variable": "ver1",
    "V1": 0.7964,
    "V2": -0.4671,
    "V3": -0.0592,
    "V4": -0.0162,
    "V5": -0.2049,
    "V6": -0.044,
    "V7": -0.1029,
    "V8": -0.2987
  }
]
```

### 3.2 `cca_with.json`

This file must contain the table titled:

```text
Correlations Between the WITH Variables and Their Canonical Variables
```

Expected logical structure:

```json
[
  {
    "Variable": "vis1",
    "W1": -0.3279,
    "W2": 0.3432,
    "W3": 0.0982,
    "W4": -0.0416,
    "W5": 0.095,
    "W6": 0.2628,
    "W7": 0.8275,
    "W8": -0.0221
  }
]
```

---

## 4. Functional Requirements

### 4.1 Locate the selected section

The programme must identify the section headed:

```html
<div class="c proctitle">Canonical Structure</div>
```

Only tables appearing after this section heading should be considered.

### 4.2 Extract the first two matching tables

After locating the `Canonical Structure` section, the programme must extract the following two tables, in this order:

1. Table whose title/header contains:

```text
Correlations Between the VAR Variables and Their Canonical Variables
```

2. Table whose title/header contains:

```text
Correlations Between the WITH Variables and Their Canonical Variables
```

The programme must not accidentally extract:

```text
Correlations Between the VAR Variables and the Canonical Variables of the WITH Variables
```

or:

```text
Correlations Between the WITH Variables and the Canonical Variables of the VAR Variables
```

These are different tables and must be ignored.

---

## 5. Parsing Requirements

### 5.1 HTML parser

Use a robust HTML parsing method, preferably:

```text
BeautifulSoup
```

with either:

```text
html.parser
```

or:

```text
lxml
```

, with a preference for `lxml` over `html.parser`.

### 5.2 Table title detection

The programme should identify the table title from the first header row of each table.

For example, the relevant title may appear inside:

```html
<th class="c b header" colspan="9" scope="colgroup">
  Correlations Between the VAR Variables and Their Canonical Variables
</th>
```

The programme should normalise text before comparison by:

- stripping leading/trailing whitespace;
- replacing repeated whitespace with a single space;
- decoding HTML entities such as `&nbsp;`.

### 5.3 Header row extraction

The second header row contains the canonical-variable column names.

For the VAR table:

```text
V1, V2, V3, V4, V5, V6, V7, V8
```

For the WITH table:

```text
W1, W2, W3, W4, W5, W6, W7, W8
```

The first column has an empty header in the SAS HTML output and must be renamed to:

```text
Variable
```

### 5.4 Body row extraction

Each body row contains:

- one row header, e.g. `ver1`, `ver2`, `vis1`, `vis2`;
- numeric correlation values.

Example row:

```html
<tr>
  <th class="l rowheader" scope="row">ver1</th>
  <td class="r data">0.7964</td>
  <td class="r data" nowrap>-0.4671</td>
  ...
</tr>
```

This must become:

```json
{
  "Variable": "ver1",
  "V1": 0.7964,
  "V2": -0.4671
}
```

---

## 6. Data Conversion Requirements

### 6.1 Numeric values

All numeric table values must be converted to JSON numbers, not strings.

For example:

```json
"V1": 0.7964
```

not:

```json
"V1": "0.7964"
```

### 6.2 Missing values

If SAS missing values occur, such as:

```text
.
```

or empty cells, they should be represented as:

```json
null
```

### 6.3 Whitespace and non-breaking spaces

The programme must clean text extracted from HTML cells by:

- replacing `\xa0` with a normal space;
- trimming whitespace;
- collapsing multiple spaces.

---

## 7. JSON Format

The JSON files should use:

- UTF-8 encoding;
- one JSON array per file;
- pretty formatting with indentation.

Example:

```json
[
  {
    "Variable": "ver1",
    "V1": 0.7964,
    "V2": -0.4671
  },
  {
    "Variable": "ver2",
    "V1": 0.4395,
    "V2": 0.6405
  }
]
```

Recommended `json.dump` options:

```python
json.dump(data, file, ensure_ascii=False, indent=2)
```

---

## 8. Command-Line Interface

The programme should expose a small CLI.

### 8.1 Positional argument

```text
html_file
```

Path to the SAS HTML results file.

### 8.2 Optional argument

```text
--output-dir
```

Directory where `cca_var.json` and `cca_with.json` will be written.

Default:

```text
.
```

### 8.3 Example usage

```bash
python cca_results_extract.py output_cl_st1_ph4_andrea_CCA/tv_commercials_cca-results.html
```

```bash
python cca_results_extract.py output_cl_st1_ph4_andrea_CCA/tv_commercials_cca-results.html --output-dir output_cl_st1_ph4_andrea_CCA
```

---

## 9. Error Handling

The programme must raise clear errors in the following cases.

### 9.1 Input file does not exist

Example message:

```text
Input HTML file not found: path/to/file.html
```

### 9.2 Canonical Structure section not found

Example message:

```text
Could not find section titled 'Canonical Structure'.
```

### 9.3 VAR canonical-structure table not found

Example message:

```text
Could not find table: Correlations Between the VAR Variables and Their Canonical Variables
```

### 9.4 WITH canonical-structure table not found

Example message:

```text
Could not find table: Correlations Between the WITH Variables and Their Canonical Variables
```

### 9.5 Malformed table

If a table has no body rows or its number of headers does not match the number of data cells, the programme should fail with a descriptive `ValueError`.

Example:

```text
Malformed table 'Correlations Between the VAR Variables and Their Canonical Variables': expected 9 columns but found 8 in row ver1.
```

---

## 10. Recommended Internal Design

The script should be structured around small, testable functions.

Suggested functions:

```python
def normalise_text(value: str) -> str:
    ...
```

Normalises whitespace and HTML text.

```python
def parse_number(value: str) -> float | None:
    ...
```

Converts SAS table cell text to `float` or `None`.

```python
def find_canonical_structure_start(soup):
    ...
```

Finds the `Canonical Structure` heading.

```python
def find_target_table(start_node, target_title: str):
    ...
```

Finds a table after the selected section whose title exactly matches the target title.

```python
def extract_table(table) -> list[dict]:
    ...
```

Converts an HTML table into a list of dictionaries.

```python
def write_json(data: list[dict], output_path: Path) -> None:
    ...
```

Writes extracted rows to a JSON file.

```python
def main() -> None:
    ...
```

Handles command-line arguments and orchestration.

---

## 11. Exact Target Table Titles

The implementation should use exact normalised title matching.

```python
VAR_TABLE_TITLE = "Correlations Between the VAR Variables and Their Canonical Variables"

WITH_TABLE_TITLE = "Correlations Between the WITH Variables and Their Canonical Variables"
```

This exact matching is important because the same section contains later tables with similar but different titles.

---

## 12. Expected Row and Column Names

For the attached SAS output, the expected extracted structures are:

### 12.1 `cca_var.json`

Columns:

```text
Variable, V1, V2, V3, V4, V5, V6, V7, V8
```

Rows:

```text
ver1
ver2
ver3
ver4
ver5
ver6
ver7
ver8
```

### 12.2 `cca_with.json`

Columns:

```text
Variable, W1, W2, W3, W4, W5, W6, W7, W8
```

Rows:

```text
vis1
vis2
vis3
vis4
vis5
vis6
vis7
vis8
```

---

## 13. Acceptance Criteria

Development is complete when all of the following are true:

1. Running the programme on the SAS HTML file creates:

   ```text
   cca_var.json
   cca_with.json
   ```

2. `cca_var.json` contains only the table:

   ```text
   Correlations Between the VAR Variables and Their Canonical Variables
   ```

3. `cca_with.json` contains only the table:

   ```text
   Correlations Between the WITH Variables and Their Canonical Variables
   ```

4. Both JSON files contain arrays of objects.

5. The first column is named:

   ```text
   Variable
   ```

6. Canonical-variable columns are named exactly:

   ```text
   V1 ... V8
   ```

   and:

   ```text
   W1 ... W8
   ```

7. Numeric values are JSON numbers.

8. SAS missing values are represented as `null`.

9. The script does not extract the later cross-correlation tables in the same section.

10. Error messages are clear when required tables or sections are missing.