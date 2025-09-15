"""
Command Router: decides which execution path to take
based on the user's instruction and model outputs.

Paths:
- dictation: inject text as-is (after optional correction)
- shell: generate shell commands from LFM and execute
- gui: use VLM to infer click targets and act
"""
from __future__ import annotations

from typing import Any, Dict, List
import shlex


class CommandRouter:
    def __init__(self, *, lfm_client: Any, command_library: Dict[str, Any]) -> None:
        self.lfm = lfm_client
        self.command_library = command_library
        # Simple heuristic for GUI tasks; can be expanded or replaced by LFM intent parsing
        self.gui_keywords = {
            "click", "press", "compose", "scroll", "select", "button",
            "menu", "tab", "play", "pause", "submit", "open compose",
        }

    def route(self, instruction: str) -> Dict[str, Any]:
        text = instruction.strip()
        low = text.lower()

        # 1) Path A: True deterministic matching (direct JSON lookup)
        deterministic_match = self._try_deterministic_match(text)
        if deterministic_match:
            return deterministic_match

        # 2) Heuristic: UI verbs => GUI path
        if any(k in low for k in self.gui_keywords):
            return {"path": "gui"}

        # 3) Path B: Ask LFM to generate shell commands using the command library as context
        try:
            commands = self.lfm.generate_commands(
                instruction=text,
                command_library=self.command_library,
                available_ops=[
                    "mouse.position=(x,y)",
                    "mouse.click(Button.left,count)",
                    "keyboard.type(text)",
                    "pyautogui.screenshot()",
                ],
            )
        except Exception:
            commands = []

        if commands:
            return {"path": "shell", "commands": commands}

        # 4) Fallback to dictation (Path D)
        return {"path": "dictation"}

    def _try_deterministic_match(self, text: str) -> Dict[str, Any] | None:
        """Path A: Direct deterministic matching without LFM"""
        low = text.lower().strip()
        
        # Check aliases
        for alias, url in self.command_library.get("aliases", {}).items():
            if alias.lower() in low or any(word in low for word in alias.lower().split("_")):
                return {"path": "shell", "commands": [["open", url]]}
        
        # Check apps
        for app_key, cmd in self.command_library.get("apps", {}).items():
            if app_key.lower() in low:
                # Support either a shell string or a pre-tokenized list
                tokens = cmd if isinstance(cmd, list) else shlex.split(str(cmd))
                return {"path": "shell", "commands": [tokens]}
        
        # Check workflows
        for workflow_key, commands in self.command_library.get("workflows", {}).items():
            key_words = workflow_key.lower().replace("_", " ").split()
            if any(word in low for word in key_words) and len([w for w in key_words if w in low]) >= len(key_words) // 2:
                return {"path": "shell", "commands": commands}
        
        return None
