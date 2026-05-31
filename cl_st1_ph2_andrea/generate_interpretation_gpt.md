# Development Specification: `generate_interpretation_gpt.py`

## 1. Programme Purpose

`generate_interpretation_gpt.py` sends prepared LMDA interpretation prompt files to an OpenAI GPT model and saves the generated interpretations as text files.

The programme reads prompt files from:

```text
interpretation/input
```

and writes model responses to:

```text
interpretation/output
```

Each input prompt file is sent as one complete user prompt. Each output file uses the same filename as the corresponding input file.

The programme is intended to automate the interpretation-generation step after prompt files have been prepared by `interpretation_prompts.py`.

---

## 2. Project Context

The project analyses commercial subcorpora organised by decade:

```text
1950
1960
1970
1980
1990
2000
2010
2020
```

The programme is used in both:

1. **Phase 2: commercial verbal subcorpus**
    - transcript texts of spoken/audio-verbal commercial content;

2. **Phase 3: commercial visual subcorpus**
    - textual descriptions of commercial visual content.

The programme is expected to live in the project phase directory as:

```text
generate_interpretation_gpt.py
```

Example:

```text
cl_st1_ph2_andrea/generate_interpretation_gpt.py
cl_st1_ph3_andrea/generate_interpretation_gpt.py
```

By default, the project name is inferred from the current working directory for status reporting.

Example:

```text
cl_st1_ph2_andrea
```

infers:

```text
cl_st1_ph2_andrea
```

---

## 3. Inputs

### 3.1 Prompt Input Directory

Default input directory:

```text
interpretation/input
```

The directory must contain one or more prompt files:

```text
*.txt
```

Expected filenames:

```text
f<n>_<pole>.txt
```

Examples:

```text
interpretation/input/f1_pos.txt
interpretation/input/f1_neg.txt
interpretation/input/f2_pos.txt
```

Each file is read as UTF-8 text and sent to the GPT model as a single user message.

### 3.2 OpenAI API Key

The programme requires:

```text
OPENAI_API_KEY
```

The key may be supplied by either:

1. the system environment; or
2. a project-local dotenv file:

```text
env/.env
```

Expected dotenv format:

```text
OPENAI_API_KEY=...
```

The system environment takes precedence if the variable is already set.

### 3.3 OpenAI SDK

The active Python environment must provide the OpenAI SDK.

The programme uses the OpenAI Responses API.

### 3.4 Command-Line Arguments

The programme must support:

```text
--input
-i
```

Default:

```text
interpretation/input
```

```text
--output
-o
```

Default:

```text
interpretation/output
```

```text
--model
-m
```

Default:

```text
gpt-5.5
```

```text
--max-output-tokens
-t
```

Default:

```text
9000
```

```text
--workers
```

Default:

```text
4
```

```text
--skip-existing
```

Default:

```text
enabled
```

```text
--no-skip-existing
```

Reprocesses prompts even if output files already exist.

```text
--retries
```

Default:

```text
5
```

```text
--retry-base-sleep
```

Default:

```text
2.0
```

---

## 4. Outputs

### 4.1 Output Directory

Default output directory:

```text
interpretation/output
```

The programme must create this directory if it does not exist.

### 4.2 Generated Interpretation Files

For each processed input prompt file:

```text
interpretation/input/<filename>.txt
```

the programme writes:

```text
interpretation/output/<filename>.txt
```

Example:

```text
interpretation/input/f1_pos.txt
```

produces:

```text
interpretation/output/f1_pos.txt
```

### 4.3 Output Encoding

All response files must be written using:

```text
UTF-8
```

### 4.4 Console Output

The programme must print progress and summary information, including:

1. project name;
2. input directory;
3. output directory;
4. model name;
5. whether temperature is sent;
6. number of prompts submitted;
7. worker activity;
8. final success/failure count;
9. failed prompt names, if any.

---

## 5. Functional Requirements

### 5.1 Project Name for Reporting

The programme must infer the project name from:

```python
Path.cwd().name
```

The inferred project name is used for console reporting only.

### 5.2 Environment Loading

Before checking for the API key, the programme must load environment variables from:

```text
env/.env
```

without overriding variables that already exist in the system environment.

If `OPENAI_API_KEY` is unavailable after this step, the programme must exit with an error.

