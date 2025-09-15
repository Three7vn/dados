from pathlib import Path
from typing import Optional, Tuple
from PIL import Image


def compress_image(
    input_path: str,
    output_path: Optional[str] = None,
    *,
    max_width: Optional[int] = 1920,
    quality: int = 80,
    fmt: str = "WEBP",
) -> Tuple[str, Tuple[int, int], Tuple[int, int]]:
    """
    Compress an image using Pillow.

    - Resizes to max_width while preserving aspect ratio (if needed).
    - Saves as WEBP (default) or JPEG with optimization.

    Returns (output_path, original_size, new_size).
    """
    src = Path(input_path)
    if output_path is None:
        # Derive output with suffix
        suffix = ".webp" if fmt.upper() == "WEBP" else ".jpg"
        output_path = str(src.with_suffix("") ) + "-compressed" + suffix

    with Image.open(src) as im:
        orig_size = im.size
        # Convert to RGB for WEBP/JPEG safety
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        w, h = im.size
        if max_width and w > max_width:
            new_h = int(h * (max_width / float(w)))
            im = im.resize((max_width, new_h), Image.LANCZOS)
        new_size = im.size
        save_kwargs = {"optimize": True}
        if fmt.upper() in ("JPEG", "JPG"):
            save_kwargs.update({"quality": quality})
        elif fmt.upper() == "WEBP":
            save_kwargs.update({"quality": quality, "method": 6})
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        im.save(output_path, fmt.upper(), **save_kwargs)

    return output_path, orig_size, new_size
