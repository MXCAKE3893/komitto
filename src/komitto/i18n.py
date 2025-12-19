import json
import locale
import os
import sys
from pathlib import Path
from functools import lru_cache

LangCode = str

_CURRENT_LANG: LangCode = None

@lru_cache(maxsize=None)
def _load_translations(lang: str) -> dict:
    """翻訳ファイルを読み込む（キャッシュ付き）"""
    base_dir = Path(__file__).parent / "locales"
    
    lang_file = base_dir / f"{lang}.json"
    if not lang_file.exists():
        lang = "en"
        lang_file = base_dir / "en.json"
    
    try:
        with open(lang_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading translations for {lang}: {e}", file=sys.stderr)
        return {}

def detect_language() -> str:
    """環境から最適な言語を検出する"""
    # 1. 環境変数 KOMITTO_LANG を最優先
    env_lang = os.environ.get("KOMITTO_LANG")
    if env_lang:
        return env_lang

    # 2. OSのロケール設定
    try:
        # getdefaultlocale is deprecated. Use getlocale instead.
        loc = locale.getlocale()
        if loc and loc[0]:
            lang = loc[0].split('_')[0] # 'ja_JP' -> 'ja'
            return lang
    except:
        pass

    return "en"

def set_language(lang: str):
    """言語を手動設定する"""
    global _CURRENT_LANG
    _CURRENT_LANG = lang

def get_current_language() -> str:
    """現在の設定言語を返す"""
    global _CURRENT_LANG
    if _CURRENT_LANG is None:
        _CURRENT_LANG = detect_language()
    return _CURRENT_LANG

def t(key: str, *args) -> str:
    """
    指定されたキーに対応する翻訳テキストを取得し、フォーマットする。
    キーは 'category.name' の形式（例: 'main.generating'）
    """
    lang = get_current_language()
    translations = _load_translations(lang)
    
    # ドット区切りのキーを探索
    keys = key.split('.')
    value = translations
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            if lang != "en":
                 en_trans = _load_translations("en")
                 value = en_trans
                 for k_en in keys:
                     if isinstance(value, dict) and k_en in value:
                         value = value[k_en]
                     else:
                         return key
                 break
            else:
                return key

    if not isinstance(value, str):
        return key

    # 文字列フォーマット
    if args:
        try:
            return value.format(*args)
        except IndexError:
            return value
    
    return value
