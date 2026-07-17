from typing import Optional
from komitto.i18n import t


def calculate_cost(llm_config: dict, prompt_tokens: int, completion_tokens: int) -> Optional[dict]:
    """
    トークン使用量からコストを計算する
    
    Args:
        llm_config: LLM設定（komitto.jsonのllmセクション）
        prompt_tokens: 入力トークン数
        completion_tokens: 出力トークン数
    
    Returns:
        {
            "input_cost": float,      # 入力コスト (USD)
            "output_cost": float,     # 出力コスト (USD)
            "total_cost": float,      # 合計コスト (USD)
            "currency": "USD"
        }
        料金情報がない場合はNoneを返す
    """
    if not llm_config:
        return None
    
    input_price = llm_config.get("input_cost_per_million")
    output_price = llm_config.get("output_cost_per_million")
    
    if input_price is None or output_price is None:
        return None
    
    input_cost = (prompt_tokens / 1_000_000) * input_price
    output_cost = (completion_tokens / 1_000_000) * output_price
    total_cost = input_cost + output_cost
    
    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
        "currency": "USD"
    }


def format_cost(cost_data: Optional[dict]) -> str:
    if not cost_data:
        return t("tui.cost_unknown")
    
    total = cost_data["total_cost"]
    
    if total < 0.01:
        micro_usd = total * 1_000_000
        return t("tui.cost_small", f"{total:.6f}", f"{micro_usd:.2f}")
    else:
        return t("tui.cost_normal", f"{total:.4f}")
