import pytest
from komitto.prompt import parse_diff_to_xml, build_prompt
from komitto.i18n import set_language

@pytest.fixture(autouse=True)
def set_test_locale():
    # 結合プロンプトの見出しが固定されるように英語にしておく
    set_language("en")

def test_parse_diff_to_xml_modification():
    """修正差分（modification）が正しくパースされ、original と modified に分かれることをテスト"""
    diff = """diff --git src/main.py src/main.py
@@ -10,3 +10,3 @@ def my_func():
-old_line
+new_line
"""
    xml = parse_diff_to_xml(diff)
    
    assert '<file path="src/main.py">' in xml
    assert '<chunk scope="def my_func():">' in xml
    assert '<type>modification</type>' in xml
    assert '<original>\nold_line\n      </original>' in xml
    assert '<modified>\nnew_line\n      </modified>' in xml
    assert '</chunk>' in xml
    assert '</file>' in xml

def test_parse_diff_to_xml_addition():
    """追加差分（addition）が正しくパースされ、modified のみが出力されることをテスト"""
    diff = """diff --git src/main.py src/main.py
@@ -1,2 +1,3 @@
+added_line1
+added_line2
"""
    xml = parse_diff_to_xml(diff)
    
    assert '<type>addition</type>' in xml
    assert '<original>' not in xml
    assert '<modified>\nadded_line1\nadded_line2\n      </modified>' in xml

def test_parse_diff_to_xml_deletion():
    """削除差分（deletion）が正しくパースされ、original のみが出力されることをテスト"""
    diff = """diff --git src/main.py src/main.py
@@ -5,2 +5,0 @@
-removed_line1
-removed_line2
"""
    xml = parse_diff_to_xml(diff)
    
    assert '<type>deletion</type>' in xml
    assert '<modified>' not in xml
    assert '<original>\nremoved_line1\nremoved_line2\n      </original>' in xml

def test_parse_diff_to_xml_escape_special_characters():
    """XML特殊文字が正しくエスケープされてXML要素に組み込まれることをテスト"""
    diff = """diff --git a/src/test&demo.py b/src/test&demo.py
@@ -1,2 +1,2 @@ def my_func(a < b):
-if a < b and b > c:
+if a < b & b > c:
"""
    xml = parse_diff_to_xml(diff)
    
    # パスがエスケープされていないこと（仕様通り）
    assert '<file path="b/src/test&demo.py">' in xml
    # スコープ名がエスケープされていること
    assert '<chunk scope="def my_func(a &lt; b):">' in xml
    # 差分内容がエスケープされていること
    assert '<original>\nif a &lt; b and b &gt; c:\n      </original>' in xml
    assert '<modified>\nif a &lt; b &amp; b &gt; c:\n      </modified>' in xml

def test_parse_diff_to_xml_no_scope():
    """@@ ヘッダにスコープ名が記載されていない場合、空文字（""）が利用されることをテスト"""
    diff = """diff --git a/index.html b/index.html
@@ -1,1 +1,2 @@
+<!DOCTYPE html>
"""
    xml = parse_diff_to_xml(diff)
    assert '<chunk scope="">' in xml

def test_parse_diff_to_xml_multiple_files():
    """複数ファイルの変更差分が、それぞれの file 要素に正しく収まることをテスト"""
    diff = """diff --git a/a.txt b/a.txt
@@ -1,1 +1,2 @@
+a_change
diff --git a/b.txt b/b.txt
@@ -5,1 +5,1 @@
-b_old
+b_new
"""
    xml = parse_diff_to_xml(diff)
    
    # 構造のチェック
    assert '<file path="b/a.txt">' in xml
    assert '<file path="b/b.txt">' in xml
    # ファイルa内にbの変更が入っていないこと
    parts = xml.split('</file>')
    assert 'a_change' in parts[0]
    assert 'b_old' not in parts[0]
    assert 'b_old' in parts[1]

def test_build_prompt_full_parameters():
    """すべてのパラメータ（logs, context）が渡された場合、すべてのセクションが結合されたプロンプトが生成されることをテスト"""
    system_prompt = "You are a commit assistant."
    recent_logs = "Commit: 123456\nMessage: first commit"
    user_context = "refactoring login"
    diff_content = "diff --git a.txt a.txt\n@@ -1 +1 @@\n+change"
    
    prompt = build_prompt(system_prompt, recent_logs, user_context, diff_content)
    
    assert system_prompt in prompt
    # 見出しと内容
    assert "Recent Commit History" in prompt or "直近" in prompt or "recent_logs" in prompt
    assert "123456" in prompt
    assert "Additional Context from User" in prompt or "ユーザー" in prompt or "user_context" in prompt
    assert "refactoring login" in prompt
    # XML Diff部分
    assert "<changeset>" in prompt
    assert '<file path="a.txt">' in prompt

def test_build_prompt_missing_optional_parameters():
    """optional なパラメータ（logs や context）が None や空の場合、対応する見出しセクションが除外されることをテスト"""
    system_prompt = "System prompt"
    diff_content = "diff --git a.txt a.txt\n@@ -1 +1 @@\n+change"
    
    # logs と context を両方省略
    prompt = build_prompt(system_prompt, None, "", diff_content)
    
    assert system_prompt in prompt
    assert "<changeset>" in prompt
    
    # logs と context の見出しが含まれていないこと
    assert "Recent Commits" not in prompt
    assert "User Context" not in prompt
