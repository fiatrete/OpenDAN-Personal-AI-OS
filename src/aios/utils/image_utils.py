import base64
import os.path
from typing import Tuple

import cv2


def to_base64(image_path: str, resize: Tuple[int, int] = None) -> str:
    """Convert image to base64."""
    ext = os.path.splitext(image_path)[1][1:]
    if resize is None:
        with open(image_path, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode("utf-8")
            return f"data:image/{ext};base64,{base64_image}"
    else:
        dest_width, dest_height = resize
        img = cv2.imread(image_path)
        width, height = img.shape[:2]
        if width > dest_width or height > dest_height:
            width_rate = dest_width / width
            height_rate = dest_height / height
            rate = min(width_rate, height_rate)
            dest_width = int(width * rate)
            dest_height = int(height * rate)
            img = cv2.resize(img, (dest_width, dest_height), interpolation=cv2.INTER_AREA)
        _, buf = cv2.imencode(f".{ext}", img)
        base64_image = base64.b64encode(buf).decode("utf-8")
        return f"data:image/{ext};base64,{base64_image}"


def is_file(image_path: str) -> bool:
    return os.path.isfile(image_path)


def is_base64(image_path: str) -> bool:
    return image_path.startswith("data:image/")


def is_url(image_path: str) -> bool:
    return image_path.startswith("http://") or image_path.startswith("https://")
