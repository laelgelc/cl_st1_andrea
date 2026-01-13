# 📺 Multimodal Corpus & Analysis Pipeline (IVACS 2026 — Malta)

This project builds a **diachronic multimodal corpus** of 800 television commercials (100 per decade), sourced from YouTube compilations and segmented into individual video files. The corpus is divided into two coordinated components: a **verbal subcorpus** and a **visual subcorpus**. These feed into a series of analytical stages culminating in multimodal discourse profiles and statistical validation.

---

## 📦 Corpus Overview

- **800 commercials**, sampled evenly across decades  
- **Two subcorpora**:  
  - **Verbal**: transcripts of spoken language  
  - **Visual**: frame‑based descriptions of visual content  

---

## 🧩 Processing & Analysis Pipeline

### 1. **Verbal Subcorpus**
Textual transcripts of all commercials.

- **Methods**
  - Video → audio extraction  
  - Automatic transcription (Whisper Large v2)
- **Output**
  - **800 verbal transcripts**

---

### 2. **Visual Subcorpus**
Frame‑level visual descriptions.

- **Methods**
  - Video decomposition into still frames  
  - Automatic annotation (GPT‑image‑1.5)
- **Output**
  - **800 visual tagging files**

---

### 3. **Lexical Multidimensional Analysis (LMDA)**
Independent LMDA for verbal and visual modes to uncover underlying discourse dimensions.

- **Steps**
  - Extract content words  
  - Compile frequency counts  
  - Apply factor analysis  
  - Interpret high‑loading factors as discourse dimensions
- **Output**
  - **Lexical dimensions of variation** for each semiotic mode

---

### 4. **Multimodal Analysis**
Integration of verbal and visual dimensions.

- **Methods**
  - Canonical Correlation Analysis (CCA)  
  - Cross‑modal comparison  
  - Discourse‑based interpretation
- **Output**
  - **Multimodal discourse profiles**

---

### 5. **Statistical Analysis**
Diachronic comparison across decades.

- **Methods**
  - ANOVAs on verbal, visual, and multimodal dimensions
- **Output**
  - **Statistically validated differences** across time and subcorpora

---

## 📊 Summary Table

| Stage / Component | Description | Tools / Methods | Output |
|------------------|-------------|-----------------|--------|
| **Verbal Subcorpus** | Textual transcripts of commercials | Video‑to‑audio conversion; Whisper Large v2 transcription | 800 transcripts |
| **Visual Subcorpus** | Frame‑based visual descriptions | Frame extraction; GPT‑image‑1.5 annotation | 800 visual tagging files |
| **LMDA** | Discursive dimension extraction | Content‑word extraction; frequency counts; factor analysis | Lexical dimensions of variation |
| **Multimodal Analysis** | Integration of verbal + visual | Canonical Correlation Analysis | Multimodal discourse profiles |
| **Statistical Analysis** | Diachronic comparison | ANOVAs | Validated differences across decades |
