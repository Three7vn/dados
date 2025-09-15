# Dados: Voice-First Operating System Agent (Local, Private, Agentic)

Voice-first computing for lazy people.

## 0. Scope and Goals

- Voice-only control of a laptop/desktop to perform real tasks (open apps, open links, compose emails, manipulate UI, run shell commands).
- Local-only execution: audio, screenshots, model inference, and actions all occur on-device.
- Asynchronous, autonomous operation: the system may perform multiple tasks in parallel (e.g., play music, push code, draft an email) while the user does something else.
- Reliability over novelty: deterministic shortcuts for known actions; ML-based inference for unknown UI states.
- Safety: capability gating, confirmation for dangerous actions, and immediate fail-safes.


## 1. Problem Statement and Target Users

- Primary persona: a user who prefers minimal effort (“lazy computing”) and wants to offload repetitive or multi-step computer tasks.
- Additional personas: busy professionals and users with accessibility needs who benefit from hands-free control.
- Objective: turn an ordinary personal computer into an agentic computer at the OS level, unified across apps (email, browser, IDE, etc.).

## 2. High-Level Architecture

```text
Voice (mic) → STT (Whisper) → Text Correction (Liquid LFM2) → Intent Parsing
  → (A) Deterministic Command Library → Shell Executor / App Launcher
  → (B) GUI Automation (PyAutoGUI) + Screenshots → VLM (Liquid LFM2-VL)
       → Target inference → Pre-click verification → Cursor/Key actions
  → (C) Text Injection (existing injector) for typing into fields

All steps → Context Manager (task graph + state) → Logging/Telemetry (JSON)
```

### 2.1 Core Components

- Audio Input: reuse `src/audio_capture.py` (PyAudio) to stream 16kHz mono audio frames.
- Speech-to-Text (STT): Whisper (or Faster-Whisper for performance) converts audio to raw text.
- Real-time Text Correction: Liquid LFM2 (language model) cleans grammar and resolves minor STT errors for text that will be injected.
- Intent Parser / Command Router:
  - Interprets utterances into actions.
  - Routes to (A) shell/app commands, (B) GUI automation with VLM assist, or (C) direct text injection.
- Command Library (deterministic):
  - JSON/DB that maps phrases to pre-approved actions (e.g., open a known URL like a YouTube playlist, open Gmail compose URL, run `git` workflow). 
  - Provides predictable, fast paths for common requests.
- GUI Automation: `pynput` for mouse/keyboard control; `PyAutoGUI` for full-desktop screenshots.
- Vision-Language Model (VLM): Liquid LFM2-VL processes screenshots to infer screen context (buttons, inputs) and propose click targets.
- Executor:
  - Shell Executor for commands (`open`, `osascript`, `git`, etc.).
  - GUI Executor using `pynput` for mouse/keyboard actions.
  - Text Injector: reuse `src/injector.py` for fast, reliable typing (requires Accessibility permission).
- Context Manager:
  - Maintains action plan and state for each user request (task graph), tracks progress, manages retries, and coordinates concurrency.
- Telemetry & Storage:
  - JSON logs of actions, decisions, and results.
  - On-device datasets for improvement (`data/` CSV + audio, plus screenshots for VLM).
  - Dictionary of deterministic phrase→command mappings.
- Local Web UI:
  - Start/stop listening, view active tasks, approve/deny sensitive actions, monitor logs and screenshots, and quickly trigger saved commands.

### 2.2 Processing Pipelines

1) Dictation/Text Injection Path
- Audio → Whisper → Liquid LFM2 correction → `TextInjector.type()`.
- Used when the intent is to enter text into a focused field.

2) Deterministic Command Path
- Utterance → parse → match in Command Library → run one or more shell commands/app launches.
- Examples:
  - "Open my playlist" → `open "<stored_playlist_url>"`.
  - "Push latest code" → `git add -A` → `git commit ...` → `git push`.

