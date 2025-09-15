import json
import os
from typing import Any, Dict, List, Optional

from llama_cpp import Llama


class LFMClient:
    """
    Liquid Foundation Model (language) client using llama-cpp-python.

    Loads a local GGUF model via from_pretrained and provides a helper to
    (1) correct grammar of text and (2) translate a natural language instruction
    into a JSON array-of-arrays of shell commands.
    """

    def __init__(
        self,
        repo_id: str = "unsloth/LFM2-1.2B-GGUF",
        filename: str = "LFM2-1.2B-F16.gguf",
        n_ctx: int = 4096,
        n_threads: Optional[int] = None,
    ) -> None:
        self.model = Llama.from_pretrained(
            repo_id=repo_id,
            filename=filename,
            n_ctx=n_ctx,
            # Let llama-cpp decide default threads if None
            n_threads=n_threads or os.cpu_count() or 4,
        )

    def correct_text(
        self,
        text: str,
        *,
        temperature: float = 0.2,
        top_p: float = 0.9,
        max_tokens: int = 256,
    ) -> str:
        """
        Light grammar and punctuation correction. Returns corrected text only.
        Fallbacks to original text on error.
        """
        prompt_system = (
            "You improve grammar, casing, and punctuation of short transcriptions. "
            "Do not change meaning. Output only the corrected text, without quotes."
        )
        messages = [
            {"role": "system", "content": prompt_system},
            {"role": "user", "content": [{"type": "text", "text": text}]},
        ]
        try:
            resp = self.model.create_chat_completion(
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )
            content = resp["choices"][0]["message"]["content"].strip()
            return content
        except Exception:
            return text

    def generate_commands(
        self,
        instruction: str,
        command_library: Dict[str, Any],
        available_ops: Optional[List[str]] = None,
        temperature: float = 0.1,
        top_p: float = 0.9,
        max_tokens: int = 512,
    ) -> List[List[str]]:
        """
        Ask the model to produce a JSON array of shell commands for macOS.
        The model receives the full command_library JSON and the available operations
        (e.g. pynput capabilities) as context.
        """
        available_ops = available_ops or []

        system_prompt = (
            "You are a command generator for macOS. "
            "Translate user instructions into a JSON array of arrays of shell commands. "
            "Use 'open -a' for apps, 'open \"<URL>\"' for links, and 'git' for repo actions. "
            "Never output explanations; output only JSON. "
            "Avoid destructive commands. Ask for confirmation if risk is detected."
        )

        dyn_ops = "\n".join(f"- {op}" for op in available_ops)
        context_blob = (
            "Command library JSON (verbatim):\n" + json.dumps(command_library, indent=2) +
            "\n\nAvailable operations (high-level, via pynput & system tools):\n"
            "- mouse.move(dx, dy)\n"
            "- mouse.position=(x, y)\n"
            "- mouse.click(Button.left, count)\n"
            "- mouse.scroll(dx, dy)\n"
            "- keyboard.type(text)\n"
            "- keyboard.press(key), keyboard.release(key)\n"
            "- pyautogui.screenshot() to capture screen\n"
            + ("\nUser-provided additional operations:\n" + dyn_ops if dyn_ops else "")
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": (
                    "Instruction:\n" + instruction + "\n\n" + context_blob +
                    "\nOutput strictly JSON array-of-arrays, e.g. [[\"open\", \"-a\", \"Google Chrome\"]]."
                )}
            ]},
        ]

        resp = self.model.create_chat_completion(
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

        content = resp["choices"][0]["message"]["content"].strip()
        # Extract first JSON array present
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list) and all(isinstance(x, list) for x in parsed):
                return self._safety_filter(parsed)
        except Exception:
            pass
        # Fallback: attempt to find JSON substring
        start = content.find("[")
        end = content.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                parsed = json.loads(content[start:end + 1])
                if isinstance(parsed, list) and all(isinstance(x, list) for x in parsed):
                    return self._safety_filter(parsed)
            except Exception:
                pass
        return []

    def _safety_filter(self, commands: List[List[str]]) -> List[List[str]]:
        """Drop obviously dangerous commands; simple allowlist-style filter."""
        dangerous = {"rm", "shutdown", "reboot", "kill", "killall"}
        filtered: List[List[str]] = []
        for cmd in commands:
            tokens = [t.lower() for t in cmd]
            if any(tok in dangerous for tok in tokens):
                continue
            # crude guard against rm -rf /
            if "rm" in tokens and "-rf" in tokens:
                continue
            filtered.append(cmd)
        return filtered
