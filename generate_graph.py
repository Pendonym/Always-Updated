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

    # Mojang manifest is newest -> oldest.
    manifest_order = list(mc_versions.keys())

    # ---------------------------------------------------------
    # GET ALL VERSIONS FROM ALL PROJECTS
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
    # FILTER VALID VERSIONS
    # ---------------------------------------------------------

    valid_versions = []

    for version in all_versions:

        if version in DISALLOWED_VERSIONS:
            continue

        if version not in mc_versions:
            continue

        valid_versions.append(version)

    # ---------------------------------------------------------
    # SORT NEWEST -> OLDEST
    # ---------------------------------------------------------

    valid_versions.sort(
        key=lambda version: manifest_order.index(version)
    )

    # ---------------------------------------------------------
    # ONLY USE THE LATEST 5
    # ---------------------------------------------------------

    selected_versions = valid_versions[:5]

    print(
        f"\nUsing the latest "
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

        point = {
            "label": mc_version
        }

        # -----------------------------------------------------
        # CALCULATE EACH PROJECT'S UPDATE TIME
        # -----------------------------------------------------

        for label in PROJECTS:

            if mc_version not in project_times[label]:
                point[label] = None
                continue

            delta = (
                project_times[label][mc_version]
                - mc_release_time
            ).total_seconds() / 3600

            # Ignore impossible negative values.
            if delta < 0:
                point[label] = None
            else:
                point[label] = round(delta, 1)

        data_points.append(point)

        # -----------------------------------------------------
        # PRINT INDIVIDUAL RESULT
        # -----------------------------------------------------

        output = f"  {mc_version}:"

        for label in PROJECTS:

            value = point[label]

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
            averages[label] = sum(values) / len(values)
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

    # =========================================================
    # GRAPH
    # =========================================================

    TEXT_COLOR = "#2ECC71"

    COLORS = {
        "Always Updated": "#FFD700",
        "Wmfgn1eN": "#4DA6FF",
        "Gvp9bbxY": "#B06CFF",
    }

    # ---------------------------------------------------------
    # FIGURE
    #
    # Top:
    #   Average Update Time
    #
    # Bottom:
    #   Individual versions
    # ---------------------------------------------------------

    fig = plt.figure(
        figsize=(14, 9)
    )

    fig.patch.set_alpha(0.0)

    grid = fig.add_gridspec(
        2,
        1,
        height_ratios=[2.2, 1.5],
        hspace=0.35,
    )

    ax_avg = fig.add_subplot(grid[0])
    ax_detail = fig.add_subplot(grid[1])

    ax_avg.patch.set_alpha(0.0)
    ax_detail.patch.set_alpha(0.0)

    # =========================================================
    # TOP GRAPH — AVERAGE UPDATE TIME
    # =========================================================

    average_labels = [
        project_names[label]
        for label in PROJECTS
    ]

    average_values = [
        averages[label]
        if averages[label] is not None
        else 0
        for label in PROJECTS
    ]

    average_colors = [
        COLORS[label]
        for label in PROJECTS
    ]

    x_avg = list(range(len(PROJECTS)))

    bars = ax_avg.bar(
        x_avg,
        average_values,
        width=0.55,
        color=average_colors,
        edgecolor="black",
        linewidth=0.8,
    )

    # ---------------------------------------------------------
    # AVERAGE VALUE LABELS
    # ---------------------------------------------------------

    max_average = max(
        average_values
    )

    for bar, value in zip(
        bars,
        average_values
    ):

        if value <= 0:
            continue

        ax_avg.text(
            bar.get_x()
            + bar.get_width() / 2,
            bar.get_height()
            + max_average * 0.025,
            f"{value:.1f}h",
            ha="center",
            va="bottom",
            fontsize=13,
            fontweight="bold",
            color=TEXT_COLOR,
        )

    # ---------------------------------------------------------
    # TOP TITLE
    # ---------------------------------------------------------

    ax_avg.set_title(
        "Average Time to Update",
        fontsize=19,
        fontweight="bold",
        color=TEXT_COLOR,
        pad=15,
    )

    ax_avg.set_ylabel(
        "Hours",
        fontsize=11,
        fontweight="bold",
        color=TEXT_COLOR,
    )

    ax_avg.set_xticks(x_avg)

    ax_avg.set_xticklabels(
        average_labels,
        fontsize=11,
        color=TEXT_COLOR,
    )

    ax_avg.tick_params(
        axis="y",
        colors=TEXT_COLOR,
    )

    # Give the average chart a reasonable amount
    # of headroom without letting an individual
    # outlier determine the scale.
    ax_avg.set_ylim(
        0,
        max_average * 1.25
    )

    # ---------------------------------------------------------
    # AVERAGE GRAPH SPINES
    # ---------------------------------------------------------

    ax_avg.spines["top"].set_visible(False)
    ax_avg.spines["right"].set_visible(False)

    ax_avg.spines["left"].set_color(
        TEXT_COLOR
    )

    ax_avg.spines["bottom"].set_color(
        TEXT_COLOR
    )

    # =========================================================
    # BOTTOM GRAPH — INDIVIDUAL RESULTS
    # =========================================================

    versions = [
        point["label"]
        for point in data_points
    ]

    x_detail = list(
        range(len(versions))
    )

    project_count = len(PROJECTS)

    width = 0.75 / project_count

    for index, project_label in enumerate(PROJECTS):

        offset = (
            index
            - (project_count - 1) / 2
        ) * width

        positions = [
            x + offset
            for x in x_detail
        ]

        existing_positions = []
        existing_values = []

        for position, point in zip(
            positions,
            data_points
        ):

            value = point[project_label]

            if value is not None:
                existing_positions.append(position)
                existing_values.append(value)

        bars = ax_detail.bar(
            existing_positions,
            existing_values,
            width=width,
            color=COLORS[project_label],
            edgecolor="black",
            linewidth=0.5,
            label=project_names[project_label],
        )

        # -----------------------------------------------------
        # INDIVIDUAL VALUE LABELS
        # -----------------------------------------------------

        for bar, value in zip(
            bars,
            existing_values
        ):

            ax_detail.text(
                bar.get_x()
                + bar.get_width() / 2,
                bar.get_height()
                + 0.8,
                f"{value:.1f}",
                ha="center",
                va="bottom",
                fontsize=7,
                fontweight="bold",
                color=TEXT_COLOR,
            )

        # -----------------------------------------------------
        # MISSING DATA MARKER
        # -----------------------------------------------------

        for position, point in zip(
            positions,
            data_points
        ):

            if point[project_label] is None:

                ax_detail.text(
                    position,
                    0.5,
                    "N/A",
                    ha="center",
                    va="bottom",
                    fontsize=11,
                    fontweight="bold",
                    color="#777777",
                )

    # ---------------------------------------------------------
    # DETAIL TITLE
    # ---------------------------------------------------------

    ax_detail.set_title(
        "Individual Update Times",
        fontsize=13,
        fontweight="bold",
        color=TEXT_COLOR,
        pad=10,
    )

    ax_detail.set_ylabel(
        "Hours",
        fontsize=10,
        fontweight="bold",
        color=TEXT_COLOR,
    )

    ax_detail.set_xticks(
        x_detail
    )

    ax_detail.set_xticklabels(
        versions,
        rotation=30,
        ha="right",
        fontsize=9,
        color=TEXT_COLOR,
    )

    ax_detail.tick_params(
        axis="y",
        colors=TEXT_COLOR,
    )

    # ---------------------------------------------------------
    # DETAIL Y LIMIT
    #
    # The individual graph still needs to contain the
    # 104.5h outlier, but it is now isolated to this
    # smaller lower section.
    # ---------------------------------------------------------

    individual_values = [
        point[label]
        for point in data_points
        for label in PROJECTS
        if point[label] is not None
    ]

    max_individual = max(
        individual_values
    )

    ax_detail.set_ylim(
        0,
        max_individual * 1.18
    )

    # ---------------------------------------------------------
    # DETAIL LEGEND
    # ---------------------------------------------------------

    ax_detail.legend(
        loc="upper left",
        frameon=False,
        labelcolor=TEXT_COLOR,
        fontsize=9,
    )

    # ---------------------------------------------------------
    # DETAIL SPINES
    # ---------------------------------------------------------

    ax_detail.spines["top"].set_visible(False)
    ax_detail.spines["right"].set_visible(False)

    ax_detail.spines["left"].set_color(
        TEXT_COLOR
    )

    ax_detail.spines["bottom"].set_color(
        TEXT_COLOR
    )

    # ---------------------------------------------------------
    # MAIN FIGURE TITLE
    # ---------------------------------------------------------

    fig.suptitle(
        "Modpack Update Speed Comparison",
        fontsize=22,
        fontweight="bold",
        color=TEXT_COLOR,
        y=0.98,
    )

    # ---------------------------------------------------------
    # FOOTER
    # ---------------------------------------------------------

    fig.text(
        0.5,
        0.01,
        "Average is calculated from the latest 5 valid Minecraft versions. "
        "N/A indicates that the modpack did not have that version.",
        ha="center",
        fontsize=8,
        color=TEXT_COLOR,
    )

    # ---------------------------------------------------------
    # SAVE
    # ---------------------------------------------------------

    plt.savefig(
        "update_graph.png",
        dpi=150,
        bbox_inches="tight",
        transparent=True,
    )

    plt.close(fig)

    print(
        "\nGraph saved: update_graph.png"
    )

    print(
        f"Displayed {len(data_points)} "
        "versions."
    )


if __name__ == "__main__":
    main()