3) GUI Automation Path
- Triggered for UI interactions (click buttons, fill forms) where deterministic paths don’t exist.
- Steps:
  1. Capture full-screen with PyAutoGUI.
  2. Send screenshot to LFM2-VL (via local llama.cpp server) with prompt of desired action (e.g., "click Compose").
  3. Receive predicted target(s) (coordinates/bboxes, labels).
  4. Pre-click verify: capture a fresh screenshot and re-check target proximity/state.
  5. Move cursor, click, optionally verify result (e.g., new element appears).
  6. If needed, type via `TextInjector` or `pynput` keystrokes.

### 2.3 Instruction-to-Command Execution Flow

From natural language instruction to terminal/GUI execution:

1. **Voice Input**: User speaks instruction (e.g., "push my latest code to GitHub")
2. **Speech-to-Text**: Whisper transcribes audio to raw text
3. **Grammar Correction**: Liquid LFM2 cleans transcription errors
4. **Intent Parsing & Command Generation**: LFM2 analyzes corrected text with augmented context:
   - JSON command library (aliases, apps, workflows) provided as context to the model
   - PyAutoGUI operation list (click, scroll, type, screenshot)
   - Current screen context (if screenshot available)
   - The model generates specific shell commands or identifies pre-defined workflows
5. **Route Decision**: System determines execution path:
   - **Path A (Deterministic)**: Direct match to JSON library entry (e.g., "open Chrome" → `open -a 'Google Chrome'`)
   - **Path B (Generated Commands)**: LFM2 generates shell command sequence (e.g., "push code" → `["git", "add", "-A"], ["git", "commit", "-m", "..."], ["git", "push"]`)
   - **Path C (GUI Automation)**: Requires screen interaction via PyAutoGUI + VLM
   - **Path D (Text Injection)**: Direct typing into focused field
6. **Command Execution**:
   - **Shell commands**: Python `subprocess.run()` executes generated command arrays
   - **GUI actions**: `pynput` moves/clicks at coordinates from VLM inference; `PyAutoGUI` only for screenshots
   - **App launching**: macOS `open` command or direct executable paths
7. **Verification**: Screenshot comparison (before/after) to confirm action success

**Terminal Access**: The system doesn't "open" a terminal window visually. Instead:
- Uses Python's `subprocess.run()` or `os.system()` to execute shell commands directly
- Commands run in background processes with captured stdout/stderr
- For interactive commands, can spawn persistent shell sessions via `subprocess.Popen()`

### 2.4 Context Manager and Concurrency

- Each user request produces a task graph with dependencies. Example:
  - Request: "Play my favorite playlist and push code, then email my manager." → three tasks, two can start immediately, third (email) gated on Gmail being ready.
- Concurrency:
  - Shell tasks run asynchronously.
  - GUI interactions serialized per target window to avoid race conditions, but different apps/tasks can run in parallel.
- Recovery & Retries:
  - If VLM target is ambiguous, ask the model again with different crop/zoom or fall back to deterministic keyboard shortcuts.

## 3. Command Library and Augmented Context

- **Purpose**: Acts as a knowledge base that augments LFM2's context, enabling fast recognition of common patterns without extensive reasoning.
- **Structure**: JSON store with aliases, apps, URLs, and multi-step workflows.
- **Integration**: The entire JSON library is provided as context to LFM2 during intent parsing, allowing the model to:
  - Directly map phrases like "open Chrome" to exact commands: `open -a 'Google Chrome'`
  - Recognize workflow patterns like "push code" and generate the full git sequence
  - Avoid hallucinating command syntax by referencing known-good examples

- **Example JSON structure**:

```json
{
  "aliases": {
    "my_youtube_playlist": "https://www.youtube.com/playlist?list=REDACTED",
    "gmail_compose": "https://mail.google.com/mail/u/0/#inbox?compose=new"
  },
  "apps": {
    "chrome": "open -a 'Google Chrome'",
    "vscode": "open -a 'Visual Studio Code'"
  },
  "workflows": {
    "push_latest_code": [
      "git add -A",
      "git commit -m 'Auto-commit from voice agent'",
      "git push"
    ]
  }
}
```