### 5.3 OpenAI SDK Import

The programme must attempt to import the OpenAI SDK.

If the SDK is unavailable, it must print an explanatory error message and exit with a non-zero status.

### 5.4 Input Directory Validation

The input path supplied by `--input` must exist and must be a directory.

If it does not exist or is not a directory, the programme must exit with an error.

### 5.5 Output Directory Creation

The output directory supplied by `--output` must be created before processing prompts.

### 5.6 Argument Validation

The programme must validate:

```text
--workers > 0
--max-output-tokens > 0
--retries >= 0
--retry-base-sleep >= 0
```

If any validation fails, the programme must exit with an error.

### 5.7 Discover Prompt Files

The programme must discover prompt files using:

```text
<input-dir>/*.txt
```

Prompt files must be sorted alphabetically by path/name.

If no prompt files are found, print:

```text
No prompt files found.
```

and exit successfully.

### 5.8 Skip Existing Outputs

By default, the programme must skip any input prompt whose corresponding output file already exists.

Example:

```text
input:  interpretation/input/f1_pos.txt
output: interpretation/output/f1_pos.txt
```

If the output exists and skip-existing is enabled, this prompt is not submitted.

If all prompts are skipped, print:

```text
Nothing to do: all outputs already exist.
```

and exit successfully.

If `--no-skip-existing` is supplied, existing outputs must be overwritten.

### 5.9 Read Prompt File

Each prompt file must be read as UTF-8 text with decoding errors ignored.

After reading, leading and trailing whitespace must be stripped.

If the resulting prompt is empty, the individual task must fail and be reported as failed.

### 5.10 API Request Structure

Each prompt must be sent as a single user message through the OpenAI Responses API.

The request must include:

```text
model
input
max_output_tokens
```

The input must contain one message:

```text
role: user
content: <full prompt text>
```

### 5.11 Temperature Handling

The programme must determine whether to send a `temperature` parameter based on the selected model.

For models whose name starts with:

```text
gpt-5
```

the programme must not send `temperature`.

For other models, the programme should send:

```text
temperature = 0.0
```

The programme must print whether temperature is sent.

### 5.12 Response Handling

The programme must extract text from the API response.

If the response text is missing, not a string, or empty after stripping, the API call must be treated as failed.

Valid response text must be stripped and written to the output file.

### 5.13 Retry Logic

Each API call must be retried for transient errors.

A transient error is identified by the exception class name or message containing markers such as:

```text
rate
timeout
temporar
connection
server
service unavailable
gateway
429
500
502
503
504
```

For transient errors, the programme must retry up to:

```text
--retries
```

times after the initial attempt.

Default:

```text
5 retries
```

### 5.14 Exponential Backoff with Jitter

Between retry attempts, the programme must sleep using exponential backoff:

```text
sleep = retry_base_sleep * 2^attempt
```

A random jitter multiplier between approximately:

```text
0.8
```

and:

```text
1.2
```

must be applied.

The programme should print a warning before each retry.

### 5.15 Non-Transient Errors

If an error is not considered transient, the programme must not retry it.

The prompt task must fail.

### 5.16 Fresh Client Per Task

Each prompt-processing task must create its own OpenAI client for API calls.

This avoids relying on shared client thread-safety.

### 5.17 Parallel Processing

The programme must process prompts using a thread pool.

The maximum number of concurrent workers is controlled by:

```text
--workers
```

Default:

```text
4
```

Each prompt is independent.

### 5.18 Per-Prompt Failure Handling

If one prompt fails, the programme must:

1. report the error;
2. mark that prompt as failed;
3. continue processing other prompts.

### 5.19 Final Failure Behaviour

At the end of processing:

- if all processed prompts succeed, exit successfully;
- if any prompt fails, print the failed prompt names and exit with an error.

---

## 6. Output Content Requirements

### 6.1 Output Filename Preservation

Each output file must use exactly the same filename as the input prompt.

Example:

```text
f1_pos.txt -> f1_pos.txt
```

### 6.2 Output File Content

Each output file must contain only the model response text.

It must not include:

- the original prompt;
- console logs;
- API metadata;
- retry warnings;
- wrapper JSON.

### 6.3 Output Directory Layout

Typical output structure:

