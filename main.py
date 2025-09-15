#!/usr/bin/env python3
"""
Dados - Voice-first OS Agent
Hold Right Option key and speak to issue commands or dictate text
"""

import sys
import time
import os
import atexit
from pathlib import Path
import json
import threading
import queue
import traceback

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from key_listener import KeyListener
from audio_capture import AudioCapture
from asr import ASREngine
from injector import TextInjector
from src.event_logger import EventLogger
from src.command_router import CommandRouter
from src.executors.shell_executor import ShellExecutor
from src.executors.gui_executor import GUIExecutor
from src.real_time.lfm_client import LFMClient
from src.real_time.vlm_client import VLMClient
from src.task_parser import TaskParser
from src.context_manager import ContextManager
from src.event_logger import EventLogger
from src.screen_monitor import ScreenMonitor
from src.web_server import web_server

# Lock file to prevent multiple instances
LOCK_FILE = Path("/tmp/dados.lock")

def create_lock():
    """Create lock file to prevent multiple instances"""
    if LOCK_FILE.exists():
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            # Check if process is still running
            os.kill(pid, 0)  # This will raise OSError if process doesn't exist
            print("❌ Another instance of Dados is already running!")
            print(f"   PID: {pid}")
            print("   Kill it first with: pkill -f 'python.*main.py'")
            return False
        except (OSError, ValueError):
            # Process is dead, remove stale lock file
            LOCK_FILE.unlink()
    
    # Create new lock file
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    
    # Register cleanup function
    atexit.register(cleanup_lock)
    return True

def cleanup_lock():
    """Remove lock file on exit"""
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()

