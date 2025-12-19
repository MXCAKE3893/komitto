# komitto (commit)

[English](./README.md) | [日本語](./README-ja.md)

A CLI tool for generating semantic commit message prompts from `git diff` information. The generated prompt is automatically copied to the clipboard, allowing you to paste it into an LLM to create your commit message.

## Key Features

- Analyzes staged changes (`git diff --staged`)
- Converts change details into an XML format that is easily understandable by LLMs
- **LLM API Integration**: Directly calls APIs from providers like OpenAI, Gemini, Anthropic, and Ollama to automatically generate commit messages
- **Contextual Understanding**: Automatically includes recent commit logs in the prompt to consider project context and style
- Combines with system prompts specifically designed for commit message generation
- Copies the final generated prompt to the clipboard
- Provides functionality to attach additional context about the changes via command-line arguments
- **Interactive Mode**: Review, edit, regenerate, or commit the generated message in an interactive session
- **Editor Integration**: Edit the commit message using your preferred editor
- **Robust Error Handling**: Gracefully handles various error scenarios with helpful feedback

## Installation

```bash
pip install komitto
```

For development installation, use the following command:

```bash
pip install -e .
```

## Language Support

komitto automatically detects your language based on your OS locale settings.
Currently supported languages are:
- English (`en`) - Default
- Japanese (`ja`)

To force a specific language, you can set the `KOMITTO_LANG` environment variable:

```bash
# Linux/macOS
export KOMITTO_LANG=ja

# Windows (PowerShell)
$env:KOMITTO_LANG="ja"
```

## Usage

### Basic Usage (Prompt Generation Mode)

1. Make changes in a repository and stage files using `git add`.
2. Run the `komitto` command.
3. The generated prompt will be copied to your clipboard - simply paste it into ChatGPT or another LLM.

```bash
komitto
# -> The generated prompt has been copied to your clipboard!
```

### AI Automated Generation Mode (Recommended)

By configuring API settings in the `komitto.toml` configuration file, the `komitto` command will automatically invoke the API when executed, directly copying the generated commit message to your clipboard.

```bash
komitto
# -> 🤖 AI is currently generating a commit message...
# -> ✅ The generated message has been copied to your clipboard!
```

### Interactive Mode

Run with the `-i` or `--interactive` flag to review and edit the generated message before committing.

```bash
komitto -i
```

You can choose from the following actions:
- **y: Accept (Commit)**: Accepts the message and automatically executes `git commit`.
- **e: Edit**: Opens an editor to modify the message.
- **r: Regenerate**: Regenerates the message.
- **n: Cancel**: Exits without doing anything.

**Note**: Interactive mode is only available when LLM API settings are configured in `komitto.toml`.

### Passing Additional Context

If you have supplementary information you want to include in the prompt, such as the purpose behind your changes or any special notes, you can pass it as command-line arguments.

 Example:
```bash
komitto "This change is an emergency bug fix"
```

### Editor Integration

When using the interactive mode, you can edit the generated message using your preferred editor. The editor is determined in the following order:
- `GIT_EDITOR` environment variable
- `VISUAL` environment variable
- `EDITOR` environment variable
- Git's configured `GIT_EDITOR`
- Default editor (notepad on Windows, vi on other platforms)

```bash
komitto -i
e
# -> Opens editor to modify the message
```


## Customization via Configuration File

You can generate a template configuration file (`komitto.toml`) for your current directory by running the following command:

```bash
komitto init
```

You can customize the prompt content by creating a TOML-formatted configuration file.
The system will search for configuration files in the following order, and any found settings will override the default settings (with later configurations taking precedence).

1. **OS-specific user configuration directory** (global settings)
    * **Windows**: `%APPDATA%\komitto\config.toml`
    * **macOS**: `~/Library/Application Support/komitto/config.toml`
    * **Linux**: `~/.config/komitto/config.toml`
2. **Current directory** (project-specific settings)
    * `./komitto.toml`

### Example Configuration File Entries (`komitto.toml` / `config.toml`)

```toml
[prompt]
# Overwrite the default system prompt
system = """
You are a helpful assistant that generates semantic commit messages.
Please analyze the provided diff information and create a concise and descriptive commit message following Conventional Commits format.
"""

[llm]
# Set the following parameters when using AI-generated content
provider = "openai" # Options: "openai", "gemini", "anthropic"

# Model specification
model = "gpt-5.2" # or other available models

# API key (uses environment variables OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, etc. if not specified)
api_key = "sk-..." 

# For using Ollama/LM Studio, etc.
# base_url = "http://localhost:11434/v1"

# Number of previous commit history entries to include in the prompt (default: 5)
history_limit = 5

[git]
# Files to exclude from the diff analysis (glob patterns)
# Default excludes: package-lock.json, yarn.lock, pnpm-lock.yaml, poetry.lock, Cargo.lock, go.sum, *.lock
exclude = [
    "package-lock.json",
    "yarn.lock",
    "*.lock"
]
```

### Using Ollama/LM Studio

To use Ollama or LM Studio as your LLM provider, configure the `base_url` parameter:

```toml
[llm]
provider = "openai"
model = "qwen3"
base_url = "http://localhost:11434/v1"
# Optional: API key might not be required for local instances
# api_key = "dummy"
```

This allows you to use locally hosted LLM models while still using the OpenAI-compatible API interface.


## How It Works

1.  Executes `git diff --staged` to retrieve differences between staged files.
2.  Converts the diff information into a structured XML format containing details such as file paths, function/class names, and types of changes (additions, modifications, deletions).
3.  Combines the predefined system prompt, any user-specified additional context, and the XML-formatted diff information to generate the final prompt.
4.  Copies the generated prompt to the clipboard.
