"""
NetProbe Grafik Üretici

results/ klasöründeki CSV dosyalarından deney grafiklerini üretir.
Her deney senaryosu için ayrı PNG dosyası oluşturur.

Kullanım:
    python analysis/plot.py                     # Tüm grafikleri üret
    python analysis/plot.py --scenario 1        # Sadece senaryo 1
    python analysis/plot.py --results-dir DIR   # Farklı sonuç klasörü
"""

import argparse
import csv
import json
import os
import glob
import sys

try:
    import matplotlib
    matplotlib.use("Agg")   # GUI gerektirmez
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Uyarı: matplotlib kurulu değil. 'pip install matplotlib' ile kurun.")


OUTPUT_DIR = "results"


def _load_scenario_csv(csv_path: str) -> list[dict]:
    with open(csv_path, newline="") as f:
        return list(csv.DictReader(f))


def _savefig(fig, name: str):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[PLOT] Kaydedildi: {path}")


# ---------------------------------------------------------------------------
# Senaryo 1: Paket boyutunun etkisi
# ---------------------------------------------------------------------------

def plot_scenario1(data: list[dict]):
    """
    X: chunk_size (byte)
    Y1: throughput (KB/s)
    Y2: completion_time (s)
    """
    if not data:
        print("[PLOT] Senaryo 1 verisi bulunamadı")
        return

    chunk_sizes = [int(r["chunk_size"]) for r in data]
    throughputs = [float(r["throughput_kbps"]) for r in data]
    comp_times  = [float(r["elapsed_s"]) for r in data]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Senaryo 1: Paket Boyutunun Etkisi", fontsize=14, fontweight="bold")

    ax1.plot(chunk_sizes, throughputs, "b-o", linewidth=2, markersize=8)
    ax1.set_xlabel("Paket Boyutu (byte)")
    ax1.set_ylabel("Throughput (KB/s)")
    ax1.set_title("Throughput vs Paket Boyutu")
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x)}B"))

    ax2.plot(chunk_sizes, comp_times, "r-s", linewidth=2, markersize=8)
    ax2.set_xlabel("Paket Boyutu (byte)")
    ax2.set_ylabel("Tamamlanma Süresi (s)")
    ax2.set_title("Tamamlanma Süresi vs Paket Boyutu")
    ax2.grid(True, alpha=0.3)

    _savefig(fig, "scenario1_packet_size.png")


# ---------------------------------------------------------------------------
# Senaryo 2: Timeout değerinin etkisi
# ---------------------------------------------------------------------------

def plot_scenario2(data: list[dict]):
    """
    X: timeout (s)
    Y1: retransmission_rate
    Y2: completion_time (s)
    """
    if not data:
        print("[PLOT] Senaryo 2 verisi bulunamadı")
        return

    timeouts    = [float(r["timeout_s"]) for r in data]
    retx_rates  = [float(r["retx_rate"]) * 100 for r in data]
    comp_times  = [float(r["elapsed_s"]) for r in data]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Senaryo 2: Timeout Değerinin Etkisi", fontsize=14, fontweight="bold")

    ax1.plot(timeouts, retx_rates, "g-^", linewidth=2, markersize=8)
    ax1.set_xlabel("Timeout (s)")
    ax1.set_ylabel("Retransmission Oranı (%)")
    ax1.set_title("Retransmission Oranı vs Timeout")
    ax1.grid(True, alpha=0.3)

    ax2.plot(timeouts, comp_times, "m-D", linewidth=2, markersize=8)
    ax2.set_xlabel("Timeout (s)")
    ax2.set_ylabel("Tamamlanma Süresi (s)")
    ax2.set_title("Tamamlanma Süresi vs Timeout")
    ax2.grid(True, alpha=0.3)

    _savefig(fig, "scenario2_timeout.png")


# ---------------------------------------------------------------------------
# Senaryo 3: Kayıp oranının etkisi
# ---------------------------------------------------------------------------

def plot_scenario3(data: list[dict]):
    """
    X: loss_rate (%)
    Y1: throughput (KB/s) ve goodput (KB/s)
    Y2: retransmission_count
    """
    if not data:
        print("[PLOT] Senaryo 3 verisi bulunamadı")
        return

    loss_rates  = [float(r["loss_rate"]) * 100 for r in data]
    throughputs = [float(r["throughput_kbps"]) for r in data]
    goodputs    = [float(r["goodput_kbps"]) for r in data]
    retx_counts = [int(r["retransmissions"]) for r in data]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Senaryo 3: Kayıp Oranının Etkisi", fontsize=14, fontweight="bold")

    ax1.plot(loss_rates, throughputs, "b-o", linewidth=2, markersize=8, label="Throughput")
    ax1.plot(loss_rates, goodputs,    "r-s", linewidth=2, markersize=8, label="Goodput")
    ax1.set_xlabel("Kayıp Oranı (%)")
    ax1.set_ylabel("Hız (KB/s)")
    ax1.set_title("Throughput & Goodput vs Kayıp Oranı")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.bar([str(lr) + "%" for lr in loss_rates], retx_counts, color="orange", alpha=0.8)
    ax2.set_xlabel("Kayıp Oranı (%)")
    ax2.set_ylabel("Retransmission Sayısı")
    ax2.set_title("Retransmission Sayısı vs Kayıp Oranı")
    ax2.grid(True, alpha=0.3, axis="y")

    _savefig(fig, "scenario3_loss_rate.png")


