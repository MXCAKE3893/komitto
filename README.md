# komitto (commit)

[English](./README.md) | [日本語](./README-ja.md)

A CLI tool for generating semantic commit message prompts from `git diff` information. The generated prompt is automatically copied to the clipboard, allowing you to paste it into an LLM to create your commit message.

## Key Features

- Analyzes staged changes (`git diff --staged`) and optionally compares multiple contexts.
- Converts change details into a structured XML/JSON format that LLMs can understand.
- **LLM API Integration**: Directly calls APIs from providers like OpenAI, Gemini, Anthropic, Ollama, etc., using settings defined in `komitto.toml`.
- **Contextual Understanding**: Automatically includes recent commit logs in the prompt to preserve project context and style.
- **Style Learning** (`komitto learn`): Analyzes your commit history to generate a custom system prompt that matches your project's commit style.
- Combines with system prompts specifically designed for commit message generation; templates can be overridden per-context, per-template, or per-model.
- Copies the final generated prompt (or raw LLM output) to the clipboard.
- Provides functionality to attach additional context about the changes via command-line arguments.
- **Interactive Mode** (`-i`/`--interactive`): Review, edit, regenerate, or commit the generated message in a rich TUI interface.
- **TUI Interface**: Built with [Textual](https://textual.textualize.io/) for a modern terminal experience with real-time streaming.
- **Editor Integration**: Edit the commit message using your preferred editor (VISUAL/EDITOR/GIT_EDITOR).
- **Robust Error Handling**: Gracefully handles various error scenarios with helpful feedback.

## Installation

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

### Prompt Generation Mode (Default)

1. Stage changes with `git add`.
2. Run `komitto`.
3. The generated prompt is copied to your clipboard.

```bash
komitto
# -> Prompt copied!
```

### AI-Automated Generation (Recommended when configured)

Configure `provider`, `model`, and other API settings in `komitto.toml`. Then running `komitto` will call the LLM, stream tokens, and copy the final commit message to the clipboard.

```bash
komitto
# -> 🤖 Generating...
# -> ✅ Copied!
```

### Interactive Mode

```bash
komitto -i
```

Available commands during the interactive loop:
- `y` – Accept and commit (`git commit -m <msg>`)
- `e` – Edit the message in an external editor
- `r` – Regenerate
- `n` or `Ctrl-C` – Cancel

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

[llm]
provider = "openai"
model = "gpt-4o"
api_key = "${OPENAI_API_KEY}"
base_url = "https://api.openai.com/v1"

history_limit = 5

[templates.simple]
system = "[{prompt}] Commit message: "

[contexts.release]
template = "simple"
model = "gpt4"

# Excludes are merged from defaults; add project-specific patterns:
[git]
exclude = [
    "node_modules/**",
    "*.lock"
]
```

### Using Ollama/LM Studio

```toml
[llm]
provider = "openai"        # still used for compatibility layer
model = "qwen3"
base_url = "http://localhost:11434/v1"
# No api_key needed for most local setups
```

## How It Works (Internal Flow)

1. `git diff --staged` retrieves staged changes.
2. Differences are transformed into a structured representation (`file path | operation | surrounding function/class signatures`) in XML-like format.
3. The configuration file defines a *system prompt*; this is merged with any user-provided context and the diff representation to produce the final LLM input.
4. Depending on CLI flags, the tool either streams tokens live (Rich UI) or returns a complete string instantly.
5. The resulting text is copied to the clipboard; in interactive mode the user can accept, edit, regenerate, or cancel.

## License

MIT © 2024-2025