import time
from pathlib import Path
from typing import Dict, Optional

import pyautogui

from real_time.image_utils import compress_image


DEFAULT_DIR = Path(__file__).resolve().parents[2] / "data" / "screenshots"


def capture_fullscreen(
    *,
    directory: Optional[str] = None,
    prefix: str = "shot",
    compress: bool = True,
    max_width: int = 1920,
) -> Dict[str, str]:
    """
    Capture a full-screen screenshot to PNG under data/screenshots/.
    Optionally create a compressed WEBP copy.

    Returns dict with keys: png_path, webp_path (optional), file_uri.
    file_uri is the file:// URI to the (compressed if available else PNG) file.
    """
    out_dir = Path(directory).expanduser() if directory else DEFAULT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d-%H%M%S")
    png_path = out_dir / f"{prefix}-{ts}.png"

    im = pyautogui.screenshot()
    im.save(png_path)

    result = {"png_path": str(png_path)}

    webp_path = None
    if compress:
        webp_path, _, _ = compress_image(str(png_path), fmt="WEBP", max_width=max_width)
        result["webp_path"] = webp_path
        result["file_uri"] = f"file://{webp_path}"
    else:
        result["file_uri"] = f"file://{png_path}"

    return result
