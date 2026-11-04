"""Figure style for the paper's data figures."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

INK = "0.10"

RC = {
    "font.family": "serif",
    "font.serif": ["Times New Roman", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 9, "axes.labelsize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.linewidth": 0.6, "axes.edgecolor": "0.35",
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.color": "0.35", "ytick.color": "0.35",
    "xtick.direction": "out", "ytick.direction": "out",
    "axes.grid": True, "axes.grid.axis": "y",
    "grid.color": "0.90", "grid.linewidth": 0.5,
    "axes.axisbelow": True, "figure.dpi": 200, "savefig.dpi": 200,
    "pdf.fonttype": 42,
}


def apply():
    plt.rcParams.update(RC)


def tag(ax, text):
    """Panel tag '(a) ...' inside the axes, house position."""
    ax.annotate(text, xy=(0.03, 1.01), xycoords="axes fraction", fontsize=9,
                va="bottom", color=INK)


def save(fig, path):
    fig.savefig(path, bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
