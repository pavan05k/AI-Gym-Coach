import importlib
import sys
import threading
import types
import unittest
from unittest.mock import patch


def _load_video_processor_class():
    """Import just the processor state logic without camera-native packages."""
    media_pipe = types.ModuleType("mediapipe")
    media_pipe_tasks = types.ModuleType("mediapipe.tasks")
    media_pipe_python = types.ModuleType("mediapipe.tasks.python")
    media_pipe_vision = types.ModuleType("mediapipe.tasks.python.vision")
    media_pipe.tasks = media_pipe_tasks
    media_pipe_tasks.python = media_pipe_python
    media_pipe_python.vision = media_pipe_vision

    webrtc = types.ModuleType("streamlit_webrtc")
    webrtc.VideoProcessorBase = type("VideoProcessorBase", (), {})

    dependencies = {
        "av": types.ModuleType("av"),
        "cv2": types.ModuleType("cv2"),
        "numpy": types.ModuleType("numpy"),
        "mediapipe": media_pipe,
        "mediapipe.tasks": media_pipe_tasks,
        "mediapipe.tasks.python": media_pipe_python,
        "mediapipe.tasks.python.vision": media_pipe_vision,
        "streamlit_webrtc": webrtc,
    }
    module_name = "services.vision.exercise_video_prosessor"

    with patch.dict(sys.modules, dependencies):
        sys.modules.pop(module_name, None)
        module = importlib.import_module(module_name)

    return module.VideoProcessorClass


VideoProcessorClass = _load_video_processor_class()


class _Detector:
    def __init__(self):
        self.reset_calls = 0

    def reset(self):
        self.reset_calls += 1


class LiveProgressTests(unittest.TestCase):
    def setUp(self):
        self.processor = VideoProcessorClass.__new__(VideoProcessorClass)
        self.processor._lock = threading.Lock()
        self.processor._exercise_type = "Squats"
        self.detector = _Detector()
        self.processor._detectors = {"Squats": self.detector}
        self.processor._latest_metrics = {"reps": 4}

    def test_same_exercise_keeps_detector_state_during_live_refreshes(self):
        self.processor.set_exercise("Squats")

        self.assertEqual(self.detector.reset_calls, 0)
        self.assertEqual(self.processor.get_latest_metrics(), {"reps": 4})

    def test_new_workout_resets_detector_once(self):
        self.processor.set_exercise("Squats", reset=True)

        self.assertEqual(self.detector.reset_calls, 1)
        self.assertIsNone(self.processor.get_latest_metrics())


if __name__ == "__main__":
    unittest.main()
