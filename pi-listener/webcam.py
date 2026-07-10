 
import argparse
import threading
import time
import wave
from pathlib import Path
 
SAMPLE_RATE = 16000   # matches what the dialogue server (Whisper) expects
CHANNELS = 1
OUTPUT_DIR = Path(__file__).parent / "recordings"
 
 
def list_input_devices():
    """Print every audio input device sounddevice can see, with its index."""
    import sounddevice as sd
    devices = sd.query_devices()
    print("\nAvailable input devices:\n")
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            marker = "  <-- looks like a webcam" if "logitech" in dev["name"].lower() or "webcam" in dev["name"].lower() else ""
            print(f"  [{i}] {dev['name']}  (inputs: {dev['max_input_channels']}){marker}")
    print()
 
 
def find_logitech_device():
    """
    Best-effort auto-detect: scan device names for 'logitech' or 'webcam'.
    Returns the device index, or None if nothing matched (caller should
    fall back to --list-devices and manual selection).
    """
    import sounddevice as sd
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        name = dev["name"].lower()
        if dev["max_input_channels"] > 0 and ("logitech" in name or "webcam" in name):
            return i
    return None
 
 
class WebcamAudioRecorder:
    """
    Mirrors the start()/stop() shape of the existing /start and /stop
    routes in pi-listener/listener.py, so wiring this in later is a
    drop-in swap rather than a rewrite.
    """
 
    def __init__(self, device=None, samplerate=SAMPLE_RATE, channels=CHANNELS):
        self.device = device
        self.samplerate = samplerate
        self.channels = channels
        self._frames = []
        self._stream = None
        self._recording = False
        self._lock = threading.Lock()
 
    def start(self):
        import sounddevice as sd
 
        if self._recording:
            print("[webcam_recorder] Already recording, ignoring start().")
            return
 
        if self.device is None:
            self.device = find_logitech_device()
            if self.device is None:
                raise RuntimeError(
                    "Could not auto-detect a Logitech/webcam input device. "
                    "Run with --list-devices and pass --device <index> explicitly."
                )
 
        self._frames = []
        self._recording = True
 
        def callback(indata, frames, time_info, status):
            if status:
                print(f"[webcam_recorder] Stream status: {status}")
            with self._lock:
                self._frames.append(indata.copy())
 
        self._stream = sd.InputStream(
            device=self.device,
            samplerate=self.samplerate,
            channels=self.channels,
            dtype="int16",
            callback=callback,
        )
        self._stream.start()
        print(f"[webcam_recorder] Recording started (device={self.device}).")
 
    def stop(self, save_path: str | None = None) -> str:
        if not self._recording:
            print("[webcam_recorder] Not currently recording, ignoring stop().")
            return ""
 
        self._stream.stop()
        self._stream.close()
        self._recording = False
 
        import numpy as np
        with self._lock:
            audio = np.concatenate(self._frames, axis=0) if self._frames else np.zeros((0, self.channels), dtype="int16")
 
        OUTPUT_DIR.mkdir(exist_ok=True)
        if save_path is None:
            save_path = str(OUTPUT_DIR / f"recording_{int(time.time())}.wav")
 
        with wave.open(save_path, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(self.samplerate)
            wf.writeframes(audio.tobytes())
 
        print(f"[webcam_recorder] Recording stopped. Saved to {save_path}")
        return save_path
 
    def is_recording(self) -> bool:
        return self._recording
 
 
# ---------------------------------------------------------------------------
# How this will eventually plug into pi-listener/listener.py:
#
#   from webcam_recorder import WebcamAudioRecorder
#   recorder = WebcamAudioRecorder()
#
#   @app.route("/start")
#   def start():
#       recorder.start()
#       return "recording started"
#
#   @app.route("/stop")
#   def stop():
#       path = recorder.stop()
#       return f"saved to {path}"
#
# Not wired in yet on purpose — this file is standalone until the webcam
# is physically connected and device detection has been confirmed.
# ---------------------------------------------------------------------------
 
 
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the webcam audio recorder standalone.")
    parser.add_argument("--list-devices", action="store_true", help="List all audio input devices and exit.")
    parser.add_argument("--device", type=int, default=None, help="Device index to record from.")
    parser.add_argument("--seconds", type=int, default=5, help="Length of the test recording.")
    args = parser.parse_args()
 
    if args.list_devices:
        list_input_devices()
        raise SystemExit(0)
 
    recorder = WebcamAudioRecorder(device=args.device)
    print(f"Recording a {args.seconds}s test clip. Speak now...")
    recorder.start()
    time.sleep(args.seconds)
    path = recorder.stop()
    print(f"Done. Test file saved at: {path}")
 