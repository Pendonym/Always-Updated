import os
import sys
import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

MODRINTH_PROJECT_ID = "rj6ioflZ"
MODRINTH_TOKEN = os.environ.get("MODRINTH_TOKEN")
DISALLOWED_VERSIONS = [
    "2point0_red",
    "2point0_purple",
    "2point0_blue",
    "15w14a",
    "1.RV-Pre1",
    "3D Shareware v1.34",
    "20w14infinite",
    "22w13oneBlockAtATime",
    "23w13a_or_b",
    "24w14potato",
    "25w14craftmine",
    "26w14a",
    "26.3-snapshot-2", # released way before the modpack was up
    "26.3-snapshot-4", # was debating if i should upload it or not since the modpack was under review

]

HEADERS = {"User-Agent": "modrinth.com/modpack/Always-Updated"}
if MODRINTH_TOKEN:
    HEADERS["Authorization"] = MODRINTH_TOKEN
else:
    print("Warning: MODRINTH_TOKEN not set in .env -- only public data will be visible.")


def get_modrinth_versions():
    """
    Returns a dict mapping mc_version -> earliest Modrinth publish datetime.
    A single modpack version can target multiple game versions, so each
    game_version gets the same publish time.
    """
    versions = []
    offset = 0
    while True:
        resp = requests.get(
            f"https://api.modrinth.com/v2/project/{MODRINTH_PROJECT_ID}/version",
            params={"limit": 100, "offset": offset},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        versions.extend(data)
        if len(data) < 100:
            break
        offset += 100

    earliest: dict = {}
    for v in versions:
        pub = datetime.fromisoformat(v["date_published"].replace("Z", "+00:00"))
        for gv in v.get("game_versions", []):
            if gv not in earliest or pub < earliest[gv]:
                earliest[gv] = pub
    return earliest


def get_mojang_manifest():
    resp = requests.get(
        "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json",
        timeout=15,
    )
    resp.raise_for_status()
    return {v["id"]: v for v in resp.json()["versions"]}


def get_mc_release_time(version_info):
    resp = requests.get(version_info["url"], timeout=15)
    resp.raise_for_status()
    time_str = resp.json()["time"]
    return datetime.fromisoformat(time_str.replace("Z", "+00:00"))

def main():
    print("Fetching Modrinth versions...")
    earliest_times = get_modrinth_versions()
    print(f"  Found {len(earliest_times)} MC versions on Modrinth.")
 
    print("Fetching Mojang version manifest...")
    mc_versions = get_mojang_manifest()
 
    data_points = []
    for mc_version in sorted(earliest_times):
        if mc_version in DISALLOWED_VERSIONS:
            print(f"  Skipping '{mc_version}': in disallow list.")
            continue
 
        if mc_version not in mc_versions:
            print(f"  Skipping '{mc_version}': not found in Mojang manifest.")
            continue
 
        mc_time = get_mc_release_time(mc_versions[mc_version])
        modpack_time = earliest_times[mc_version]
        delta_hours = (modpack_time - mc_time).total_seconds() / 3600
 
        if delta_hours < 0:
            print(f"  Skipping '{mc_version}': negative delta ({delta_hours:.1f}h).")
            continue
 
        data_points.append({"label": mc_version, "hours": round(delta_hours, 1)})
        print(f"  {mc_version}: {delta_hours:.1f}h")
 
    if not data_points:
        print("No valid data points found. Exiting without generating graph.")
        sys.exit(0)
 
    labels = [d["label"] for d in data_points]
    hours = [d["hours"] for d in data_points]
    avg = sum(hours) / len(hours)
    max_h = max(hours)
 
    # Green reads reasonably well on both light and dark backgrounds.
    TEXT_COLOR = "#2ECC71"
 
    fig_width = max(14, len(labels) * 1.1)
    fig, ax = plt.subplots(figsize=(fig_width, 6))
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)
 
    x = list(range(len(labels)))
    bars = ax.bar(x, hours, color="#FFD700", edgecolor="#B8860B", linewidth=0.8, width=0.6)
 
    for bar, h in zip(bars, hours):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_h * 0.012,
            f"{h}h",
            ha="center", va="bottom", fontsize=9, fontweight="bold", color=TEXT_COLOR,
        )
 
    ax.axhline(y=avg, color=TEXT_COLOR, linestyle="--", linewidth=1.5)
    ax.text(
        len(labels) - 0.5,
        avg + max_h * 0.02,
        f"All-Time Avg: {avg:.1f}h",
        color=TEXT_COLOR, fontsize=10, fontweight="bold", ha="right",
        bbox=dict(facecolor="none", edgecolor=TEXT_COLOR, boxstyle="round,pad=0.3"),
    )
 
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9, color=TEXT_COLOR)
    ax.tick_params(axis="y", colors=TEXT_COLOR)
    ax.set_ylabel("Hours to Update", fontsize=12, fontweight="bold", color=TEXT_COLOR)
    ax.set_ylim(0, max_h * 1.22)
    ax.set_title(
        f"Always Updated: Update Speed (All-Time Avg: {avg:.1f}h)",
        fontsize=14, fontweight="bold", color=TEXT_COLOR,
    )
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(TEXT_COLOR)
    ax.spines["bottom"].set_color(TEXT_COLOR)
 
    plt.tight_layout()
    plt.savefig("update_graph.png", dpi=150, bbox_inches="tight", transparent=True)
    print(f"Graph saved: update_graph.png ({len(data_points)} entries, avg {avg:.1f}h)")
 
 
if __name__ == "__main__":
    main()
