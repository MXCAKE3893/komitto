import re
from xml.sax.saxutils import escape

def parse_diff_to_xml(diff_content):
    """Git DiffをXML形式に変換する"""
    diff_lines = diff_content.split('\n')
    output = []
    
    output.append("以下より<changeset>")
    output.append("<changeset>")
    
    current_file = None
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

    for line in diff_lines:
        if line.startswith("diff --git"):
            flush_chunk()
            if current_file:
                output.append("  </file>")
            
            match = re.search(r"diff --git (.*?) (.*)", line)
            file_path = match.group(2) if match else "unknown"
            current_file = file_path
            output.append(f'  <file path="{file_path}">')
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

    flush_chunk()
    if current_file:
        output.append("  </file>")
    output.append("</changeset>")
    
    return "\n".join(output)

def build_prompt(system_prompt: str, recent_logs: str | None, user_context: str, diff_content: str) -> str:
    """最終的なプロンプトを構築する"""
    full_payload = [system_prompt, "\n---\n"]
    
    if recent_logs:
        full_payload.append("## 📜 直近のコミット履歴（参考情報）")
        full_payload.append(f"以下の履歴を踏まえて、文脈や形式を考慮してください:\n\n{recent_logs}")
        full_payload.append("\n---\n")
    
    if user_context:
        full_payload.append("## 💡 ユーザーからの追加コンテキスト（補足情報）")
        full_payload.append(f"ユーザーメモ: {user_context}")
        full_payload.append("\n---\n")

    xml_output = parse_diff_to_xml(diff_content)
    full_payload.append(xml_output)

    return "\n".join(full_payload)
