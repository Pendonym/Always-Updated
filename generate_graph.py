import os
import sys
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

PROJECTS = {
    "Always Updated": "rj6ioflZ",
    "Wmfgn1eN": "Wmfgn1eN",
    "Gvp9bbxY": "Gvp9bbxY",
}

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
]

HEADERS = {
    "User-Agent": "modrinth.com/modpack/Always-Updated"
}

if MODRINTH_TOKEN:
    HEADERS["Authorization"] = MODRINTH_TOKEN
else:
    print(
        "Warning: MODRINTH_TOKEN not set in .env "
        "-- only public data will be visible."
    )


def get_modrinth_project_name(project_id):
    resp = requests.get(
        f"https://api.modrinth.com/v2/project/{project_id}",
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()

    return resp.json().get("title", project_id)


def get_modrinth_versions(project_id):
    """
    Returns:
        {
            "1.21.8": datetime(...),
            "1.21.7": datetime(...),
            ...
        }

    If multiple Modrinth versions target the same Minecraft version,
    the earliest publication time is used.
    """

    versions = []
    offset = 0

    while True:
        resp = requests.get(
            f"https://api.modrinth.com/v2/project/{project_id}/version",
            params={
                "limit": 100,
                "offset": offset,
            },
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

    earliest = {}

    for version in versions:
        published = datetime.fromisoformat(
            version["date_published"].replace("Z", "+00:00")
        )

        for game_version in version.get("game_versions", []):
            if (
                game_version not in earliest
                or published < earliest[game_version]
            ):
                earliest[game_version] = published

    return earliest


def get_mojang_manifest():
    resp = requests.get(
        "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json",
        timeout=15,
    )
    resp.raise_for_status()

    return {
        version["id"]: version
        for version in resp.json()["versions"]
    }


def get_mc_release_time(version_info):
    """
    Returns the official Minecraft release timestamp.
    """

    resp = requests.get(
        version_info["url"],
        timeout=15,
    )

    resp.raise_for_status()

    data = resp.json()

    release_time_str = data.get("releaseTime")
    time_str = data.get("time")

    release_dt = None
    time_dt = None

    if release_time_str:
        release_dt = datetime.fromisoformat(
            release_time_str.replace("Z", "+00:00")
        )

    if time_str:
        time_dt = datetime.fromisoformat(
            time_str.replace("Z", "+00:00")
        )

    chosen = release_dt or time_dt

    if chosen is None:
        raise ValueError(
            "Neither releaseTime nor time found"
        )

    return chosen


def main():
    print("==========================================")
    print("       MODRINTH UPDATE SPEED COMPARISON")
    print("==========================================\n")

    # ---------------------------------------------------------
    # GET PROJECT NAMES
    # ---------------------------------------------------------

    project_names = {}

    for label, project_id in PROJECTS.items():
        try:
            name = get_modrinth_project_name(project_id)

            project_names[label] = name

            print(
                f"{label}: {name} ({project_id})"
            )

        except Exception as e:
            print(
                f"Failed to get project name for "
                f"{label}: {e}"
            )

            project_names[label] = label

    # ---------------------------------------------------------
    # GET MODRINTH VERSION DATA
    # ---------------------------------------------------------

    project_times = {}

    for label, project_id in PROJECTS.items():
        print(
            f"\nFetching versions for "
            f"{project_names[label]}..."
        )

        try:
            times = get_modrinth_versions(
                project_id
            )

            project_times[label] = times

            print(
                f"  Found {len(times)} Minecraft versions."
            )

        except Exception as e:
            print(
                f"  ERROR: {e}"
            )

            project_times[label] = {}

    # ---------------------------------------------------------
    # GET MOJANG DATA
    # ---------------------------------------------------------

    print("\nFetching Mojang version manifest...")

    mc_versions = get_mojang_manifest()

    # Mojang manifest is ordered newest -> oldest.
    manifest_order = list(mc_versions.keys())

    # ---------------------------------------------------------
    # GET UNION OF ALL VERSIONS
    # ---------------------------------------------------------

    all_versions = set()

    for label in PROJECTS:
        all_versions.update(
            project_times[label].keys()
        )

    print(
        f"\nFound {len(all_versions)} total versions "
        "across all projects."
    )

    # ---------------------------------------------------------
    # FILTER TO VALID VERSIONS
    # ---------------------------------------------------------

    valid_versions = []

    for version in all_versions:

        if version in DISALLOWED_VERSIONS:
            continue

        if version not in mc_versions:
            continue

        valid_versions.append(version)

    # ---------------------------------------------------------
    # SORT BY MOJANG MANIFEST ORDER
    # NEWEST -> OLDEST
    # ---------------------------------------------------------

    valid_versions.sort(
        key=lambda version: manifest_order.index(version)
    )

    # ---------------------------------------------------------
    # ONLY SHOW THE LATEST 5
    # ---------------------------------------------------------

    selected_versions = valid_versions[:5]

    print(
        f"\nDisplaying the latest "
        f"{len(selected_versions)} valid versions:"
    )

    for version in selected_versions:
        print(f"  {version}")

    # ---------------------------------------------------------
    # BUILD DATA
    # ---------------------------------------------------------

    data_points = []

    for mc_version in selected_versions:

        try:
            mc_release_time = get_mc_release_time(
                mc_versions[mc_version]
            )

        except Exception as e:
            print(
                f"Skipping {mc_version}: "
                f"failed to get release time ({e})"
            )
            continue

        deltas = {}

        # -----------------------------------------------------
        # CALCULATE UPDATE TIME FOR EACH PROJECT
        # -----------------------------------------------------

        for label in PROJECTS:

            # Project does not have this Minecraft version.
            if mc_version not in project_times[label]:
                deltas[label] = None
                continue

            delta = (
                project_times[label][mc_version]
                - mc_release_time
            ).total_seconds() / 3600

            # Ignore impossible negative values.
            if delta < 0:
                deltas[label] = None
            else:
                deltas[label] = delta

        # -----------------------------------------------------
        # SAVE DATA POINT
        # -----------------------------------------------------

        point = {
            "label": mc_version
        }

        for label in PROJECTS:

            if deltas[label] is None:
                point[label] = None
            else:
                point[label] = round(
                    deltas[label],
                    1
                )

        data_points.append(point)

        # -----------------------------------------------------
        # CONSOLE OUTPUT
        # -----------------------------------------------------

        output = f"  {mc_version}:"

        for label in PROJECTS:

            value = deltas[label]

            if value is None:
                output += f" {label}=N/A"
            else:
                output += (
                    f" {label}={value:.1f}h"
                )

        print(output)

    if not data_points:
        print(
            "\nNo valid data points found."
        )
        sys.exit(0)

    # ---------------------------------------------------------
    # CALCULATE AVERAGES
    # ---------------------------------------------------------

    averages = {}

    for label in PROJECTS:

        values = [
            point[label]
            for point in data_points
            if point[label] is not None
        ]

        if values:
            averages[label] = (
                sum(values) / len(values)
            )
        else:
            averages[label] = None

    # ---------------------------------------------------------
    # PRINT AVERAGES
    # ---------------------------------------------------------

    print("\n==========================================")
    print("                 AVERAGES")
    print("==========================================")

    for label in PROJECTS:

        if averages[label] is None:

            print(
                f"{project_names[label]}: N/A"
            )

        else:

            count = sum(
                1
                for point in data_points
                if point[label] is not None
            )

            print(
                f"{project_names[label]}: "
                f"{averages[label]:.1f}h "
                f"({count} versions)"
            )

    # ---------------------------------------------------------
    # FIND FASTEST
    # ---------------------------------------------------------

    valid_averages = {
        label: average
        for label, average in averages.items()
        if average is not None
    }

    if valid_averages:

        fastest = min(
            valid_averages,
            key=valid_averages.get
        )

        print(
            f"\nFASTEST OVERALL: "
            f"{project_names[fastest]} "
            f"({averages[fastest]:.1f}h average)"
        )

    print("\n==========================================")

    # ---------------------------------------------------------
    # GRAPH DATA
    # ---------------------------------------------------------

    labels = [
        point["label"]
        for point in data_points
    ]

    x = list(range(len(labels)))

    project_count = len(PROJECTS)

    # Bar width automatically adjusts based on
    # number of projects.
    width = 0.75 / project_count

    fig_width = max(
        14,
        len(labels) * 2.0
    )

    fig, ax = plt.subplots(
        figsize=(fig_width, 7)
    )

    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)

    # ---------------------------------------------------------
    # COLORS
    # ---------------------------------------------------------

    colors = [
        "#FFD700",  # Always Updated - Gold
        "#4DA6FF",  # Wmfgn1eN - Blue
        "#B06CFF",  # Gvp9bbxY - Purple
    ]

    TEXT_COLOR = "#2ECC71"
    MISSING_COLOR = "#777777"

    # ---------------------------------------------------------
    # FIND MAX VALUE
    # ---------------------------------------------------------

    all_values = [
        point[label]
        for point in data_points
        for label in PROJECTS
        if point[label] is not None
    ]

    max_h = max(all_values)

    # ---------------------------------------------------------
    # DRAW BARS
    # ---------------------------------------------------------

    for index, project_label in enumerate(PROJECTS):

        offset = (
            index
            - (project_count - 1) / 2
        ) * width

        bar_positions = [
            i + offset
            for i in x
        ]

        # Only draw actual bars for versions that exist.
        existing_positions = []
        existing_values = []

        for position, point in zip(
            bar_positions,
            data_points
        ):

            value = point[project_label]

            if value is not None:
                existing_positions.append(position)
                existing_values.append(value)

        bars = ax.bar(
            existing_positions,
            existing_values,
            width=width,
            color=colors[
                index % len(colors)
            ],
            edgecolor="black",
            linewidth=0.6,
            label=project_names[
                project_label
            ],
        )

        # -----------------------------------------------------
        # VALUE LABELS
        # -----------------------------------------------------

        for bar, value in zip(
            bars,
            existing_values
        ):

            ax.text(
                bar.get_x()
                + bar.get_width() / 2,
                bar.get_height()
                + max_h * 0.015,
                f"{value:.1f}h",
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="bold",
                color=TEXT_COLOR,
            )

        # -----------------------------------------------------
        # MISSING VERSION MARKERS
        #
        # Instead of a fake empty bar with vertical N/A text,
        # show a simple dash where the missing bar would be.
        # -----------------------------------------------------

        for position, point in zip(
            bar_positions,
            data_points
        ):

            if point[project_label] is None:

                ax.text(
                    position,
                    max_h * 0.015,
                    "—",
                    ha="center",
                    va="bottom",
                    fontsize=12,
                    fontweight="bold",
                    color=MISSING_COLOR,
                )

        # -----------------------------------------------------
        # AVERAGE LINE
        # -----------------------------------------------------

        if averages[project_label] is not None:

            ax.axhline(
                y=averages[project_label],
                color=colors[
                    index % len(colors)
                ],
                linestyle="--",
                linewidth=1.4,
            )

    # ---------------------------------------------------------
    # AXIS
    # ---------------------------------------------------------

    ax.set_xticks(x)

    ax.set_xticklabels(
        labels,
        rotation=45,
        ha="right",
        fontsize=10,
        color=TEXT_COLOR,
    )

    ax.tick_params(
        axis="y",
        colors=TEXT_COLOR,
    )

    ax.set_ylabel(
        "Hours to Update",
        fontsize=12,
        fontweight="bold",
        color=TEXT_COLOR,
    )

    ax.set_ylim(
        0,
        max_h * 1.25
    )

    # ---------------------------------------------------------
    # TITLE
    # ---------------------------------------------------------

    average_text = " | ".join(
        (
            f"{project_names[label]}: "
            f"{averages[label]:.1f}h"
            if averages[label] is not None
            else f"{project_names[label]}: N/A"
        )
        for label in PROJECTS
    )

    ax.set_title(
        (
            "Modpack Update Speed Comparison\n"
            + average_text
        ),
        fontsize=14,
        fontweight="bold",
        color=TEXT_COLOR,
    )

    # ---------------------------------------------------------
    # LEGEND
    # ---------------------------------------------------------

    ax.legend(
        loc="upper left",
        frameon=False,
        labelcolor=TEXT_COLOR,
    )

    # ---------------------------------------------------------
    # SPINES
    # ---------------------------------------------------------

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.spines["left"].set_color(
        TEXT_COLOR
    )

    ax.spines["bottom"].set_color(
        TEXT_COLOR
    )

    # ---------------------------------------------------------
    # SAVE GRAPH
    # ---------------------------------------------------------

    plt.tight_layout()

    plt.savefig(
        "update_graph.png",
        dpi=150,
        bbox_inches="tight",
        transparent=True,
    )

    print(
        f"\nGraph saved: update_graph.png"
    )

    print(
        f"Displayed {len(data_points)} "
        f"versions."
    )


if __name__ == "__main__":
    main()