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

## Installation

```bash
pip install komitto
```

For development installation, use the following command:

```bash
pip install -e .
```

## Usage

### Basic Usage (Prompt Generation Mode)

1. Make changes in a repository and stage files using `git add`.
2. Run the `komitto` command.
3. The generated prompt will be copied to your clipboard - simply paste it into ChatGPT or another LLM.
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

### Passing Additional Context

If you have supplementary information you want to include in the prompt, such as the purpose behind your changes or any special notes, you can pass it as command-line arguments.

 Example:
```bash
komitto "This change is an emergency bug fix"
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
You are a cheerful engineer speaking in Kansai dialect.
...
"""

[llm]
# Set the following parameters when using AI-generated content
provider = "openai" # Options: "openai", "gemini", "anthropic"

# Model specification
model = "gpt-5"

# API key (uses environment variables OPENAI_API_KEY, etc. if not specified)
# api_key = "sk-..." 

# For using Ollama/LM Studio, etc.
# base_url = "http://localhost:11434/v1"

# Number of previous commit history entries to include in the prompt (default: 5)
history_limit = 5
```

## How It Works

1.  Executes `git diff --staged` to retrieve differences between staged files.
2.  Converts the diff information into a structured XML format containing details such as file paths, function/class names, and types of changes (additions, modifications, deletions).
3.  Combines the predefined system prompt, any user-specified additional context, and the XML-formatted diff information to generate the final prompt.
4.  Copies the generated prompt to the clipboard.
