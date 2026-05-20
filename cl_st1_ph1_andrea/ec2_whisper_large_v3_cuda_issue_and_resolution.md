# EC2 Whisper Large v3 CUDA Runtime Issue and Resolution

## 1. Context

The transcription stage of the project uses:

```text
transcribe_commercials_whisper.py
```

to transcribe commercial audio files with:

```text
Whisper Large v3
```

through the:

```text
faster-whisper
```

backend.

The programme reads Whisper-ready audio files from:

```text
corpus/03_audio/
```

and writes transcript outputs to:

```text
corpus/04_transcripts/
```

Each successful transcription writes:

```text
corpus/04_transcripts/<Commercial ID>.txt
corpus/04_transcripts/<Commercial ID>.json
```

The programme was deployed on an EC2 GPU instance using CUDA acceleration.

---

## 2. Initial Problem

When running the transcription programme:

```bash
python transcribe_commercials_whisper.py
```

the programme started correctly, loaded metadata correctly, planned five test transcriptions, and downloaded/loaded the Whisper Large v3 model successfully.

The run reached this stage:

```text
Whisper model loaded successfully
Processing audio with duration 00:59.025
```

However, each transcription failed with the following error:

```text
Library libcublas.so.12 is not found or cannot be loaded
```

Example log output:

```text
ERROR FAILED tv_com_1950_1 error=Library libcublas.so.12 is not found or cannot be loaded
```

The same error occurred for all five test audio files.

---

## 3. Diagnosis

The error:

```text
Library libcublas.so.12 is not found or cannot be loaded
```

indicates that the NVIDIA CUDA cuBLAS runtime library required by the transcription backend was not available to the active Python environment.

This means:

- the Whisper model itself was downloaded successfully;
- `faster-whisper` was installed and importable;
- the programme logic was working;
- the error occurred at GPU inference time;
- the active environment could not locate the CUDA 12 cuBLAS shared library.

The missing library was:

```text
libcublas.so.12
```

This is part of the CUDA runtime stack required for GPU inference.

The warning:

```text
Failed to detect devices under "/sys/class/drm/card0"
```

also appeared, but it was not the cause of the failure. The actual blocking error was the missing cuBLAS library.

---

## 4. Solution

The solution was to install the required CUDA runtime libraries into the active conda environment and ensure that the environment library path was visible at runtime.

A dedicated conda environment for Whisper was used:

```bash
conda create -n whisper_lg_v3 python=3.11 -y
conda activate whisper_lg_v3
```

The transcription dependencies were installed:

```bash
conda install -c conda-forge faster-whisper tqdm -y
```

The CUDA runtime libraries were installed into the same environment:

```bash
conda install -c nvidia cuda-toolkit=12 -y
```

If needed, cuDNN can also be installed:

```bash
conda install -c conda-forge cudnn -y
```

Then the conda environment’s library directory was added to `LD_LIBRARY_PATH`:

```bash
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
```

This allowed the runtime linker to find libraries such as:

```text
libcublas.so.12
```

inside the active conda environment.

---

## 5. Making the Fix Persistent

To avoid needing to manually export `LD_LIBRARY_PATH` every time, the environment activation script was created:

```bash
mkdir -p "$CONDA_PREFIX/etc/conda/activate.d"
nano "$CONDA_PREFIX/etc/conda/activate.d/env_vars.sh"
```

The following line was added to the file:

```bash
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
```

After saving the file, the environment can be reactivated:

```bash
conda deactivate
conda activate whisper_lg_v3
```

The path can be checked with:

```bash
echo "$LD_LIBRARY_PATH"
```

The beginning of the output should include the conda environment library path, for example:

```text
/home/ubuntu/.../envs/whisper_lg_v3/lib
```

---

## 6. Successful Test After the Fix

After installing the CUDA runtime libraries and setting `LD_LIBRARY_PATH`, the same command was run again:

```bash
python transcribe_commercials_whisper.py
```

