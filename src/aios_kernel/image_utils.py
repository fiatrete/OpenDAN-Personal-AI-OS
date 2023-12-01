import base64
import os.path


def to_base64(image_path: str) -> str:
    """Convert image to base64."""
    ext = os.path.splitext(image_path)[1]
    with open(image_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:image/{ext};base64,{base64_image}"


def is_file(image_path: str) -> bool:
    return os.path.isfile(image_path)


def is_base64(image_path: str) -> bool:
    return image_path.startswith("data:image/")


def is_url(image_path: str) -> bool:
    return image_path.startswith("http://") or image_path.startswith("https://")