```text
interpretation/output/
  f1_pos.txt
  f1_neg.txt
  f2_pos.txt
  f2_neg.txt
```

### 6.4 Failed Prompt Outputs

If a prompt fails, the programme should not write a partial output file unless a valid response was received.

---

## 7. Error Handling Requirements

### 7.1 Missing OpenAI SDK

If the OpenAI SDK is unavailable, print an explanatory error and exit with a non-zero status.

### 7.2 Missing API Key

If `OPENAI_API_KEY` is not available from the system environment or `env/.env`, exit with an error.

### 7.3 Invalid Input Directory

If the input path does not exist or is not a directory, exit with an error.

### 7.4 Invalid Worker Count

If:

```text
--workers <= 0
```

exit with an error.

### 7.5 Invalid Max Output Tokens

If:

```text
--max-output-tokens <= 0
```

exit with an error.

### 7.6 Invalid Retry Count

If:

```text
--retries < 0
```

exit with an error.

### 7.7 Invalid Retry Base Sleep

If:

```text
--retry-base-sleep < 0
```

exit with an error.

### 7.8 No Prompt Files

If the input directory contains no `.txt` files, print a message and exit successfully.

### 7.9 All Outputs Already Exist

If all outputs already exist and skip-existing is enabled, print a message and exit successfully.

### 7.10 Empty Prompt File

If a prompt file is empty after stripping whitespace, mark that prompt as failed and continue processing other prompts.

### 7.11 Empty API Response

If the API returns no usable output text, mark that prompt as failed.

### 7.12 API or Network Failure

If an API or network failure is transient, retry according to the retry settings.

If retries are exhausted, mark the prompt as failed.

### 7.13 Non-Transient API Failure

If an API error is not transient, do not retry and mark the prompt as failed.

### 7.14 Some Prompts Failed

If one or more prompts fail, print their filenames and exit with an error after all other prompts complete.

---

## 8. Non-Functional Requirements

### 8.1 Encoding

All input and output files must use:

```text
UTF-8
```

Input decoding errors should be ignored.

### 8.2 Determinism

The programme must be deterministic in file discovery and output mapping:

- input files sorted by filename;
- output filenames identical to input filenames;
- skip-existing behaviour stable.

The generated interpretation text itself may vary depending on the model, service behaviour, or retry timing.

### 8.3 Concurrency Safety

Parallel workers must not write to the same output file.

Because each input maps to one distinct output filename, concurrent writes are safe as long as prompt filenames are unique.

### 8.4 No Input Mutation

The programme must not modify:

```text
interpretation/input/
env/.env
```

### 8.5 Output Overwrite Behaviour

By default, existing output files are skipped.

If:

```text
--no-skip-existing
```

is supplied, existing output files may be overwritten.

### 8.6 API Key Safety

The programme must not print the value of:

```text
OPENAI_API_KEY
```

or include it in output files.

### 8.7 Dependency Requirements

The programme depends on:

```text
openai
python-dotenv
```

It also uses Python standard-library modules including:

```text
argparse
os
random
sys
time
concurrent.futures
pathlib
```

The programme must run under the project Python environment.

---

## 9. Downstream Usage

The generated interpretation files are intended for human review and possible inclusion in project reports.

Typical output:

```text
interpretation/output/f1_pos.txt
interpretation/output/f1_neg.txt
```

The files represent model-generated interpretations of individual LMDA factor poles.

They may be edited manually before use in final analysis or documentation.

---

## 10. Acceptance Criteria

The programme is correct if:

1. It can be run from the project root using:

```shell
python generate_interpretation_gpt.py
```

2. It accepts an explicit input directory:

```shell
python generate_interpretation_gpt.py --input interpretation/input
```

3. It accepts an explicit output directory:

```shell
python generate_interpretation_gpt.py --output interpretation/output
```

4. It accepts an explicit model name:

```shell
python generate_interpretation_gpt.py --model gpt-5.5
```

5. It accepts an explicit worker count:

```shell
python generate_interpretation_gpt.py --workers 4
```

6. It accepts an explicit output token limit:

```shell
python generate_interpretation_gpt.py --max-output-tokens 9000
```

7. It skips existing outputs by default.

8. It reprocesses existing outputs when called with:

```shell
python generate_interpretation_gpt.py --no-skip-existing
```

9. It accepts retry configuration:

