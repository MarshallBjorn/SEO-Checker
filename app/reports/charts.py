import io
import math

import matplotlib

matplotlib.use("Agg")  # MUSI być przed importem pyplot

import matplotlib.pyplot as plt  # noqa: E402

_BLUE = "#2563eb"
_RED = "#ef4444"


def _fig_to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def render_radar_chart(category_scores: dict[str, int]) -> bytes:
    """Radar chart PNG — score per kategoria."""
    labels = list(category_scores.keys())
    values = [category_scores[k] for k in labels]
    n = len(labels)

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw={"polar": True})
    if n == 0:
        ax.set_title("Brak danych")
        return _fig_to_png(fig)

    angles = [2 * math.pi * i / n for i in range(n)]
    ax.plot(angles + angles[:1], values + values[:1], color=_BLUE, linewidth=2)
    ax.fill(angles + angles[:1], values + values[:1], color=_BLUE, alpha=0.25)
    ax.set_xticks(angles)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 100)
    ax.set_title("Score per kategoria")
    return _fig_to_png(fig)


def render_issue_bar_chart(issues_per_category: dict[str, int]) -> bytes:
    """Bar chart PNG — liczba problemów per kategoria."""
    labels = list(issues_per_category.keys())
    values = [issues_per_category[k] for k in labels]

    fig, ax = plt.subplots(figsize=(8, 5))
    if labels:
        ax.bar(labels, values, color=_RED)
        ax.set_ylabel("Liczba problemów")
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
            tick.set_horizontalalignment("right")
    ax.set_title("Problemy per kategoria")
    return _fig_to_png(fig)
