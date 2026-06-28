import re
from pathlib import Path
from xml.sax.saxutils import escape
from typing import Optional
from .i18n import t

def parse_diff_to_xml(diff_content):
    """Git DiffをXML形式に変換する"""
    diff_lines = diff_content.split('\n')
    output = []
    
    output.append("以下より<changeset>")
    output.append("<changeset>")
    
    current_file = None
    current_file_index = None
    current_change_type = "modification"
    current_binary = False
    current_scope = ""
    in_chunk = False
    added_lines = []
    removed_lines = []
    
    def flush_chunk():
        nonlocal in_chunk, added_lines, removed_lines
        if not in_chunk:
            return
            
        if added_lines and removed_lines:
            c_type = "modification"
        elif added_lines:
            c_type = "addition"
        else:
            c_type = "deletion"

        output.append(f'    <chunk scope="{escape(current_scope)}">')
        output.append(f'      <type>{c_type}</type>')
        
        if removed_lines:
            content = "\n".join(removed_lines)
            output.append(f'      <original>\n{escape(content)}\n      </original>')
        
        if added_lines:
            content = "\n".join(added_lines)
            output.append(f'      <modified>\n{escape(content)}\n      </modified>')
            
        output.append('    </chunk>')
        
        added_lines.clear()
        removed_lines.clear()
        in_chunk = False

    def flush_file():
        nonlocal current_file, current_file_index, current_binary, current_change_type
        flush_chunk()
        if not current_file:
            return

        if current_binary and current_file_index is not None:
            extension = Path(current_file).suffix
            output[current_file_index] = (
                f'  <file path="{current_file}" binary="true" '
                f'extension="{escape(extension)}" type="{current_change_type}">'
            )

        output.append("  </file>")
        current_file = None
        current_file_index = None
        current_binary = False
        current_change_type = "modification"

    for line in diff_lines:
        if line.startswith("diff --git"):
            flush_file()
             
            match = re.search(r"diff --git (.*?) (.*)", line)
            file_path = match.group(2) if match else "unknown"
            current_file = file_path
            current_file_index = len(output)
            output.append(f'  <file path="{file_path}">')
            continue

        if current_file and line.startswith("new file mode"):
            current_change_type = "addition"
            continue

        if current_file and line.startswith("deleted file mode"):
            current_change_type = "deletion"
            continue

        if current_file and (line.startswith("Binary files ") or line.startswith("GIT binary patch")):
            current_binary = True
            continue

        if line.startswith("@@"):
            flush_chunk()
            scope_match = re.search(r"@@.*?@@\s*(.*)", line)
            current_scope = scope_match.group(1).strip() if scope_match else "global"
            in_chunk = True
            continue
            
        if in_chunk:
            if line.startswith("-") and not line.startswith("---"):
                removed_lines.append(line[1:])
            elif line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])

    flush_file()
    output.append("</changeset>")
    
    return "\n".join(output)

def build_prompt(system_prompt: str, recent_logs: Optional[str], user_context: str, diff_content: str, reference_content: Optional[str] = None) -> str:
    """最終的なプロンプトを構築する"""
    full_payload = [system_prompt, "\n---\n"]
    
    if reference_content:
        full_payload.append(t("prompt.reference_files_title"))
        full_payload.append(reference_content)
        full_payload.append("\n---\n")
    
    if recent_logs:
        full_payload.append(t("prompt.recent_logs_title"))
        full_payload.append(t("prompt.recent_logs_instruction", recent_logs))
        full_payload.append("\n---\n")
    
    if user_context:
        full_payload.append(t("prompt.user_context_title"))
        full_payload.append(t("prompt.user_context_instruction", user_context))
        full_payload.append("\n---\n")

    xml_output = parse_diff_to_xml(diff_content)
    full_payload.append(xml_output)

    return "\n".join(full_payload)

def clean_markdown_code_block(text: str) -> str:
    """LLMが生成したマークダウンのコードブロック(```)を除去する"""
    if not text:
        return text
    
    text = text.strip()
    match = re.match(r'^```[^\n]*\n(.*)```$', text, re.DOTALL)
    if match:
        return match.group(1).strip()
        
    return text