# ---------------------------------------------------------------------------
# Senaryo 4: Dosya boyutunun etkisi
# ---------------------------------------------------------------------------

def plot_scenario4(data: list[dict]):
    """
    X: file_size (KB)
    Y1: throughput (KB/s)
    Y2: completion_time (s)
    """
    if not data:
        print("[PLOT] Senaryo 4 verisi bulunamadı")
        return

    file_sizes  = [int(r["file_size_bytes"]) / 1024 for r in data]
    throughputs = [float(r["throughput_kbps"]) for r in data]
    comp_times  = [float(r["elapsed_s"]) for r in data]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Senaryo 4: Dosya Boyutunun Etkisi", fontsize=14, fontweight="bold")

    ax1.plot(file_sizes, throughputs, "c-o", linewidth=2, markersize=8)
    ax1.set_xlabel("Dosya Boyutu (KB)")
    ax1.set_ylabel("Throughput (KB/s)")
    ax1.set_title("Throughput vs Dosya Boyutu")
    ax1.grid(True, alpha=0.3)

    ax2.plot(file_sizes, comp_times, "y-s", linewidth=2, markersize=8, color="darkorange")
    ax2.set_xlabel("Dosya Boyutu (KB)")
    ax2.set_ylabel("Tamamlanma Süresi (s)")
    ax2.set_title("Tamamlanma Süresi vs Dosya Boyutu")
    ax2.grid(True, alpha=0.3)

    _savefig(fig, "scenario4_file_size.png")


# ---------------------------------------------------------------------------
# Genel özet grafiği
# ---------------------------------------------------------------------------

def plot_summary_from_json(json_files: list[str]):
    """Log klasöründeki JSON özetlerinden genel özet çizer."""
    if not json_files:
        print("[PLOT] Özet JSON dosyası bulunamadı")
        return

    labels, throughputs, goodputs, retx_rates = [], [], [], []
    for path in json_files[:8]:   # en fazla 8 oturum
        with open(path) as f:
            d = json.load(f)
        labels.append(d["session_id"][-6:])
        throughputs.append(d.get("throughput_bps", 0) / 1024)
        goodputs.append(d.get("goodput_bps", 0) / 1024)
        retx_rates.append(d.get("retx_rate", 0) * 100)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Oturum Özeti", fontsize=14, fontweight="bold")

    x = range(len(labels))
    width = 0.35
    ax1.bar([i - width/2 for i in x], throughputs, width, label="Throughput", color="steelblue")
    ax1.bar([i + width/2 for i in x], goodputs,    width, label="Goodput",    color="seagreen")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels, rotation=45, ha="right")
    ax1.set_ylabel("Hız (KB/s)")
    ax1.set_title("Throughput & Goodput Karşılaştırması")
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis="y")

    ax2.bar(list(x), retx_rates, color="tomato", alpha=0.8)
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(labels, rotation=45, ha="right")
    ax2.set_ylabel("Retransmission Oranı (%)")
    ax2.set_title("Retransmission Oranı Karşılaştırması")
    ax2.grid(True, alpha=0.3, axis="y")

    _savefig(fig, "summary_overview.png")


def main():
    if not HAS_MATPLOTLIB:
        sys.exit(1)

    parser = argparse.ArgumentParser(description="NetProbe Grafik Üretici")
    parser.add_argument("--scenario",    type=int, choices=[1, 2, 3, 4],
                        help="Sadece belirtilen senaryonun grafiğini üret")
    parser.add_argument("--results-dir", default="results",
                        help="Senaryo CSV dosyalarının bulunduğu klasör")
    parser.add_argument("--logs-dir",    default="logs",
                        help="JSON özet dosyalarının bulunduğu klasör")
    args = parser.parse_args()

    global OUTPUT_DIR
    OUTPUT_DIR = args.results_dir
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    scenario_loaders = {
        1: ("scenario1_*.csv", plot_scenario1),
        2: ("scenario2_*.csv", plot_scenario2),
        3: ("scenario3_*.csv", plot_scenario3),
        4: ("scenario4_*.csv", plot_scenario4),
    }

    if args.scenario:
        pattern, func = scenario_loaders[args.scenario]
        files = glob.glob(os.path.join(args.results_dir, pattern))
        if files:
            data = _load_scenario_csv(files[0])
            func(data)
        else:
            print(f"[PLOT] {pattern} bulunamadı, genel JSON özetleri çiziliyor...")
            json_files = sorted(glob.glob(os.path.join(args.logs_dir, "summary_client_*.json")))
            plot_summary_from_json(json_files)
    else:
        # Tüm senaryoları üret
        for s_id, (pattern, func) in scenario_loaders.items():
            files = glob.glob(os.path.join(args.results_dir, pattern))
            if files:
                data = _load_scenario_csv(files[0])
                func(data)
            else:
                print(f"[PLOT] Senaryo {s_id} için CSV bulunamadı, atlandı")

        # Genel özet
        json_files = sorted(glob.glob(os.path.join(args.logs_dir, "summary_client_*.json")))
        plot_summary_from_json(json_files)


if __name__ == "__main__":
    main()
