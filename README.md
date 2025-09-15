# Dados

**Intelligent, privacy-first real-time voice OS agent for sub-second actions and navigation.**

note-This is a work in progress and you are likely to find errors while running, for now- however, some functionality is great.

Hold **Right Option (⌥)** and speak to control your computer or dictate text into any app. You can also use the local Web UI.

## How it works

1. Hold down the **Right Option (⌥)** key - to the right of spacebar
2. Speak naturally
3. Release **Right Option** key
4. Text appears in your active app

## Features

- **Privacy-first**: All processing happens locally on your device
- **Works across the OS**: Operates at the operating system level, across all apps
- **Fast**: Sub-second actions and navigation
- **Simple**: Hold Right Option (⌥) and speak, or use the Web UI
- **Ultra-fast actions**: Deterministic commands + model generated commands  
- **Auto-start**: Runs automatically when you log in

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

## Auto-Start Setup

To have Dados automatically start when you log in:

```bash
# 1. Create your custom plist file from template
cp com.dados.agent.plist.template com.dados.agent.plist

# 2. Edit the file and replace "/path/to/your/dados" with your actual path
# 3. Copy service file to LaunchAgents
cp com.dados.agent.plist ~/Library/LaunchAgents/

# 4. Load the service (starts immediately and on every login)
launchctl load ~/Library/LaunchAgents/com.dados.agent.plist
```

## Service Management

Use the included service control script:

```bash
# Check if service is running
./service_control.sh status

# Start the service
./service_control.sh start

# Stop the service
./service_control.sh stop

# Restart the service
./service_control.sh restart

# View recent logs
./service_control.sh logs

# Disable auto-start completely
./service_control.sh disable
```

## Usage

Run the app and hold **Right Option (⌥)** while speaking. Dados will execute commands, navigate UI, or type text depending on context.

**Important**: If actions don't occur, you may need to grant permissions:

- **System Settings** → **Privacy & Security** → **Accessibility** (for keyboard/mouse control)
- **System Settings** → **Privacy & Security** → **Screen Recording** (for screenshots)

Once the service is running, just **hold Right Option (⌥) and speak** — it's always ready! Or open `index.html` to use the Web UI button.

Press **Ctrl+C** to quit (if running manually).

## Supervised Fine-Tuning Data Collection

Dados can optionally collect local data for improving command generation and UI targeting:

- **Events CSV**: `data/csv/events.csv` stores rows with fields like `timestamp`, `user_request`, `generated_commands`, `mouse_move_from`, `mouse_click_at`, `screenshot_before`, `screenshot_after`, `execution_success`, `error_message`, `execution_time_ms`, `audio_file`.
- **Screenshots**: `data/screenshots/` capture before/after context to supervise vision-language targeting.
- **Audio**: `data/audio/` stores `.wav` audio tied to requests for improving STT or instruction parsing.

At a high level, you fine-tune by preparing datasets from these logs and training your LFM (command generation) and/or VLM (click targeting) to reduce errors.

## Need Help?

If you need help setting up Dados, email a {at} beesumbodi.me.

## License

Dados is licensed under the MIT License.

## Context

**On-device agentic computing.** I can use my voice to get my computer to do anything. For example, I can tell my computer to "send my boss an email saying that I won't be in tomorrow". "And then while you're doing that, also play that video about Sam Altman and Tucker Carlson from my Youtube watch later. Play that in the background.", "And after you've done that, I would like you to do some research on LiquidAI's Vision language models. Research its capabilities and what it can do. Send a report to me, to my email." "Finally, I am due to go to the US soon, finish off my VISA application please; you can find my details on my Notion page".

**Beyond mere agentic browsers.** I can tell my computer what to do at the **operating system level**, sharing context across all apps, all my files, and it also has a **data pipeline for learning** through supervised fine-tuning which I have partially set up.

**Autonomous operation.** While the computer does all this, I do not need to be present; I can be watching Netflix, or go for a walk, or literally anything else. 

**Problem:** I'm a lazy computer user. I want to be able to **kill context switching** and spend my time doing other things, such as being with my family and writing about philosophy rather than mundane tasks.

**Accessibility benefits.** Additionally, people with accessibility issues/disabilities that cannot continuously type can significantly benefit from being able to intelligently control computers with **voice only**. It is **non-invasive** compared to companies like Neuralink, and **less ambiguous** as accuracy (user intent) is higher.