def main():
    # Check for existing instance
    if not create_lock():
        return 1
    
    print("Dados - Hold RIGHT OPTION key (⌥) and speak to control your computer")
    
    # Initialize components
    audio = AudioCapture()
    asr = ASREngine()
    injector = TextInjector()

    # Load command library (deterministic commands)
    cmd_lib_path = Path(__file__).parent / "src" / "dictionary" / "command_library.json"
    if not cmd_lib_path.exists():
        example = cmd_lib_path.with_suffix(cmd_lib_path.suffix + ".example")
        cmd_lib_path = example if example.exists() else cmd_lib_path
    try:
        with open(cmd_lib_path, 'r', encoding='utf-8') as f:
            command_library = json.load(f)
    except Exception:
        command_library = {"aliases": {}, "apps": {}, "workflows": {}}

    # Instantiate models with graceful fallback
    lfm = None
    vlm = None
    try:
        lfm = LFMClient()  # unsloth/LFM2-1.2B-GGUF, F16 by default
        print("LFM2 language model ready")
    except Exception as e:
        print(f"[warn] LFM init failed: {e}. Falling back to dictation-only for commands.")

    try:
        vlm = VLMClient()  # gabriellarson/LFM2-VL-1.6B-GGUF
        print("LFM2-VL vision model ready")
    except Exception as e:
        print(f"[warn] VLM init failed: {e}. GUI automation will be disabled.")

    # Executors, router, and context manager
    event_logger = EventLogger()
    screen_monitor = ScreenMonitor(interval=1.0)  # Screenshot every second
    router = CommandRouter(lfm_client=lfm, command_library=command_library)
    shell_exec = ShellExecutor()
    gui_exec = GUIExecutor(screen_monitor=screen_monitor)
    task_parser = TaskParser()
    context_mgr = ContextManager()

    # Background processing queue
    task_queue: "queue.Queue" = queue.Queue()

    def worker():
        while True:
            item = task_queue.get()
            if item is None:
                break
            started_at = time.time()
            audio_data = item.get("audio")
            try:
                raw_text = asr.transcribe(audio_data)
                if not raw_text.strip():
                    print("No speech detected")
                    continue
                
                # Optional grammar correction
                corrected_text = raw_text
                try:
                    if lfm:
                        corrected_text = lfm.correct_text(raw_text)
                except Exception:
                    corrected_text = raw_text

                # Parse into multiple tasks if complex instruction
                tasks = task_parser.parse(corrected_text)
                print(f"Parsed {len(tasks)} task(s)")
                
                if len(tasks) == 1:
                    # Single task - use original simple flow
                    task = tasks[0]
                    route_info = router.route(task.instruction)
                    path = route_info.get("path", "dictation")
                    print(f"Route: {path}")

                    success = True
                    err = ""
                    generated_cmds = route_info.get("commands")
                    mouse_from = None
                    mouse_at = None
                    shot_before = None
                    shot_after = None

                    if path == "dictation":
                        injector.type_text(task.instruction)
                        print(f"Typed: {task.instruction}")
                        web_server.add_speech_entry(corrected_text)
                        web_server.add_action_entry("Text Injection", f"Typed: {task.instruction}")
                    elif path == "shell" and generated_cmds:
                        ok, details = shell_exec.run(generated_cmds)
                        success = success and ok
                        results = details.get("results", [])
                        # Detailed logging for each command
                        for r in results:
                            tokens = r.get("cmd", [])
                            rc = r.get("returncode")
                            cwd_used = r.get("cwd")
                            if rc == 0:
                                print(f"[OK] $ {' '.join(tokens)} (cwd={cwd_used})")
                            else:
                                stderr_snip = (r.get('stderr') or '')[:200].replace('\n', ' ')
                                print(f"[ERR rc={rc}] $ {' '.join(tokens)} (cwd={cwd_used}) :: {stderr_snip}")
                        if not ok:
                            err = "; ".join(
                                f"{r['cmd']} -> rc={r['returncode']} err={(r.get('stderr') or '')[:200]}" for r in results if r.get("returncode", 0) != 0
                            )
                        
                        # Add to web UI
                        web_server.add_speech_entry(corrected_text)
                        cmd_summary = f"Executed {len(results)} command(s): {', '.join(' '.join(r.get('cmd', [])) for r in results[:3])}"
                        if len(results) > 3:
                            cmd_summary += f" and {len(results)-3} more"
                        web_server.add_action_entry("Shell Command", cmd_summary, success=ok)
                    elif path == "gui" and vlm:
                        gui_res = gui_exec.execute(instruction=task.instruction, vlm_client=vlm)
                        success = success and bool(gui_res.get("success"))
                        if gui_res.get("error"):
                            err = gui_res.get("error", "")
                        mouse_from = gui_res.get("mouse_move_from")
                        mouse_at = gui_res.get("mouse_click_at")
                        shots = gui_res.get("screenshots", {})
                        shot_before = (shots.get("before", {}) or {}).get("webp_path") or (shots.get("before", {}) or {}).get("png_path")
                        shot_after = (shots.get("after", {}) or {}).get("webp_path") or (shots.get("after", {}) or {}).get("png_path")
                        print("GUI action attempted")
                        
                        # Add to web UI
                        web_server.add_speech_entry(corrected_text)
                        target_info = gui_res.get("target", {})
                        if target_info:
                            gui_summary = f"VLM analysis → Click at ({target_info.get('x')}, {target_info.get('y')}) → {target_info.get('label', 'Unknown')}"
                        else:
                            gui_summary = f"GUI automation attempted → {gui_res.get('error', 'No target found')}"
                        web_server.add_action_entry("GUI Action", gui_summary, success=success)
                    else:
                        # Fallback to dictation if models missing
                        injector.type_text(task.instruction)
                        print(f"Typed: {task.instruction}")

                    elapsed_ms = int((time.time() - started_at) * 1000)
                    event_logger.log(
                        user_request=corrected_text,
                        route_path=path,
                        generated_commands=generated_cmds,
                        mouse_move_from=mouse_from,
                        mouse_click_at=mouse_at,
                        screenshot_before=shot_before,
                        screenshot_after=shot_after,
                        success=success,
                        error_message=err,
                        execution_time_ms=elapsed_ms,
                        audio_file="",
                    )
                else:
                    # Multi-task - use context manager for orchestration
                    print(f"Multi-task execution: {[t.instruction for t in tasks]}")
                    executions = context_mgr.execute_tasks(
                        tasks=tasks,
                        shell_executor=shell_exec,
                        gui_executor=gui_exec,
                        text_injector=injector,
                        command_router=router,
                        vlm_client=vlm
                    )
                    
                    # Log summary of multi-task execution
                    summary = context_mgr.get_execution_summary()
                    elapsed_ms = int((time.time() - started_at) * 1000)
                    
                    # Log each task execution
                    for task_id, execution in executions.items():
                        task_success = execution.status.value == "completed"
                        event_logger.log(
                            user_request=f"{corrected_text} [task: {execution.task.instruction}]",
                            route_path=execution.result.get("path", "unknown") if execution.result else "failed",
                            generated_commands=execution.result.get("details", {}).get("results") if execution.result else None,
                            mouse_move_from=None,
                            mouse_click_at=None,
                            screenshot_before=None,
                            screenshot_after=None,
                            success=task_success,
                            error_message=execution.error or "",
                            execution_time_ms=int((execution.completed_at - execution.started_at) * 1000) if execution.completed_at and execution.started_at else 0,
                            audio_file="",
                        )
                    
                    print(f"Multi-task completed: {summary['completed']}/{summary['total_tasks']} successful")
            except Exception as e:
                print(f"Processing error: {e}")
                traceback.print_exc()
            finally:
                task_queue.task_done()

    threading.Thread(target=worker, daemon=True).start()
    
    def start_dictation():
        print("Recording...")
        audio.start()
    
    def stop_dictation():
        print("Processing...")
        audio_data = audio.stop()
        # enqueue processing to avoid blocking the key listener
        task_queue.put({"audio": audio_data})
        print("Enqueued speech for processing")
    
    # Start key listener for Right Option key
    listener = KeyListener(
        trigger_key='right_option',
        on_press=start_dictation,
        on_release=stop_dictation
    )
    
    try:
        listener.start()
        # Start continuous screen monitoring
        screen_monitor.start()
        # Start web server
        web_server.start()
        print("Ready! Hold RIGHT OPTION key (⌥) and speak...")
        print("The Right Option key is to the right of the spacebar")
        print("Also: Enable Terminal in System Settings > Privacy & Security > Accessibility")
        print("Web UI available at: http://localhost:8080")
        print("Single instance protection active")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nGoodbye!")
        listener.stop()
        return 0


if __name__ == "__main__":
    sys.exit(main())
 