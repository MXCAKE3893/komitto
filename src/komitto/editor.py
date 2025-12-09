import os
import subprocess
import tempfile
import textwrap
import sys

def launch_editor(initial_message: str) -> str:
    """環境変数で指定されたエディタを起動してメッセージを編集させる"""
    # エディタの特定: 環境変数 -> git var GIT_EDITOR -> デフォルト
    editor = os.environ.get('GIT_EDITOR') or \
             os.environ.get('VISUAL') or \
             os.environ.get('EDITOR')

    if not editor:
        try:
            result = subprocess.run(['git', 'var', 'GIT_EDITOR'], capture_output=True, text=True, encoding='utf-8')
            if result.returncode == 0 and result.stdout:
                editor = result.stdout.strip()
        except Exception:
            pass

    if not editor:
        editor = 'notepad' if os.name == 'nt' else 'vi'

    with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8', suffix=".txt") as tmp_file:
        tmp_file_path = tmp_file.name
        tmp_file.write(initial_message.strip() + "\n\n")
        tmp_file.write(textwrap.dedent("""
            # --- komitto interactive mode ---
            # コミットメッセージを編集してください。
            # '#' で始まる行は最終的なメッセージから除外されます。
        """).strip())
    
    try:
        if os.name == 'nt':
            cmd = f'{editor} "{tmp_file_path}"'
            subprocess.run(cmd, check=True, shell=True)
        else:
            import shlex
            cmd_args = shlex.split(editor)
            cmd_args.append(tmp_file_path)
            subprocess.run(cmd_args, check=True)
        
        with open(tmp_file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        cleaned_lines = [line for line in lines if not line.strip().startswith('#')]
        return "".join(cleaned_lines).strip()
        
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"⚠️ エディタ '{editor}' の起動に失敗しました ({e})。編集をキャンセルします。", file=sys.stderr)
        return initial_message
    finally:
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
