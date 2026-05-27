import pytest
from unittest.mock import patch
from komitto.cost import calculate_cost, format_cost

def test_calculate_cost_normal():
    """正常な価格設定のもとで、トークンから正しくコストが計算されることをテスト"""
    llm_config = {
        "input_cost_per_million": 2.50,
        "output_cost_per_million": 10.00
    }
    # 2,000,000 input tokens = $5.00
    # 500,000 output tokens = $5.00
    # Total = $10.00
    result = calculate_cost(llm_config, 2_000_000, 500_000)
    assert result == {
        "input_cost": 5.00,
        "output_cost": 5.00,
        "total_cost": 10.00,
        "currency": "USD"
    }

def test_calculate_cost_empty_config():
    """設定が None または空の場合、None を返すことをテスト"""
    assert calculate_cost(None, 100, 100) is None
    assert calculate_cost({}, 100, 100) is None

@pytest.mark.parametrize("config", [
    {"input_cost_per_million": 2.50},  # output_cost_per_million が欠損
    {"output_cost_per_million": 10.00}, # input_cost_per_million が欠損
    {"input_cost_per_million": None, "output_cost_per_million": 10.00}, # 片方が None
])
def test_calculate_cost_incomplete_config(config):
    """設定情報が不完全な場合、None を返すことをテスト"""
    assert calculate_cost(config, 100, 100) is None

def test_calculate_cost_zero_tokens():
    """トークン数が 0 の場合にコストが 0.0 になることをテスト"""
    llm_config = {
        "input_cost_per_million": 2.0,
        "output_cost_per_million": 4.0
    }
    result = calculate_cost(llm_config, 0, 0)
    assert result == {
        "input_cost": 0.0,
        "output_cost": 0.0,
        "total_cost": 0.0,
        "currency": "USD"
    }

def test_calculate_cost_negative_tokens():
    """負のトークン数が渡された場合でも計算自体は行われる（または想定内の挙動になる）ことをテスト"""
    llm_config = {
        "input_cost_per_million": 10.0,
        "output_cost_per_million": 10.0
    }
    result = calculate_cost(llm_config, -100_000, -200_000)
    assert result["total_cost"] == -3.0

@patch("komitto.cost.t")
def test_format_cost_none(mock_t):
    """コストデータが None の場合、コスト不明用の翻訳キーが呼び出されることをテスト"""
    mock_t.return_value = "💰 コスト: 不明"
    assert format_cost(None) == "💰 コスト: 不明"
    mock_t.assert_called_once_with("tui.cost_unknown")

@patch("komitto.cost.t")
def test_format_cost_normal_value(mock_t):
    """コストが $0.01 以上の通常金額の場合、通常表示用のフォーマット関数が呼ばれることをテスト"""
    cost_data = {
        "total_cost": 0.015,
        "currency": "USD"
    }
    mock_t.return_value = "💰 コスト: $0.0150"
    result = format_cost(cost_data)
    assert result == "💰 コスト: $0.0150"
    mock_t.assert_called_once_with("tui.cost_normal", "0.0150")

@patch("komitto.cost.t")
def test_format_cost_small_value(mock_t):
    """コストが $0.01 未満の微小金額の場合、マイクロ表示用のフォーマット関数が呼ばれることをテスト"""
    # $0.000123 = 123 uUSD
    cost_data = {
        "total_cost": 0.000123,
        "currency": "USD"
    }
    mock_t.return_value = "💰 コスト: $0.000123 (~123.00μ$)"
    result = format_cost(cost_data)
    assert result == "💰 コスト: $0.000123 (~123.00μ$)"
    mock_t.assert_called_once_with("tui.cost_small", "0.000123", "123.00")
