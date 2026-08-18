import os
import sys
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# =========================================================
# PROJECTS
# =========================================================

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


# =========================================================
# MODRINTH
# =========================================================

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
    Gets every Modrinth project version.

    IMPORTANT:
    Multiple Modrinth project versions can target the same
    Minecraft version.

    Example:

        AU v1 -> 26.3-snapshot-8
        AU v2 -> 26.3-snapshot-8
        AU v3 -> 26.3-snapshot-8

    Only the EARLIEST publication time is used for
    26.3-snapshot-8.

    Returns:

        {
            "26.3-snapshot-8": datetime(...),
            "26.3-snapshot-7": datetime(...),
            ...
        }
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

            if game_version in DISALLOWED_VERSIONS:
                continue

            if (
                game_version not in earliest
                or published < earliest[game_version]
            ):
                earliest[game_version] = published

    return earliest


# =========================================================
# MOJANG
# =========================================================

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
    Gets the official Minecraft releaseTime.

    Falls back to time if releaseTime isn't available.
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


# =========================================================
# MAIN
# =========================================================

def main():

    print("==========================================")
    print("       MODRINTH UPDATE SPEED COMPARISON")
    print("==========================================\n")

    # =====================================================
    # GET PROJECT NAMES
    # =====================================================

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

    # =====================================================
    # GET MODRINTH VERSION DATA
    # =====================================================

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
                f"  Found {len(times)} unique Minecraft versions."
            )

        except Exception as e:

            print(
                f"  ERROR: {e}"
            )

            project_times[label] = {}

    # =====================================================
    # GET MOJANG VERSION MANIFEST
    # =====================================================

    print(
        "\nFetching Mojang version manifest..."
    )

    mc_versions = get_mojang_manifest()

    # Mojang manifest is newest -> oldest.
    manifest_order = list(
        mc_versions.keys()
    )

    # =====================================================
    # ALWAYS UPDATED IS THE REFERENCE
    # =====================================================
    #
    # This is the important part.
    #
    # The averages and individual comparison are based on
    # the Minecraft versions that Always Updated itself has
    # uploaded.
    #
    # We do NOT use the union of all three projects anymore.
    # =====================================================

    reference_versions = []

    for version in project_times["Always Updated"]:

        if version in DISALLOWED_VERSIONS:
            continue

        if version not in mc_versions:
            continue

        reference_versions.append(version)

    # Newest -> oldest according to Mojang.
    reference_versions.sort(
        key=lambda version: manifest_order.index(version)
    )

    print(
        f"\nAlways Updated has "
        f"{len(reference_versions)} valid Minecraft versions."
    )

    # =====================================================
    # GET RELEASE TIMES FOR ALL REFERENCE VERSIONS
    # =====================================================

    release_times = {}

    for mc_version in reference_versions:

        try:

            release_times[mc_version] = (
                get_mc_release_time(
                    mc_versions[mc_version]
                )
            )

        except Exception as e:

            print(
                f"Skipping {mc_version}: "
                f"failed to get Minecraft release time "
                f"({e})"
            )

    # =====================================================
    # BUILD ALL-TIME DATA
    # =====================================================
    #
    # This contains EVERY Always Updated version.
    #
    # It is used for the averages.
    # =====================================================

    all_data_points = []

    for mc_version in reference_versions:

        if mc_version not in release_times:
            continue

        mc_release_time = release_times[
            mc_version
        ]

        point = {
            "label": mc_version
        }

        for label in PROJECTS:

            if mc_version not in project_times[label]:

                point[label] = None

                continue

            delta = (
                project_times[label][mc_version]
                - mc_release_time
            ).total_seconds() / 3600

            # Ignore negative values.
            if delta < 0:

                point[label] = None

            else:

                point[label] = round(
                    delta,
                    1
                )

        all_data_points.append(point)

    # =====================================================
    # ALL-TIME AVERAGES
    # =====================================================

    averages = {}

    for label in PROJECTS:

        values = [
            point[label]
            for point in all_data_points
            if point[label] is not None
        ]

        if values:

            averages[label] = (
                sum(values) / len(values)
            )

        else:

            averages[label] = None

    # =====================================================
    # PRINT ALL-TIME AVERAGES
    # =====================================================

    print("\n==========================================")
    print("             ALL-TIME AVERAGES")
    print("==========================================")

    for label in PROJECTS:

        if averages[label] is None:

            print(
                f"{project_names[label]}: N/A"
            )

        else:

            count = sum(
                1
                for point in all_data_points
                if point[label] is not None
            )

            print(
                f"{project_names[label]}: "
                f"{averages[label]:.1f}h "
                f"({count} versions)"
            )

    # =====================================================
    # FASTEST ALL-TIME
    # =====================================================

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
            f"\nFASTEST ALL-TIME: "
            f"{project_names[fastest]} "
            f"({averages[fastest]:.1f}h average)"
        )

    # =====================================================
    # LATEST 5 INDIVIDUAL VERSIONS
    # =====================================================
    #
    # ONLY the latest 5 are shown in the lower graph.
    #
    # These are based on Always Updated's versions, not
    # the union of all projects.
    # =====================================================

    latest_versions = reference_versions[:5]

    print("\n==========================================")
    print("          LATEST 5 VERSIONS")
    print("==========================================")

    latest_data_points = []

    for mc_version in latest_versions:

        # Find the corresponding all-time data point.
        matching = next(
            (
                point
                for point in all_data_points
                if point["label"] == mc_version
            ),
            None,
        )

        if matching is None:
            continue

        latest_data_points.append(
            matching
        )

        output = f"  {mc_version}:"

        for label in PROJECTS:

            value = matching[label]

            if value is None:

                output += (
                    f" {label}=N/A"
                )

            else:

                output += (
                    f" {label}={value:.1f}h"
                )

        print(output)

    # =====================================================
    # GRAPH COLORS
    # =====================================================

    TEXT_COLOR = "#2ECC71"

    COLORS = {
        "Always Updated": "#FFD700",
        "Wmfgn1eN": "#B06CFF",
        "Gvp9bbxY": "#4DA6FF",
    }

    # =====================================================
    # CREATE FIGURE
    # =====================================================

    fig = plt.figure(
        figsize=(14, 9)
    )

    fig.patch.set_alpha(0.0)

    grid = fig.add_gridspec(
        2,
        1,
        height_ratios=[
            2.2,
            1.7,
        ],
        hspace=0.38,
    )

    ax_avg = fig.add_subplot(
        grid[0]
    )

    ax_detail = fig.add_subplot(
        grid[1]
    )

    ax_avg.patch.set_alpha(0.0)
    ax_detail.patch.set_alpha(0.0)

    # =====================================================
    # TOP GRAPH
    # ALL-TIME AVERAGE UPDATE TIME
    # =====================================================

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

    x_avg = list(
        range(len(PROJECTS))
    )

    bars = ax_avg.bar(
        x_avg,
        average_values,
        width=0.55,
        color=average_colors,
        edgecolor="black",
        linewidth=0.8,
    )

    max_average = max(
        average_values
    )

    # =====================================================
    # AVERAGE VALUE LABELS
    # =====================================================

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

    # =====================================================
    # TOP GRAPH TITLE
    # =====================================================

    ax_avg.set_title(
        "Average Update Time - All Minecraft Versions",
        fontsize=18,
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

    ax_avg.set_xticks(
        x_avg
    )

    ax_avg.set_xticklabels(
        average_labels,
        fontsize=11,
        color=TEXT_COLOR,
    )

    ax_avg.tick_params(
        axis="y",
        colors=TEXT_COLOR,
    )

    # Only the averages determine this scale.
    # Individual 104.5h outliers do NOT affect it.
    ax_avg.set_ylim(
        0,
        max_average * 1.25
    )

    # =====================================================
    # TOP SPINES
    # =====================================================

    ax_avg.spines["top"].set_visible(
        False
    )

    ax_avg.spines["right"].set_visible(
        False
    )

    ax_avg.spines["left"].set_color(
        TEXT_COLOR
    )

    ax_avg.spines["bottom"].set_color(
        TEXT_COLOR
    )

    # =====================================================
    # BOTTOM GRAPH
    # LATEST 5 INDIVIDUAL UPDATE TIMES
    # =====================================================

    versions = [
        point["label"]
        for point in latest_data_points
    ]

    x_detail = list(
        range(len(versions))
    )

    project_count = len(
        PROJECTS
    )

    width = (
        0.75 / project_count
    )

    # Find the largest value ONLY among the
    # latest 5 individual versions.
    latest_values = [
        point[label]
        for point in latest_data_points
        for label in PROJECTS
        if point[label] is not None
    ]

    max_latest = (
        max(latest_values)
        if latest_values
        else 1
    )

    # =====================================================
    # DRAW LATEST 5 BARS
    # =====================================================

    for index, project_label in enumerate(
        PROJECTS
    ):

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
            latest_data_points
        ):

            value = point[
                project_label
            ]

            if value is not None:

                existing_positions.append(
                    position
                )

                existing_values.append(
                    value
                )

        bars = ax_detail.bar(
            existing_positions,
            existing_values,
            width=width,
            color=COLORS[
                project_label
            ],
            edgecolor="black",
            linewidth=0.5,
            label=project_names[
                project_label
            ],
        )

        # =================================================
        # VALUE LABELS
        # =================================================

        for bar, value in zip(
            bars,
            existing_values
        ):

            ax_detail.text(
                bar.get_x()
                + bar.get_width() / 2,
                bar.get_height()
                + max_latest * 0.018,
                f"{value:.1f}h",
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="bold",
                color=TEXT_COLOR,
            )

        # =================================================
        # MISSING DATA
        # =================================================

        for position, point in zip(
            positions,
            latest_data_points
        ):

            if point[
                project_label
            ] is None:

                ax_detail.text(
                    position,
                    max_latest * 0.012,
                    "—",
                    ha="center",
                    va="bottom",
                    fontsize=12,
                    fontweight="bold",
                    color="#777777",
                )

    # =====================================================
    # BOTTOM GRAPH TITLE
    # =====================================================

    ax_detail.set_title(
        "Latest 5 Individual Update Times",
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

    ax_detail.set_ylim(
        0,
        max_latest * 1.25
    )

    # =====================================================
    # BOTTOM LEGEND
    # =====================================================

    ax_detail.legend(
        loc="upper left",
        frameon=False,
        labelcolor=TEXT_COLOR,
        fontsize=9,
    )

    # =====================================================
    # BOTTOM SPINES
    # =====================================================

    ax_detail.spines["top"].set_visible(
        False
    )

    ax_detail.spines["right"].set_visible(
        False
    )

    ax_detail.spines["left"].set_color(
        TEXT_COLOR
    )

    ax_detail.spines["bottom"].set_color(
        TEXT_COLOR
    )

    # =====================================================
    # MAIN TITLE
    # =====================================================

    fig.suptitle(
        "Modpack Update Speed Comparison",
        fontsize=21,
        fontweight="bold",
        color=TEXT_COLOR,
        y=0.98,
    )

    # =====================================================
    # FOOTER
    # =====================================================

    fig.text(
        0.5,
        0.01,
        (
            "Average uses every valid Minecraft version "
            "uploaded by Always Updated. "
            "Individual results show only the latest 5. "
            "— = no update for that version."
        ),
        ha="center",
        fontsize=8,
        color=TEXT_COLOR,
    )

    # =====================================================
    # SAVE
    # =====================================================

    plt.savefig(
        "update_graph.png",
        dpi=150,
        bbox_inches="tight",
        transparent=True,
    )

    plt.close(fig)

    # =====================================================
    # FINAL OUTPUT
    # =====================================================

    print("\n==========================================")

    print(
        "Graph saved: update_graph.png"
    )

    print(
        f"All-time average calculated from "
        f"{len(all_data_points)} Always Updated versions."
    )

    print(
        f"Individual graph displays "
        f"{len(latest_data_points)} latest versions."
    )

    print("==========================================")


if __name__ == "__main__":
    main()