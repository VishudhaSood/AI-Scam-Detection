import io
import av
import numpy as np
from faster_whisper import WhisperModel

from app.services.cuda_check import cuda_runtime_available

class StreamingTranscriber:
    """
    Handles audio decoding via PyAV and speech-to-text via faster-whisper.
    Decodes cumulative WebM buffers to raw 16kHz PCM and transcribes active blocks.
    """
    _model = None
    _device = "cpu"

    @classmethod
    def _get_model(cls):
        if cls._model is None:
            # Never let ctranslate2 attempt a CUDA load when the runtime DLLs
            # are absent: a failed in-process load can poison the Windows DLL
            # loader and deadlock later native calls (see cuda_check.py).
            if cuda_runtime_available():
                try:
                    model = WhisperModel("tiny", device="cuda", compute_type="float16")
                    # Constructor success does not prove CUDA works (DLL load
                    # is deferred to first inference) — probe before caching.
                    probe_segments, _ = model.transcribe(
                        np.zeros(16000, dtype=np.float32), beam_size=1
                    )
                    list(probe_segments)
                    cls._device = "cuda"
                    print("Loaded Whisper tiny model on CUDA.")
                except Exception as e:
                    print(f"Failed to load Whisper on CUDA ({e}), falling back to CPU...")
                    model = WhisperModel("tiny", device="cpu", compute_type="int8")
                    cls._device = "cpu"
                    print("Loaded Whisper tiny model on CPU.")
            else:
                print("CUDA runtime libraries not found; using CPU int8 Whisper model.")
                model = WhisperModel("tiny", device="cpu", compute_type="int8")
                cls._device = "cpu"
            cls._model = model
        return cls._model

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
        """
        if pcm_data is None or pcm_data.size == 0:
            return ""

        model = self._get_model()
        try:
            # Run Whisper transcription with beam_size=5 (optimized)
            segments, info = model.transcribe(pcm_data, beam_size=5)
            text = "".join(segment.text for segment in segments)
            return text.strip()
        except Exception as e:
            print(f"Whisper transcription error: {e}")
            return ""
