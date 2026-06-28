# komitto (commit)

[![PyPI Downloads](https://static.pepy.tech/personalized-badge/komitto?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=BRIGHTGREEN&left_text=downloads)](https://pepy.tech/projects/komitto)

[English](https://github.com/mxcake3893/komitto/blob/main/README.md) | [日本語](https://github.com/mxcake3893/komitto/blob/main/README-ja.md)

A CLI tool that analyzes `git diff` and calls LLM APIs (OpenAI, Gemini, Anthropic, Ollama, etc.) to generate semantic commit messages. It can also learn your project's commit style from history (`komitto learn`) and apply it automatically.

<p align="center">
  <img src="https://raw.githubusercontent.com/mxcake3893/komitto/main/assets/komitto-demo.gif" alt="komitto running in terminal">
</p>

## Key Features

- Analyzes staged changes (`git diff --staged`) and optionally compares multiple contexts.
- Converts change details into a structured XML/JSON format that LLMs can understand.
- **LLM API Integration**: Directly calls APIs from providers like OpenAI, Gemini, Anthropic, Ollama, etc., using settings defined in `komitto.toml`.
- **Reasoning Process Visualization**: Streams and visualizes the LLM's reasoning process (e.g., `<think>` tags) in real-time.
- **Contextual Understanding**: Automatically includes recent commit logs in the prompt to preserve project context and style.
- **External File References**: Easily reference and embed the contents of external files into your prompt context.
- **Style Learning** (`komitto learn`): Analyzes your commit history to generate a custom system prompt that matches your project's commit style.
- Combines with system prompts specifically designed for commit message generation; templates can be overridden per-context, per-template, or per-model.
- Copies the final generated prompt (or raw LLM output) to the clipboard.
- Provides functionality to attach additional context about the changes via command-line arguments.
- **Interactive Mode** (`-i`/`--interactive`): Review, edit, regenerate, or commit the generated message in a rich TUI interface.
- **TUI Interface**: Built with [Textual](https://textual.textualize.io/) for a modern terminal experience with real-time streaming, loading spinners, and animations.
- **Editor Integration**: Edit the commit message using your preferred editor (VISUAL/EDITOR/GIT_EDITOR).

## Installation

komitto requires Python 3.9+.

```bash
pip install komitto
```

For development installation, use:

```bash
pip install -e .
```

## Language Support

komitto automatically detects your language based on OS locale. Supported languages:
- English (`en`) – default
- Japanese (`ja`)

Set `KOMITTO_LANG=ja` to force Japanese.

## Usage

### AI-Automated Generation (Recommended)

When you configure `provider`, `model`, and other API settings in `komitto.toml`, running `komitto` will directly interact with the LLM. It streams the reasoning process and the commit message generation in real-time, then provides an interactive prompt.

```bash
komitto
# -> ⏳ Generating...
# -> (Streams the reasoning and message)
# -> Commit message generated.
# -> [y] Accept and commit [e] Edit [r] Regenerate [n] Cancel:
```

Available commands during the interactive loop:
- `y` – Accept and commit (`git commit -m <msg>`)
- `e` – Edit the message in an external editor
- `r` – Regenerate
- `n` or `Ctrl-C` – Cancel

### Prompt Generation Mode (Manual)

If you haven't configured the `[llm]` section, komitto falls back to generating a prompt based on your staged changes and copies it to your clipboard.

```bash
komitto
# -> Prompt copied!
```

### Comparison Mode

Compare two different configurations side-by-side:

```bash
komitto --compare ctxA ctxB
```

Two columns are displayed; press `a` or `b` to select one, then commit or edit as usual.

### Passing Additional Context

Add free-form context that will be merged into the prompt:

```bash
komitto "Urgent bug fix for payment processing"
```

### Editor Integration

During interactive mode you can invoke the configured editor at any time. The selection order is:
1. `$GIT_EDITOR`
2. `$VISUAL`
3. `$EDITOR`
4. Git's built-in default (`notepad` on Windows, `vi` otherwise).

### Style Learning

Analyze your existing commit history to automatically generate a system prompt tailored to your project:

```bash
komitto learn
```

This command:
1. Reads recent commit messages from your repository
2. Analyzes the language, format, and conventions used
3. Generates a custom system prompt matching your style
4. Optionally updates `komitto.toml` automatically

### CLI Options

| Option                      | Description                                      |
|-----------------------------|--------------------------------------------------|
| `-i`, `--interactive`       | Enable interactive TUI mode                      |
| `-c`, `--context-name NAME` | Use a specific context profile from config       |
| `-t`, `--template NAME`     | Use a specific prompt template from config       |
| `-m`, `--model NAME`        | Use a specific model from config                 |
| `--compare CTX1 CTX2`       | Compare outputs from two context configurations  |

## Customization via Configuration File

Create a project-specific configuration with:

```bash
komitto init
```

Configuration files are looked up in this order (later overrides earlier):

1. User config directory (`%APPDATA%\komitto\config.toml`, etc.)
2. Project directory `./komitto.toml`

### Sample `komitto.toml`

```toml
[prompt]
system = """
You are a helpful assistant that produces semantic commit messages following Conventional Commits.
Analyze the diff below and output only the subject line (<=50 chars) and an optional body.
"""

[context]
# Reference files to always include in the prompt
# files = ["README.md"]

[llm]
provider = "openai" # "openai", "gemini", "anthropic"
model = "gpt-5.4-mini"
# api_key = "sk-..." # Optional if environment variable is set
# base_url = "http://localhost:11434/v1" # For Ollama etc.
# history_limit = 5
# timeout = 300 # Request timeout in seconds (default: 300)

[git]
# Files to exclude from the diff (glob patterns)
exclude = [
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Cargo.lock",
    "go.sum",
    "*.lock"
]

# --- Advanced Settings (Templates & Contexts) ---
# [templates.simple]
# system = "Summarize changes in one line."

# [models.gpt54mini]
# provider = "openai"
# model = "gpt-5.4-mini"

# [contexts.release]
# template = "simple"
# model = "gpt54mini"
```

### Using Ollama/LM Studio

```toml
[llm]
provider = "openai"        # still used for compatibility layer
model = "qwen3"
base_url = "http://localhost:11434/v1"
```

## How It Works (Internal Flow)

1. `git diff --staged` retrieves staged changes.
2. Differences are transformed into a structured representation (`file path | operation | surrounding function/class signatures`) in XML-like format.
3. The configuration file defines a *system prompt*; this is merged with any user-provided context and the diff representation to produce the final LLM input.
4. Depending on CLI flags, the tool either streams tokens live (Rich UI) or returns a complete string instantly.
5. The resulting text is copied to the clipboard; in interactive mode the user can accept, edit, regenerate, or cancel.

## License

MIT © 2025-2026
