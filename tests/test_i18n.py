import os
import locale
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from komitto.i18n import (
    detect_language,
    set_language,
    get_current_language,
    t,
    _load_translations
)

# テスト前に言語キャッシュをリセットするためのフィクスチャ
@pytest.fixture(autouse=True)
def reset_i18n_state():
    import komitto.i18n
    komitto.i18n._CURRENT_LANG = None
    _load_translations.cache_clear()
    yield
    komitto.i18n._CURRENT_LANG = None
    _load_translations.cache_clear()

def test_detect_language_env_priority():
    """環境変数 KOMITTO_LANG が最優先で検出されることをテスト"""
    with patch.dict(os.environ, {"KOMITTO_LANG": "fr"}):
        assert detect_language() == "fr"

def test_detect_language_locale_fallback():
    """環境変数がない場合、OSのロケール設定から検出されることをテスト"""
    with patch.dict(os.environ, {}, clear=True):
        # Jaロケールが返る場合
        with patch('locale.getlocale', return_value=('ja_JP', 'UTF-8')):
            assert detect_language() == "ja"
            
        # ロケール取得が失敗するか None を返す場合
        with patch('locale.getlocale', return_value=None):
            assert detect_language() == "en"

def test_detect_language_exception_fallback():
    """locale.getlocale() が例外を投げた場合に en にフォールバックすることをテスト"""
    with patch.dict(os.environ, {}, clear=True):
        with patch('locale.getlocale', side_effect=Exception("locale error")):
            assert detect_language() == "en"

def test_set_and_get_language():
    """set_language と get_current_language の組み合わせおよびキャッシュ挙動をテスト"""
    set_language("ja")
    assert get_current_language() == "ja"
    
    set_language("en")
    assert get_current_language() == "en"

def test_get_current_language_detects_if_none():
    """キャッシュがない場合、detect_language を用いて自動取得されることをテスト"""
    with patch("komitto.i18n.detect_language", return_value="ja") as mock_detect:
        assert get_current_language() == "ja"
        mock_detect.assert_called_once()
        # 二回目はキャッシュから返るため detect_language は呼ばれない
        assert get_current_language() == "ja"
        assert mock_detect.call_count == 1

def test_load_translations_file_not_found():
    """存在しない言語ファイルが指定された場合、en.json にフォールバックすることをテスト"""
    # 存在しない言語 "xyz" を指定
    translations = _load_translations("xyz")
    # en.json が読まれていることをアサーション（適当な英語キーが存在すること）
    assert "main" in translations

@patch("builtins.open", side_effect=IOError("Permission denied"))
def test_load_translations_io_error(mock_open):
    """ファイル読み込み中にIOErrorが発生した場合、空の辞書を返しエラーにならないことをテスト"""
    # 標準エラー出力を確認するためのパッチ
    with patch("sys.stderr.write") as mock_stderr:
        translations = _load_translations("en")
        assert translations == {}
        # エラーメッセージが標準エラーに出力されているはず
        assert any("Error loading translations" in call[0][0] for call in mock_stderr.call_args_list if call[0])

def test_t_normal_translation():
    """正常系のキー解決と翻訳結果の取得をテスト"""
    set_language("ja")
    # ja.json に存在するキーを指定
    assert t("main.prompt_copied") == "✅ プロンプトをクリップボードにコピーしました！"

def test_t_with_arguments():
    """プレースホルダーへの引数埋め込みとフォーマットをテスト"""
    set_language("ja")
    # "learn.analyzing": "直近 {0} 件のコミットを分析中..."
    result = t("learn.analyzing", 15)
    assert result == "直近 15 件のコミットを分析中..."

def test_t_format_index_error():
    """フォーマットのプレースホルダー数より少ない引数を渡した場合、フォーマットせず元の文字列を返すことをテスト"""
    set_language("ja")
    # 引数が足りない場合
    result = t("learn.analyzing") # 本来1つ必要
    # エラーで落ちずに、フォーマット前の文言が返るはず
    assert "直近 {0} 件" in result

def test_t_fallback_to_english():
    """現在設定されている言語（例: ja）にキーが存在しない場合、英語（en）のキーにフォールバックすることをテスト"""
    # モックの翻訳データを作成
    mock_ja = {"main": {}} # ja にはキー自体が存在しない
    mock_en = {"main": {"only_in_english": "English message"}}

    def mock_load(lang):
        if lang == "ja":
            return mock_ja
        return mock_en

    with patch("komitto.i18n._load_translations", side_effect=mock_load):
        set_language("ja")
        # ja にないキーを指定すると、en.json から取得される
        assert t("main.only_in_english") == "English message"

def test_t_key_not_found_returns_key():
    """英語ファイルにも指定されたキーが存在しない場合、キー文字列そのものが返されることをテスト"""
    # 完全に存在しないキー
    assert t("non_existent_category.non_existent_key") == "non_existent_category.non_existent_key"

def test_t_value_not_a_string():
    """キーがオブジェクト（辞書など）を指しており、最終値が文字列ではない場合にキーそのものを返すことをテスト"""
    # "main" は辞書であるため、t("main") はキー自身を返すはず
    assert t("main") == "main"


# ==============================================================================
# 言語リソース (ja.json と en.json) の整合性自動検証テスト
# ==============================================================================

def get_all_paths(d, current_path=""):
    """辞書内のすべての葉ノードの階層パス（ドット区切り）と値を再帰的に取得する"""
    paths = {}
    for k, v in d.items():
        new_path = f"{current_path}.{k}" if current_path else k
        if isinstance(v, dict):
            paths.update(get_all_paths(v, new_path))
        else:
            paths[new_path] = v
    return paths

def test_i18n_resources_keys_and_placeholders_match():
    """ja.json と en.json で翻訳キーの過不足がなく、プレースホルダー形式が一致していることをテスト"""
    locales_dir = Path(__file__).parent.parent / "src" / "komitto" / "locales"
    
    with open(locales_dir / "en.json", "r", encoding="utf-8") as f:
        en_data = json.load(f)
    with open(locales_dir / "ja.json", "r", encoding="utf-8") as f:
        ja_data = json.load(f)
        
    en_paths = get_all_paths(en_data)
    ja_paths = get_all_paths(ja_data)
    
    # 1. キーの過不足チェック
    en_keys = set(en_paths.keys())
    ja_keys = set(ja_paths.keys())
    
    missing_in_ja = en_keys - ja_keys
    missing_in_en = ja_keys - en_keys
    
    assert not missing_in_ja, f"ja.json に以下のキーが不足しています: {missing_in_ja}"
    assert not missing_in_en, f"en.json に以下のキーが不足しています: {missing_in_en}"
    
    # 2. プレースホルダーの整合性チェック
    # 例: {0}, {1} などのプレースホルダーが ja と en の両方で一致しているか
    import re
    placeholder_pattern = re.compile(r"\{(\d+)\}")
    
    for key in en_keys:
        en_val = en_paths[key]
        ja_val = ja_paths[key]
        
        if isinstance(en_val, str) and isinstance(ja_val, str):
            en_placeholders = set(placeholder_pattern.findall(en_val))
            ja_placeholders = set(placeholder_pattern.findall(ja_val))
            
            assert en_placeholders == ja_placeholders, (
                f"キー '{key}' でプレースホルダーが一致しません。\n"
                f"en: {en_val} (placeholders: {en_placeholders})\n"
                f"ja: {ja_val} (placeholders: {ja_placeholders})"
            )