```shell
python generate_interpretation_gpt.py --retries 5 --retry-base-sleep 2.0
```

10. It loads `OPENAI_API_KEY` from either the system environment or:

```text
env/.env
```

11. It validates input directory and numeric arguments.

12. It discovers `.txt` prompt files under the input directory.

13. It maps each input file to an output file with the same name.

14. It sends each prompt as one user message.

15. It omits `temperature` for GPT-5-family models.

16. It sends `temperature = 0.0` for non-GPT-5-family models.

17. It retries transient failures with exponential backoff and jitter.

18. It continues processing other prompts if one prompt fails.

19. It reports failed prompts at the end.

20. It exits with an error if any prompt failed.

21. It writes UTF-8 response files.

22. It never prints the API key.

---

## 11. Example

### Input

Prompt directory:

```text
interpretation/input
```

Example files:

```text
interpretation/input/f1_pos.txt
interpretation/input/f1_neg.txt
```

Example prompt content:

```text
You are a corpus linguist specialising in Lexical Multi-Dimensional Analysis (LMDA).

Interpret Factor f1 (pos) as a discourse dimension.

=== MEAN DECADE SCORES ===
decade	Mean fac1
1950	0.42
1960	-0.18

=== FACTOR LOADINGS (f1_pos) ===
buy (0.41), save (0.38), new (0.36)

=== EXAMPLE EXCERPTS ===
...
```

Environment:

```text
OPENAI_API_KEY=...
```

or:

```text
env/.env
```

containing:

```text
OPENAI_API_KEY=...
```

### Command

```shell
python generate_interpretation_gpt.py
```

### Equivalent Explicit Command

```shell
python generate_interpretation_gpt.py \
  --input interpretation/input \
  --output interpretation/output \
  --model gpt-5.5 \
  --workers 4 \
  --max-output-tokens 9000 \
  --skip-existing \
  --retries 5 \
  --retry-base-sleep 2.0
```

### Output

```text
interpretation/output/f1_pos.txt
interpretation/output/f1_neg.txt
```

### Console Summary Example

```text
Project: cl_st1_ph2_andrea
Input directory: interpretation/input
Output directory: interpretation/output
Model: gpt-5.5
Temperature sent: False
Submitting 2 prompts using 4 workers…
[WORKER] Reading f1_pos.txt
[WORKER] Sending to GPT: f1_pos.txt
[WORKER] Saved → interpretation/output/f1_pos.txt

Done. Succeeded: 2/2
```

---

## 12. Recommended Future Enhancements

These are optional and must not alter current default behaviour unless explicitly requested.

### 12.1 Dry Run Mode

Expose:

```text
--dry-run
```

to list prompts that would be processed without calling the API.

### 12.2 Cost and Token Logging

Record estimated or actual token usage per prompt if returned by the API.

Possible output:

```text
interpretation/output/usage_log.tsv
```

### 12.3 Manifest

Write:

```text
interpretation/output/generation_manifest.json
```

containing:

- project;
- input directory;
- output directory;
- model;
- prompt files processed;
- skipped files;
- failed files;
- timestamp.

### 12.4 Per-Prompt Error Logs

Write failed prompt diagnostics to:

```text
interpretation/output/errors/
```

Example:

```text
interpretation/output/errors/f1_pos.error.txt
```

### 12.5 Recursive Input Discovery

Expose:

```text
--recursive
```

to discover prompt files in nested input directories.

### 12.6 Configurable Temperature

Expose:

```text
--temperature
```

for models that support it.

Current required behaviour uses `0.0` for non-GPT-5-family models and omits the parameter for GPT-5-family models.

### 12.7 Rate Limit Throttling

Expose:

```text
--requests-per-minute
```

to limit concurrent API calls under strict rate limits.

---

## 13. Summary

`generate_interpretation_gpt.py` submits prepared LMDA interpretation prompts to an OpenAI GPT model and saves the generated responses.

Its core responsibility is:

```text
For each prompt file, call the OpenAI Responses API and write the model response to a matching output file.
```

It must preserve:

- prompt-to-output filename mapping;
- UTF-8 file handling;
- skip-existing default behaviour;
- retry handling for transient failures;
- parallel prompt processing;
- API key safety;
- compatibility across Phase 2 and Phase 3.