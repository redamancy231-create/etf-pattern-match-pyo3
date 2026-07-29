"""Panel 适配器测试：使用合成 tensor，避免测试硬依赖 ml-quant。"""

import numpy as np
import pytest


class FakeTensor:
    """实现 Panel 适配器所需的最小 torch.Tensor 协议。"""

    def __init__(self, values):
        self._values = np.asarray(values)

    def __getitem__(self, item):
        return FakeTensor(self._values[item])

    def detach(self):
        return self

    def cpu(self):
        return self

    def numpy(self):
        return self._values


class MockPanel:
    """合成 Panel，模拟 ml-quant 的数据结构。"""

    def __init__(self, n_dates=100, n_stocks=3):
        rng = np.random.default_rng(42)
        self.dates = np.array([f"2024-{i:03d}" for i in range(1, n_dates + 1)])
        self.stocks = [f"stock_{i:03d}" for i in range(n_stocks)]
        self.fields = {
            "close": FakeTensor(
                100.0
                * np.cumprod(
                    1.0 + rng.normal(0.0, 0.02, size=(n_dates, n_stocks)),
                    axis=0,
                )
            )
        }
        self.mask = FakeTensor(np.ones((n_dates, n_stocks), dtype=bool))


def test_panel_to_prices_by_index():
    from etf_pattern_match_pyo3.panel_adapter import panel_to_prices

    prices, mask, symbol = panel_to_prices(MockPanel(), asset_col=0)
    assert prices.shape == (100,)
    assert prices.dtype == np.float64
    assert prices.flags.c_contiguous
    assert mask.dtype == bool
    assert mask.all()
    assert symbol == "stock_000"


def test_panel_to_prices_by_name_and_negative_index():
    from etf_pattern_match_pyo3.panel_adapter import panel_to_prices

    panel = MockPanel()
    _, _, by_name = panel_to_prices(panel, asset_col="stock_001")
    _, _, by_negative_index = panel_to_prices(panel, asset_col=-1)
    assert by_name == "stock_001"
    assert by_negative_index == "stock_002"


def test_pattern_match_single_panel_rejects_masked_query(monkeypatch):
    import etf_pattern_match_pyo3 as package
    from etf_pattern_match_pyo3.panel_adapter import pattern_match_single_panel

    panel = MockPanel()
    panel.mask._values[25, 0] = False

    def should_not_run(*args, **kwargs):
        pytest.fail("masked query must not reach the Rust core")

    monkeypatch.setattr(package, "pattern_match_single", should_not_run)
    assert pattern_match_single_panel(panel, t_idx=25) is None


def test_pattern_match_single_panel_preserves_axis_and_marks_nan(monkeypatch):
    import etf_pattern_match_pyo3 as package
    from etf_pattern_match_pyo3.panel_adapter import pattern_match_single_panel

    panel = MockPanel()
    panel.mask._values[10, 0] = False
    captured = {}

    def fake_match(prices, t_idx, **kwargs):
        captured["prices"] = prices
        captured["t_idx"] = t_idx
        captured["kwargs"] = kwargs
        return {"ok": 1.0}

    monkeypatch.setattr(package, "pattern_match_single", fake_match)
    result = pattern_match_single_panel(panel, t_idx=50, k=3)
    assert result == {"ok": 1.0}
    assert captured["prices"].shape == (100,)
    assert np.isnan(captured["prices"][10])
    assert captured["t_idx"] == 50
    assert captured["kwargs"] == {"k": 3}


def test_pattern_match_batch_panel_normalizes_indices(monkeypatch):
    import etf_pattern_match_pyo3 as package
    from etf_pattern_match_pyo3.panel_adapter import pattern_match_batch_panel

    panel = MockPanel()
    panel.mask._values[10, 1] = False
    captured = {}

    def fake_batch(prices, t_indices, **kwargs):
        captured["prices"] = prices
        captured["t_indices"] = t_indices
        return "batch-result"

    monkeypatch.setattr(package, "pattern_match_batch", fake_batch)
    result = pattern_match_batch_panel(
        panel,
        t_indices=[30, 40],
        asset_col="stock_001",
    )
    assert result == "batch-result"
    assert np.isnan(captured["prices"][10])
    assert captured["t_indices"].dtype == np.int64
    assert captured["t_indices"].flags.c_contiguous


def test_pattern_match_single_panel_retries_when_core_rejects_nan(monkeypatch):
    import etf_pattern_match_pyo3 as package
    from etf_pattern_match_pyo3.panel_adapter import pattern_match_single_panel

    panel = MockPanel()
    panel.mask._values[10, 0] = False
    calls = []

    def fake_match(prices, t_idx, **kwargs):
        calls.append(prices.copy())
        if np.isnan(prices).any():
            raise ValueError("non-finite value at index 10")
        return {"ok": 1.0}

    monkeypatch.setattr(package, "pattern_match_single", fake_match)
    result = pattern_match_single_panel(panel, t_idx=50)
    assert result == {"ok": 1.0}
    assert len(calls) == 2
    assert np.isnan(calls[0][10])
    assert np.isfinite(calls[1]).all()


def test_pattern_match_single_panel_core_integration():
    from etf_pattern_match_pyo3.panel_adapter import pattern_match_single_panel

    result = pattern_match_single_panel(MockPanel(n_dates=800), t_idx=500)
    if result is not None:
        assert len(result) == 15


def test_panel_to_prices_supports_direct_close_and_numpy_stocks():
    from etf_pattern_match_pyo3.panel_adapter import panel_to_prices

    panel = MockPanel(n_dates=8, n_stocks=2)
    panel.close = panel.fields.pop("close")
    panel.stocks = np.asarray(panel.stocks)

    prices, mask, symbol = panel_to_prices(panel, asset_col="stock_001")
    assert prices.shape == (8,)
    assert mask.all()
    assert symbol == "stock_001"


def test_panel_to_prices_supports_real_torch_when_installed():
    torch = pytest.importorskip("torch")
    from etf_pattern_match_pyo3.panel_adapter import panel_to_prices

    panel = MockPanel(n_dates=8, n_stocks=2)
    panel.fields["close"] = torch.as_tensor(
        panel.fields["close"]._values,
        dtype=torch.float64,
    )
    panel.mask = torch.ones((8, 2), dtype=torch.bool)
    prices, mask, symbol = panel_to_prices(panel, asset_col=1)
    assert prices.shape == (8,)
    assert mask.all()
    assert symbol == "stock_001"
