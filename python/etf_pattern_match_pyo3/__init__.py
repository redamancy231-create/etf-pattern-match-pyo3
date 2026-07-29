# etf_pattern_match_pyo3 — Rust/PyO3 ETF 形态匹配计算核心

from etf_pattern_match_pyo3._core import (
    FEATURE_KEYS,
    cosine_similarity,
    dtw_distance,
    pattern_match_batch,
    pattern_match_single,
    standardize_returns,
)

__all__ = [
    "standardize_returns",
    "cosine_similarity",
    "dtw_distance",
    "pattern_match_single",
    "pattern_match_batch",
    "FEATURE_KEYS",
]

# 可选：Panel 适配器。模块不顶层导入 torch/mlquant，核心导入不受可选依赖影响。
try:
    from etf_pattern_match_pyo3.panel_adapter import (
        panel_to_prices as panel_to_prices,
        pattern_match_batch_panel as pattern_match_batch_panel,
        pattern_match_single_panel as pattern_match_single_panel,
    )
except ImportError:
    _has_panel = False
else:
    _has_panel = True
    __all__.extend(
        [
            "panel_to_prices",
            "pattern_match_single_panel",
            "pattern_match_batch_panel",
        ]
    )

# 可选：GPU 加速。gpu_adapter 不顶层导入 CuPy，核心导入不受可选依赖影响。
# 注意：不在此处调用 has_gpu()——避免触发 CuPy 环境探测和 GPU 初始化。
# 用户主动调用 has_gpu() 时才检测。
try:
    from etf_pattern_match_pyo3.gpu_adapter import (
        cosine_prefilter_gpu as cosine_prefilter_gpu,
        cosine_similarity_batch_gpu as cosine_similarity_batch_gpu,
        has_gpu as has_gpu,
    )
except ImportError:
    _has_gpu_extra = False
else:
    _has_gpu_extra = True
    __all__.extend(
        [
            "has_gpu",
            "cosine_similarity_batch_gpu",
            "cosine_prefilter_gpu",
        ]
    )