"""Quick test to see what happens when Whisper tries to transcribe."""
import os
import glob

# Check if any webm files exist from recent recordings
search_dirs = [
    r"C:\Users\Admin",
    r"C:\Users\Admin\Downloads",
    r"C:\Users\Admin\Hackathon\Scam Detection\AI-Scam-Detection",
]

print("=== Step 1: Testing Whisper model load ===")
try:
    from faster_whisper import WhisperModel
    print("  Import: OK")
    
    try:
        model = WhisperModel("tiny", device="cuda", compute_type="float16")
        print("  Model load (CUDA): OK")
    except Exception as e:
        print(f"  CUDA failed: {e}")
        try:
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            print("  Model load (CPU): OK")
        except Exception as e2:
            print(f"  CPU also failed: {e2}")
            model = None
            
except Exception as e:
    print(f"  Import failed: {e}")
    model = None

print("\n=== Step 2: Testing ffmpeg ===")
import shutil
ffmpeg_path = shutil.which("ffmpeg")
if ffmpeg_path:
    print(f"  ffmpeg found at: {ffmpeg_path}")
else:
    print("  ffmpeg NOT FOUND - this is required for .webm decoding!")
    print("  Whisper uses ffmpeg internally to decode audio formats.")
    print("  Without it, transcription of .webm files will FAIL.")

print("\n=== Step 3: Testing transcription with a dummy WAV ===")
if model:
    import tempfile
    import struct
    import wave
    
    # Create a tiny valid WAV file (1 second of silence)
    wav_path = os.path.join(tempfile.gettempdir(), "test_silence.wav")
    with wave.open(wav_path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b'\x00\x00' * 16000)  # 1s of silence
    
    try:
        segments, info = model.transcribe(wav_path, beam_size=5)
        text = "".join(s.text for s in segments)
        print(f"  Transcription result: '{text.strip()}'")
        print("  Whisper transcription: WORKING!")
    except Exception as e:
        print(f"  Transcription failed: {e}")
    finally:
        os.remove(wav_path)
else:
    print("  Skipped (model not loaded)")

print("\n=== DIAGNOSIS ===")
if not ffmpeg_path:
    print("ROOT CAUSE: ffmpeg is not installed.")
    print("Whisper needs ffmpeg to decode .webm audio files.")
    print("The code silently falls back to mock transcripts when this fails.")
    print("\nFIX: Install ffmpeg and add it to PATH")