The programme successfully processed the default test batch of five commercials.

Successful log output included:

```text
Whisper model loaded successfully
Processing audio with duration 00:59.025
SUCCESS tv_com_1950_1 -> corpus/04_transcripts/tv_com_1950_1.txt
SUCCESS tv_com_1950_2 -> corpus/04_transcripts/tv_com_1950_2.txt
SUCCESS tv_com_1950_3 -> corpus/04_transcripts/tv_com_1950_3.txt
SUCCESS tv_com_1950_4 -> corpus/04_transcripts/tv_com_1950_4.txt
SUCCESS tv_com_1950_5 -> corpus/04_transcripts/tv_com_1950_5.txt
```

The final run summary was:

```text
Finished run: succeeded=5 failed=0 skipped_existing=0 missing_input=0 invalid_metadata=0
```

This confirmed that GPU transcription was working correctly.

---

## 7. Output Files Created

The successful test run created transcript outputs in:

```text
corpus/04_transcripts/
```

For example:

```text
corpus/04_transcripts/tv_com_1950_1.txt
corpus/04_transcripts/tv_com_1950_1.json
corpus/04_transcripts/tv_com_1950_2.txt
corpus/04_transcripts/tv_com_1950_2.json
```

The programme also wrote manifest files:

```text
corpus/04_transcripts/transcribe_commercials_whisper_manifest.json
corpus/04_transcripts/transcribe_commercials_whisper_manifest_20260520T141704Z.json
```

The latest manifest recorded the successful test run.

---

## 8. Notes on Remaining Warnings

The following warning appeared during transcription:

```text
Failed to detect devices under "/sys/class/drm/card0"
```

This warning did not prevent successful GPU transcription. Since the programme completed with:

```text
succeeded=5 failed=0
```

the warning can be ignored for now.

The Hugging Face warning:

```text
You are sending unauthenticated requests to the HF Hub.
```

is also not fatal. It only means that model downloads may be slower or subject to rate limits. The model was successfully downloaded and loaded.

If download reliability becomes an issue, a Hugging Face token can be configured later.

---

## 9. Final Working Setup

The working setup is:

```text
EC2 GPU instance
x86_64 architecture
Python 3.11 conda environment
faster-whisper
Whisper Large v3
CUDA 12 runtime libraries
LD_LIBRARY_PATH pointing to the conda environment lib directory
```

The key environment variable is:

```bash
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:$LD_LIBRARY_PATH"
```

The recommended active environment is:

```bash
conda activate whisper_lg_v3
```

---

## 10. Recommended Production Run

After confirming the test run, the full transcription can be launched with:

```bash
python transcribe_commercials_whisper.py --no-test-mode
```

For a long EC2 run, use `tmux`:

```bash
tmux new -s whisper
conda activate whisper_lg_v3
cd ~/cl_st1_andrea/cl_st1_ph1_andrea
python transcribe_commercials_whisper.py --no-test-mode
```

Detach from `tmux` with:

```text
Ctrl+B
D
```

Reattach later with:

```bash
tmux attach -t whisper
```

Alternatively, use `nohup`:

```bash
nohup python transcribe_commercials_whisper.py --no-test-mode \
  > whisper_transcription_output.log 2>&1 &
```

Monitor progress with:

```bash
tail -f whisper_transcription_output.log
```

or:

```bash
tail -f corpus/04_transcripts/transcribe_commercials_whisper.log
```

---

## 11. Summary

The failure was caused by a missing CUDA runtime dependency:

```text
libcublas.so.12
```

The problem was solved by:

1. using a dedicated Python 3.11 conda environment;
2. installing `faster-whisper`;
3. installing CUDA 12 runtime libraries into the same environment;
4. adding the conda environment library path to `LD_LIBRARY_PATH`;
5. making that environment variable persistent through a conda activation script.

After the fix, the test transcription run completed successfully:

```text
succeeded=5 failed=0
```

The EC2 instance is now ready for full Whisper Large v3 transcription.