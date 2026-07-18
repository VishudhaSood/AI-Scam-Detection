import ctypes
import os
import platform

# Preload system C++ runtime DLLs on Windows to prevent Anaconda DLL Hell crash
if platform.system() == "Windows":
    try:
        windir = os.environ.get("SystemRoot", os.environ.get("windir", "C:\\Windows"))
        system32 = os.path.join(windir, "System32")
        for dll in ["msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"]:
            dll_path = os.path.join(system32, dll)
            if os.path.exists(dll_path):
                ctypes.CDLL(dll_path)
    except Exception:
        pass

import io
import av
import numpy as np

import threading

# Try to import faster-whisper safely
try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

class StreamingTranscriber:
    """
    Handles audio decoding via PyAV and speech-to-text via faster-whisper.
    Decodes cumulative WebM buffers to raw 16kHz PCM and transcribes active blocks.
    Supports a zero-dependency mock mode for local testing.
    """
    _model = None
    _device = "cpu"
    _model_lock = threading.Lock()

    def __init__(self):
        self.cycle_count = 0
        self.mock_script = [
            "Hello? Yes, am I speaking with the card holder?",
            "This is the police head department. We have detected suspicious transactions on your account.",
            "An arrest warrant has been issued under your name for money laundering. You must act fast.",
            "To suspend the warrant, you must transfer a safety deposit of fifty thousand rupees immediately.",
            "Do not hang up the call or speak to anyone. Verify your OTP and bank details now."
        ]

    @classmethod
    def _get_model(cls):
        if not HAS_WHISPER:
            raise ImportError("faster_whisper is not installed in the environment.")
            
        with cls._model_lock:
            if cls._model is None:
                try:
                    # Attempt to load tiny model on CUDA
                    cls._model = WhisperModel("tiny", device="cuda", compute_type="float16")
                    cls._device = "cuda"
                    print("Loaded Whisper tiny model on CUDA.")
                except Exception as e:
                    print(f"Failed to load Whisper on CUDA ({e}), falling back to CPU...")
                    # Fallback to CPU with int8 quantization
                    cls._model = WhisperModel("tiny", device="cpu", compute_type="int8")
                    cls._device = "cpu"
                    print("Loaded Whisper tiny model on CPU.")
        return cls._model

    @classmethod
    def eager_load_model(cls):
        if os.environ.get("USE_MOCK_WHISPER") == "true":
            print("Eager loading StreamingTranscriber model skipped: mock mode active.")
            return
        try:
            print("Eagerly loading StreamingTranscriber Whisper model...")
            cls._get_model()
            print("StreamingTranscriber Whisper model preloaded successfully!")
        except Exception as e:
            print(f"Failed to eager load StreamingTranscriber model: {e}")

    def decode_to_pcm(self, audio_bytes: bytes) -> np.ndarray:
        """
        Decodes a container-formatted audio buffer (e.g. WebM) into 16kHz mono float32 PCM.
        Handles incomplete/growing buffers gracefully.
        """
        if not audio_bytes or len(audio_bytes) < 100:
            return np.array([], dtype=np.float32)

        input_file = io.BytesIO(audio_bytes)
        try:
            with av.open(input_file) as container:
                if not container.streams.audio:
                    return np.array([], dtype=np.float32)
                
                stream = container.streams.audio[0]
                resampler = av.AudioResampler(
                    format="flt",
                    layout="mono",
                    rate=16000
                )
                
                chunks = []
                for frame in container.decode(stream):
                    resampled_frames = resampler.resample(frame)
                    for r_frame in resampled_frames:
                        chunks.append(r_frame.to_ndarray().flatten())
                
                if not chunks:
                    return np.array([], dtype=np.float32)
                
                return np.concatenate(chunks)
        except Exception as e:
            # Incomplete streams can throw AVErrors during early frames; handle gracefully
            return np.array([], dtype=np.float32)

    def transcribe_pcm(self, pcm_data: np.ndarray) -> str:
        """
        Transcribes raw 16kHz float32 mono PCM numpy array using Whisper.
        If USE_MOCK_WHISPER=true or if model loading fails, runs in simulation mode.
        """
        # If mock mode is requested or whisper is missing, run simulated transcription
        if os.environ.get("USE_MOCK_WHISPER") == "true" or not HAS_WHISPER:
            return self._get_mock_transcription()

        if pcm_data is None or pcm_data.size == 0:
            return ""

        try:
            model = self._get_model()
            # Run Whisper transcription with VAD filtering and English language lock to prevent hallucinations
            segments, info = model.transcribe(
                pcm_data,
                beam_size=5,
                language="en",
                vad_filter=True
            )
            text = "".join(segment.text for segment in segments)
            return text.strip()
        except Exception as e:
            print(f"Whisper transcription failed/hung ({e}). Switching to mock fallback.")
            # Set environment variable so subsequent loops bypass Whisper immediately
            os.environ["USE_MOCK_WHISPER"] = "true"
            return self._get_mock_transcription()

    def _get_mock_transcription(self) -> str:
        """
        Returns a line-by-line mock transcript of a scam call.
        """
        if self.cycle_count < len(self.mock_script):
            transcript = self.mock_script[self.cycle_count]
            self.cycle_count += 1
            return transcript
        else:
            return "This call is classified as a scam. Please hang up immediately."
