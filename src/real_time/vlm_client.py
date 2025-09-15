import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from llama_cpp import Llama


class VLMClient:
    """
    Vision-Language Model client using llama-cpp-python.

    Loads a local GGUF multimodal model via from_pretrained and provides a helper to
    infer click targets from a screenshot and instruction.
    """

    def __init__(
        self,
        repo_id: str = "gabriellarson/LFM2-VL-1.6B-GGUF",
        filename: str = "LFM2-VL-1.6B-F16.gguf",
        n_ctx: int = 4096,
        n_threads: Optional[int] = None,
    ) -> None:
        self.model = Llama.from_pretrained(
            repo_id=repo_id,
            filename=filename,
            n_ctx=n_ctx,
            n_threads=n_threads or os.cpu_count() or 4,
        )

    def suggest_targets(
        self,
        image_path: str,
        instruction: str,
        context_images: Optional[List[str]] = None,
        temperature: float = 0.1,
        top_p: float = 0.9,
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        """
        Ask the model for JSON: {"targets": [{"x": int, "y": int, "label": str, "confidence": float}], "notes": str}
        Coordinates are absolute pixels relative to the screenshot.
        """
        p = Path(image_path).expanduser().resolve()
        system_prompt = (
            "You analyze one or more desktop screenshots and return UI click targets as JSON. "
            "If multiple images are provided, the first is the current frame and the rest are recent context frames. "
            "Output only JSON with fields: targets (list of {x:int, y:int, label:str, confidence:float}), and optional notes. "
            "Coordinates must be absolute pixel positions for the current frame. "
            "Map your reasoning to the actual pynput API used by the agent: mouse.position=(x,y) for absolute set; "
            "mouse.move(dx,dy) for relative move; mouse.click(Button.left,count) for clicks; mouse.scroll(dx,dy) for scrolling. "
            "Be conservative: if ambiguous or low confidence, return an empty list."
        )
        user_text = (
            "Instruction: " + instruction + "\n" 
            "Return JSON with fields: targets (list of {x, y, label, confidence}), and optional notes."
        )
        # Build message content with current image plus optional context images
        content_parts: List[Dict[str, Any]] = [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": f"file://{p}"}},
        ]
        if context_images:
            for ci in context_images:
                try:
                    cp = Path(ci).expanduser().resolve()
                    content_parts.append({"type": "image_url", "image_url": {"url": f"file://{cp}"}})
                except Exception:
                    continue
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content_parts},
        ]
        resp = self.model.create_chat_completion(
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        content = resp["choices"][0]["message"]["content"].strip()
        try:
            return json.loads(content)
        except Exception:
            # Fallback: try to extract JSON object substring
            start = content.find("{")
            end = content.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(content[start:end + 1])
                except Exception:
                    pass
        return {"targets": [], "notes": "parse_error"}
