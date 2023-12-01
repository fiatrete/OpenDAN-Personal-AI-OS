import base64
from typing import List

import cv2


def extract_frames(video_path: str) -> List[str]:
    """Extract frames from video."""
    frames = []
    vidcap = cv2.VideoCapture(video_path)
    while vidcap.isOpened():
        success, image = vidcap.read()
        if not success:
            break
        _, buffer = cv2.imencode(".jpg", image)
        frames.append(base64.b64encode(buffer).decode("utf-8"))
    vidcap.release()
    return frames
