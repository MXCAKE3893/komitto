import subprocess
import sys

def get_git_diff():
    """ステージングされた変更を取得する"""
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Error: Not a git repository.", file=sys.stderr)
        sys.exit(1)

    cmd = ["git", "diff", "--staged", "--no-prefix", "-U0"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    
    if not result.stdout:
        print("Warning: No staged changes found. (Use 'git add' first)", file=sys.stderr)
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
