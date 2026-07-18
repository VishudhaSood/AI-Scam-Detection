import ctypes
import sys

_cached_result: bool | None = None


def cuda_runtime_available() -> bool:
    """
    Safely checks whether the CUDA runtime libraries ctranslate2 needs are
    actually present, WITHOUT letting ctranslate2 attempt the load itself.

    Why this exists: WhisperModel(device="cuda") constructs successfully even
    when the CUDA runtime is missing, because ctranslate2 defers DLL loading
    to the first inference. On this project's Windows machines a failed
    in-process load poisons the DLL loader state: the first call raises
    "Library cublas64_12.dll is not found" and any later native call can
    deadlock the whole process (observed freezing live WS sessions). A ctypes
    load attempt is safe: it fails instantly with OSError and touches nothing.
    """
    global _cached_result
    if _cached_result is None:
        if sys.platform != "win32":
            _cached_result = True  # non-Windows: let ctranslate2 decide
        else:
            try:
                ctypes.WinDLL("cublas64_12.dll")
                _cached_result = True
            except OSError:
                _cached_result = False
    return _cached_result
