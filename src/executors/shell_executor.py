"""ShellExecutor: safely run shell commands without shell=True.
- Accepts list-of-lists tokens or list of strings.
- Handles 'cd' by updating cwd for subsequent commands.
- Captures stdout/stderr for logging.
- Integrates safety confirmation gates.
"""
from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

from safety_manager import SafetyManager


class ShellExecutor:
    def __init__(self, base_cwd: Optional[str | Path] = None) -> None:
        self.base_cwd = str(base_cwd) if base_cwd else None
        self.safety = SafetyManager()

    def _to_tokens(self, cmd: Any) -> List[str]:
        if isinstance(cmd, list):
            return [str(t) for t in cmd]
        return shlex.split(str(cmd))

    def run(self, commands: List[Any], cwd: Optional[str | Path] = None, timeout: int = 120, 
            interactive: bool = True) -> Tuple[bool, Dict[str, Any]]:
        cur_cwd = str(cwd or self.base_cwd or ".")
        results: List[Dict[str, Any]] = []
        all_ok = True
        
        # Convert to token lists for safety check
        token_commands = [self._to_tokens(cmd) for cmd in commands if self._to_tokens(cmd)]
        
        # Safety gate: check for dangerous operations
        if interactive and self.safety.requires_confirmation(token_commands):
            prompt = self.safety.get_confirmation_prompt(token_commands)
            try:
                response = input(prompt).strip().lower()
                if response != 'yes':
                    return False, {"results": [], "error": "User cancelled dangerous operation"}
            except (EOFError, KeyboardInterrupt):
                return False, {"results": [], "error": "User cancelled dangerous operation"}
        
        for cmd in commands:
            tokens = self._to_tokens(cmd)
            if not tokens:
                continue
            if tokens[0] == "cd":
                # Update working directory for subsequent commands
                new_dir = tokens[1] if len(tokens) > 1 else "."
                cur_cwd = str(Path(cur_cwd) / new_dir) if not Path(new_dir).is_absolute() else new_dir
                results.append({"cmd": tokens, "cwd": cur_cwd, "returncode": 0, "stdout": "", "stderr": ""})
                continue
            try:
                proc = subprocess.run(
                    tokens,
                    cwd=cur_cwd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                ok = proc.returncode == 0
                all_ok = all_ok and ok
                results.append({
                    "cmd": tokens,
                    "cwd": cur_cwd,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                })
            except Exception as e:
                all_ok = False
                results.append({
                    "cmd": tokens,
                    "cwd": cur_cwd,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": str(e),
                })
        return all_ok, {"results": results}
