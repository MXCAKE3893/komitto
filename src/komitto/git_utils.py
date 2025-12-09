import subprocess
import sys
from .i18n import t

def get_git_diff():
    """ステージングされた変更を取得する"""
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print(t("git_utils.not_a_repo"), file=sys.stderr)
        sys.exit(1)

    cmd = ["git", "diff", "--staged", "--no-prefix", "-U0"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    
    if not result.stdout:
        print(t("git_utils.no_staged_changes"), file=sys.stderr)
        sys.exit(1)
        
    return result.stdout

def get_git_log(limit=5):
    """直近のコミットメッセージと変更ファイルを取得する"""
    cmd = [
        "git", "log", 
        f"-n {limit}", 
        "--date=iso", 
        "--pretty=format:Commit: %h%nDate: %ad%nMessage:%n%B%n[Files]", 
        "--name-status"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        if result.returncode == 0 and result.stdout:
            logs = result.stdout.strip()
            formatted_logs = []
            for block in logs.split("Commit: "):
                if not block.strip():
                    continue
                formatted_logs.append(f"Commit: {block.strip()}")
            
            return "\n\n----------------------------------------\n\n".join(formatted_logs)
    except Exception:
        pass
    return None

def git_commit(message):
    """メッセージを指定してコミットを実行する"""
    if not message.strip():
        print(t("git_utils.commit_message_empty"), file=sys.stderr)
        return False

    cmd = ["git", "commit", "-m", message]
    try:
        # ユーザーにgitの出力を直接見せるため、capture_outputはしない
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False
