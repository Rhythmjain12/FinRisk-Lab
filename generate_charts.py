"""One-off helper: run the FinRisk-Lab pipeline and export each chart to PNG.

Monkey-patches plotly's Figure.show() so it writes a static PNG to
outputs/charts/ instead of opening a browser tab. After running, the charts
can be referenced from the README.
"""

from pathlib import Path
import plotly.graph_objects as go

chart_dir = Path("outputs/charts")
chart_dir.mkdir(parents=True, exist_ok=True)

# Stable, descriptive filenames in call order (matches src/main.py)
NAMES = [
    "01_normalized_prices",
    "02_drawdowns_comparison",
    "03_correlation_heatmap",
    "04_risk_contribution",
    "05_stress_test",
    "06_asset_risk_return",
    "07_max_drawdown_comparison",
    "08_diversification_benefit",
]
counter = {"i": 0}


def show_and_save(self, *args, **kwargs):
    name = NAMES[counter["i"]] if counter["i"] < len(NAMES) else f"extra_{counter['i']:02d}"
    out = chart_dir / f"{name}.png"
    self.write_image(str(out), width=1400, height=800, scale=2)
    print(f"  saved {out}")
    counter["i"] += 1


go.Figure.show = show_and_save

from src.main import main  # noqa: E402

main()
print(f"\nDone. {counter['i']} charts written to {chart_dir.resolve()}")
