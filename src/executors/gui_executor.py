"""GUIExecutor: capture screenshot, ask VLM for targets, verify, and click.
Uses pynput for mouse control and real_time.screenshot for captures.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from pynput.mouse import Controller as MouseController, Button

from real_time.screenshot import capture_fullscreen


class GUIExecutor:
    def __init__(self, screen_monitor: Optional[object] = None) -> None:
        self.mouse = MouseController()
        # Optional continuous screenshot provider with get_recent_images(n:int) -> List[str]
        self.screen_monitor = screen_monitor

    @staticmethod
    def _dist(a: Tuple[int, int], b: Tuple[int, int]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def execute(self, *, instruction: str, vlm_client: Any, verify_radius: int = 32, 
                max_retries: int = 3) -> Dict[str, Any]:
        """
        Execute GUI action with VLM retry logic and fallback to keyboard shortcuts.
        Returns a dict: {
          success: bool,
          target: {x, y, label, confidence} | None,
          screenshots: {before, after, verify},
          error: str | "",
          retries_used: int
        }
        """
        out: Dict[str, Any] = {
            "success": False,
            "target": None,
            "screenshots": {},
            "error": "",
            "retries_used": 0,
        }
        
        for attempt in range(max_retries):
            try:
                # Capture screenshot with different strategies per attempt
                if attempt == 0:
                    before_cap = capture_fullscreen(prefix="before")
                elif attempt == 1:
                    # Retry with different compression/resolution
                    before_cap = capture_fullscreen(prefix="retry1", compress=False)
                else:
                    # Final attempt with cropped/zoomed screenshot
                    before_cap = capture_fullscreen(prefix="retry2", max_width=1280)
                
                out["screenshots"][f"attempt_{attempt}"] = before_cap
                image_path = before_cap.get("webp_path") or before_cap["png_path"]

                # Adjust VLM temperature per attempt (more creative on retries)
                temp = 0.3 + (attempt * 0.1)
                context_imgs = None
                if self.screen_monitor and hasattr(self.screen_monitor, "get_recent_images"):
                    try:
                        context_imgs = self.screen_monitor.get_recent_images(3)
                    except Exception:
                        context_imgs = None
                pred = vlm_client.suggest_targets(
                    image_path=image_path,
                    instruction=instruction,
                    context_images=context_imgs,
                    temperature=min(temp, 0.7)
                )
                targets = pred.get("targets", []) if isinstance(pred, dict) else []
                
                if not targets:
                    if attempt == max_retries - 1:
                        # Final fallback: try keyboard shortcuts
                        return self._fallback_keyboard_action(instruction, out)
                    continue

                # Choose highest confidence target
                def conf(t: Dict[str, Any]) -> float:
                    try:
                        return float(t.get("confidence", 0.0))
                    except Exception:
                        return 0.0
                
                best = max(targets, key=conf)
                confidence = conf(best)
                
                # Skip low confidence targets on early attempts
                if attempt < 2 and confidence < 0.5:
                    continue
                
                tx, ty = int(best.get("x", 0)), int(best.get("y", 0))
                out["target"] = {
                    "x": tx,
                    "y": ty,
                    "label": best.get("label", ""),
                    "confidence": confidence,
                }

                # Pre-click verification
                verify_cap = capture_fullscreen(prefix="verify")
                out["screenshots"]["verify"] = verify_cap
                v_path = verify_cap.get("webp_path") or verify_cap["png_path"]
                v_context_imgs = None
                if self.screen_monitor and hasattr(self.screen_monitor, "get_recent_images"):
                    try:
                        v_context_imgs = self.screen_monitor.get_recent_images(3)
                    except Exception:
                        v_context_imgs = None
                v_pred = vlm_client.suggest_targets(
                    image_path=v_path,
                    instruction=instruction,
                    context_images=v_context_imgs,
                    temperature=0.3
                )
                v_targets = v_pred.get("targets", []) if isinstance(v_pred, dict) else []
                
                # Check if target still exists nearby
                near = False
                for t in v_targets:
                    vx, vy = int(t.get("x", 0)), int(t.get("y", 0))
                    if self._dist((vx, vy), (tx, ty)) <= verify_radius:
                        near = True
                        break
                
                if not near and v_targets and attempt < max_retries - 1:
                    # Target moved, try again
                    continue
                elif not near and v_targets:
                    # Update to closest target on final attempt
                    closest = min(v_targets, key=lambda t: self._dist((int(t.get("x", 0)), int(t.get("y", 0))), (tx, ty)))
                    tx, ty = int(closest.get("x", tx)), int(closest.get("y", ty))

                # Execute click
                prev_pos = self.mouse.position
                self.mouse.position = (tx, ty)
                self.mouse.click(Button.left, 1)

                after_cap = capture_fullscreen(prefix="after")
                out["screenshots"]["after"] = after_cap

                out["success"] = True
                out["mouse_move_from"] = prev_pos
                out["mouse_click_at"] = (tx, ty)
                out["retries_used"] = attempt
                return out
                
            except Exception as e:
                if attempt == max_retries - 1:
                    out["error"] = str(e)
                    return out
                continue
        
        # All retries failed
        out["error"] = "max_retries_exceeded"
        out["retries_used"] = max_retries
        return out

    def _fallback_keyboard_action(self, instruction: str, out: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback to deterministic keyboard shortcuts when VLM fails"""
        from pynput.keyboard import Controller as KeyboardController, Key
        
        keyboard = KeyboardController()
        low_instruction = instruction.lower()
        
        try:
            # Common keyboard shortcuts as fallback
            if "compose" in low_instruction or "new" in low_instruction:
                keyboard.key_down(Key.cmd)
                keyboard.press('n')
                keyboard.key_up(Key.cmd)
                out["success"] = True
                out["fallback"] = "keyboard_shortcut_cmd_n"
            elif "save" in low_instruction:
                keyboard.key_down(Key.cmd)
                keyboard.press('s')
                keyboard.key_up(Key.cmd)
                out["success"] = True
                out["fallback"] = "keyboard_shortcut_cmd_s"
            elif "copy" in low_instruction:
                keyboard.key_down(Key.cmd)
                keyboard.press('c')
                keyboard.key_up(Key.cmd)
                out["success"] = True
                out["fallback"] = "keyboard_shortcut_cmd_c"
            elif "paste" in low_instruction:
                keyboard.key_down(Key.cmd)
                keyboard.press('v')
                keyboard.key_up(Key.cmd)
                out["success"] = True
                out["fallback"] = "keyboard_shortcut_cmd_v"
            else:
                out["error"] = "no_fallback_available"
                
        except Exception as e:
            out["error"] = f"fallback_failed: {e}"
            
        return out