- **Command Generation Flow**:
  1. User instruction: "open Chrome and push my code"
  2. LFM2 receives instruction + full JSON context
  3. Model generates: `[["open", "-a", "Google Chrome"], ["git", "add", "-A"], ["git", "commit", "-m", "Auto-commit"], ["git", "push"]]`
  4. Python executor runs each command via `subprocess.run()`

- **Safety**:
  - Allowlist actions by default; require explicit opt-in for destructive commands (e.g., `rm -rf`).
  - Confirmation gates for high-risk items (delete, terminate processes, credential changes).

## 4. Models and Runtime

- Whisper STT:
  - `openai-whisper` or `faster-whisper` (smaller footprint). Maintain 16 kHz mono audio.
- Liquid LFM2 (language):
  - Used for grammar correction and intent parsing assistance.
  - Runs locally via llama.cpp with quantized models for CPU efficiency.
- Liquid LFM2-VL (vision-language):
  - Model: `gabriellarson/LFM2-VL-1.6B-GGUF` (quantized HuggingFace model).
  - Used to interpret screenshots, recognize UI elements, and propose interaction targets.
  - Runs via llama.cpp inference engine for optimal laptop/desktop performance.
- Deployment:
  - llama.cpp serves models via OpenAI-compatible HTTP server locally.
  - Python bindings call chat/completions endpoints for both text and vision tasks.
  - Command library JSON (under `src/dictionary/command_library.json`) is injected into LFM2 prompts as context, enabling direct command recognition and generation.
  - Available automation operations provided to models: `pynput` (mouse/keyboard) and `pyautogui.screenshot()` for vision.

## 5. GUI Automation and Screenshots

- Use `pynput` for:
  - Mouse move/click/drag, scroll, keypresses, and window focus.
- Use `PyAutoGUI` for:
  - Full-desktop screenshots (`pyautogui.screenshot()`), saved/compressed locally.
- Pre-click verification loop:
  - Initial screenshot → VLM target inference → move cursor near target.
  - Fresh screenshot before click to validate that the expected element is still present and not moved; abort if mismatch.
- Fail-safes:
  - Global keyboard abort (e.g., ESC) monitored via `pynput`.

## 6. Text Injection and Keyboard Control

- Reuse `src/injector.py` (pynput Controller.type) for fast, reliable typing.
- Accessibility permission is required on macOS.
- Fallback: clipboard-based paste for large text blocks if needed.

## 7. Shell Execution and App Launching

- macOS examples:
  - `open -a "Google Chrome"` to launch apps.
  - `open "<URL>"` to open links.
  - `osascript` for AppleScript-driven UI automation when deterministic.
- Git workflows: commit/push with clear prompts or pre-configured messages.
- Process control: `killall "AppName"` if explicitly allowed.

## 8. Security, Privacy, and Safety

- Everything runs locally; no cloud calls.
- Capability gating by category: filesystem, networking, process control, input automation.
- Allowlist/denylist enforcement per user settings.
- Confirm-before-execute for dangerous operations.
- Screen Recording and Accessibility permissions must be granted to enable screenshots and input control.

## 9. Data, Telemetry, and Learning Loops

- Logging (JSON): intents, actions, results, errors, screenshots (paths), and timings etc..

## 10. Core Flow

- Core features to deliver quickly:
  1) Voice capture → Whisper STT → Liquid LFM2 correction.
  2) Command Library to run: open app, open URL, push code, start email compose.
  3) PyAutoGUI cursor control and full-screen screenshots.
  4) LFM2-VL loop to target and click a button (e.g., Gmail "Compose").
  5) Text injection into input fields (subject/body).
  6) Safety gates and fail-safes enabled.

- Demo script example:
  - "Play my favorite playlist" (deterministic URL) → Chrome opens → VLM clicks Play.
  - "Push latest code" → git add/commit/push in background terminal.
  - "Email my manager I'm running late" → open Gmail compose → VLM clicks Compose → injector types to/subject/body.



