# AASIST Anti-Spoofing & Evidence Fusion Engine

This document provides a comprehensive technical overview of the integrated **AASIST (Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks)** voice spoofing detector and the **Evidence Fusion Engine** in the AI Scam Detection platform.

---

## 1. Rationale: Why AASIST Was Selected
AASIST is a state-of-the-art open-source audio anti-spoofing architecture. It is designed to distinguish between **bona fide** (genuine human) speech and **spoof** (synthetic/AI-generated or replayed) voice.
* **Graph Attention Networks (GATs):** Unlike traditional architectures that analyze time or frequency domains separately, AASIST integrates spectro-temporal features using Graph Attention Networks to identify artifacts left by synthetic voice cloning systems (e.g., ElevenLabs, Tacotron, WaveNet).
* **Speed and Lightweight footprint:** The standard AASIST model is extremely compact and optimized, making it ideal for real-time CPU-only inference during live phone calls.
* **ONNX Portability:** Converting the model to ONNX format allows the platform to perform inference without requiring PyTorch, significantly reducing docker image size and dependency overhead.

---

## 2. Decoupled Architecture: Running Independently of Whisper
AASIST and Whisper STT run completely **in parallel and independently**:
```
Incoming Audio (16kHz Mono PCM)
       │
       ├──► Whisper STT (Transcribes spoken words for semantic threat)
       │
       └──► AASIST (Analyzes acoustic biometrics for synthetic voice clone traces)
```
### Why this independence is crucial:
1. **Modularity:** Whisper is concerned with *what* is being said (semantic meaning), whereas AASIST is concerned with *how* it is being said (acoustic print). 
2. **Robustness:** If one service fails (e.g., Whisper cannot transcribe due to an accent, or AASIST fails due to a missing weight file), the other signal still reaches the Evidence Fusion layer.
3. **Efficiency:** Whisper requires language processing windowing (rolling 30s blocks), whereas AASIST runs on raw 5-second acoustic slices to capture immediate spoofing signals.

---

## 3. Evidence Fusion: Rationale and Mechanics
In a production scam-detection system, **relying on a single score is dangerous**. A single-point failure (like a false positive from a voice model or a misclassified transcript keyword) can disrupt calls or miss scams. 

The **Evidence Fusion Engine** solves this by combining 5 independent dimensions:

1. **Transcript Scam Risk** (Qwen LLM semantic analysis of speech) — Weight: **40%**
2. **AI Voice Probability** (AASIST biometric spoof detection) — Weight: **20%**
3. **Heuristic Keyword Scorer** (Immediate keyword/urgency matching) — Weight: **20%**
4. **RBI / Regulatory Advisory Match** (ChromaDB semantic retrieval count) — Weight: **10%**
5. **Verification Question Response Verdict** (Penalties if caller is evasive) — Weight: **10%**

### Fusion Safeguard Rules:
* **The Low-Spoof Shield:** A low deepfake/spoof probability **never** reduces the transcript-based scam risk. If a scammer speaks a clear OTP scam script using a real human voice, the combined risk remains high (`max(fused, transcript_risk)`).
* **The High-Spoof Cap:** A high deepfake score alone **cannot** trigger the `DANGER` (SCAM) state unless there is content-based scam activity. If the transcript and heuristics indicate a safe call (`risk < 0.40`), the overall fused score is capped at `0.74` (remaining in `VERIFY` mode).

---

## 4. Inference Flow & Preprocessing
AASIST expects a raw mono waveform sampled at **16,000 Hz** of length **64,600 samples** (~4.03 seconds). The inference flow operates as follows:

```
[Audio Bytes / PCM] ──► [PyAV 16kHz Resampler] ──► [Tile / Truncate to 64,600] ──► [ONNX CPU Session] ──► [Softmax Logits] ──► [Spoof Probability]
```

1. **Audio Decoding:** The audio buffer is resampled to 16kHz mono float32 PCM using `PyAV` (or reused from the transcriber).
2. **Padding/Truncation:** 
   * If the input is shorter than 64,600 samples, it is repeated (tiled) to fit.
   * If the input is longer, it is truncated to the first 64,600 samples.
3. **Logits Softmax:** The output logits `[logit_real, logit_spoof]` from the model are normalized using softmax to produce a percentage spoof probability.

---

## 5. Performance, Latency, & Limitations

### Latency Profile
* **Hardware:** Intel/AMD CPU (Single Core)
* **Average Preprocessing Latency:** ~2–5 ms
* **Average Inference Latency:** ~25–40 ms
* **Total Execution Time:** < 50 ms (well within the 5-second streaming cycle)

### Acoustic Limitations & Noisy Speakerphone Considerations
* **Channel Degradation:** In speakerphone mode, the microphone captures ambient room reverberation and telephone compression artifacts. This can degrade AASIST accuracy (causing high false positives/negatives).
* **Evidence Fusion Dampening:** Because of these channel distortions, the Evidence Fusion Engine weights AASIST at **20%** and relies on temporal smoothing (EMA) and state machine hysteresis to prevent twitchy UI gauge movements.
* **Graceful Degradation:** If the ONNX model fails to load, `deepfake_probability` returns `null`, and the fusion engine redistributes its 20% weight to the remaining active signals.

---

## 6. How to Acquire the Pretrained AASIST ONNX Model
To run real deepfake voice detection, place the pretrained AASIST ONNX model at `backend/app/resources/aasist.onnx`.

### Option A: Direct Download (Recommended)
You can download a pre-exported AASIST ONNX model from the community resources or Hugging Face.

### Option B: Export from PyTorch
If you have a PyTorch `.pth` checkpoint, you can export it to ONNX using Python:
```python
import torch
# 1. Instantiate the AASIST model architecture
model = AASIST(config) 
model.load_state_dict(torch.load("aasist_best.pth", map_location="cpu"))
model.eval()

# 2. Export using dummy input
dummy_input = torch.randn(1, 64600)
torch.onnx.export(
    model, 
    dummy_input, 
    "aasist.onnx",
    input_names=["input"], 
    output_names=["output"],
    dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}}
)
```
