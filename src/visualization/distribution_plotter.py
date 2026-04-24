import matplotlib.pyplot as plt
import numpy as np
import matplotlib.cm as cm


class DistributionPlotter:

    def plot_multi_colored_distribution(
        self,
        x_values,
        distribution,
        variable_name,
        colors,
        title="",
        color_bars="#d96f76",
        width=7,
        height=7,
        write_values=True,
        rotation=False,
        save=False,
        file_name="distribution.png",
        decimals=2,
        ax=None,
    ):
        plt.rcParams.update({"font.size": 14})

        if ax is None:
            fig, ax = plt.subplots(figsize=(width, height))
        else:
            fig = ax.figure

        ind = np.arange(len(distribution))
        ax.bar(ind, distribution, color=colors)

        ax.set_xticks(ind)
        ax.set_xticklabels(x_values)
        ax.set_frame_on(False)

        if rotation:
            for label in ax.get_xticklabels():
                label.set_rotation(90)

        ax.set_ylabel(variable_name)

        delta = 0.05 * np.max(distribution)
        ax.set_yticks([])

        if write_values:
            for i in range(len(ind)):
                y_text = distribution[i] + delta
                x_text = ind[i]
                ax.text(
                    x_text,
                    y_text,
                    str(round(distribution[i], decimals)),
                    ha="center",
                )

        ax.set_ylim([0, np.max(distribution) + 4 * delta])

        if title:
            ax.set_title(title)

        fig.tight_layout()

        if save:
            fig.savefig(file_name, dpi=600, bbox_inches="tight")

        return ax

    def plot_distribution(
        self,
        x_values,
        distribution,
        variable_name,
        title="",
        color_bars="#d96f76",
        width=7,
        height=7,
        write_values=True,
        rotation=False,
        save=False,
        file_name="distribution.png",
        decimals=2,
        histogram=False,
        x_label="",
        ax=None,
    ):
        plt.rcParams.update({"font.size": 14})

        if ax is None:
            fig, ax = plt.subplots(figsize=(width, height))
        else:
            fig = ax.figure

        ind = np.arange(len(distribution))

        if not histogram:
            ax.bar(ind, distribution, color=color_bars)
            ax.set_xticks(ind)
            ax.set_xticklabels(x_values)
            ax.set_frame_on(False)
        else:
            bar_width = 1
            ax.bar(ind, distribution, color=color_bars, width=bar_width)
            ax.set_xticks(ind)
            ax.set_xticklabels([round(x, 2) for x in x_values])
            write_values = False
            rotation = True

        if rotation:
            for label in ax.get_xticklabels():
                label.set_rotation(90)

        ax.set_ylabel(variable_name)

        delta = 0.05 * np.max(distribution)

        if not histogram:
            ax.set_yticks([])

        if write_values:
            for i in range(len(ind)):
                y_text = distribution[i] + delta
                x_text = ind[i]
                ax.text(
                    x_text,
                    y_text,
                    str(round(distribution[i], decimals)),
                    ha="center",
                )

        ax.set_ylim([0, np.max(distribution) + 4 * delta])

        if x_label:
            ax.set_xlabel(x_label)

        if title:
            ax.set_title(title)

        fig.tight_layout()

        if save:
            fig.savefig(file_name, dpi=600, bbox_inches="tight")

        return ax

    def plot_population_pyramid(
        self,
        y_categories,
        distribution_left,
        distribution_right,
        population_left_name,
        population_right_name,
        x_label,
        y_label,
        title,
        color_1="#3b79ff",
        color_2="#50ff40",
        width=7,
        height=7,
        save=False,
        file_name="population_pyramid.png",
        ax=None,
    ):
        plt.rcParams.update({"font.size": 14})

        distribution_left = -distribution_left

        max_distribution_1 = np.max(np.abs(distribution_left))
        max_distribution_2 = np.max(np.abs(distribution_right))

        limit = max(max_distribution_1, max_distribution_2)
        limit += 0.2 * limit

        if ax is None:
            fig, ax = plt.subplots(figsize=(width, height))
        else:
            fig = ax.figure

        ax.set_frame_on(False)
        ax.set_title(title)

        bars_left = ax.barh(
            y_categories,
            distribution_left,
            color=color_1,
            label=population_left_name,
        )
        bars_right = ax.barh(
            y_categories,
            distribution_right,
            color=color_2,
            label=population_right_name,
        )

        ax.bar_label(bars_left, labels=[str(round(x, 2)) for x in -bars_left.datavalues])
        ax.bar_label(bars_right, labels=[str(round(x, 2)) for x in bars_right.datavalues])

        ax.set_ylabel(y_label)
        ax.set_xlabel(x_label)

        ax.tick_params(
            axis="y",
            color="blue",
            width=4,
            length=0,
            direction="out",
            labelcolor="blue",
            grid_color="black",
        )

        ax.set_xticks([], minor=True)
        ax.set_xticks([])
        ax.set_xlim([-limit, limit])

        ax.legend(loc="best")
        fig.tight_layout()

        if save:
            fig.savefig(file_name, dpi=600, bbox_inches="tight")

        return ax

    def multi_distribution_plotter(
        self,
        distributions,
        width=7,
        height=7,
        title="",
        gap_factor=3,
        bar_width=0.2,
        distance_between_values=0.2,
        write_values=True,
        rotation=False,
        save=False,
        file_name="distribution.png",
        ylims=None,
        values_on_top=False,
        delta=0.1,
        decimals=1,
        plot_scales=True,
        variable_name="",
        add_dividers=False,
        ax=None,
    ):
        plt.rcParams.update({"font.size": 14})

        if ax is None:
            fig, ax = plt.subplots(figsize=(width, height))
        else:
            fig = ax.figure

        ax.set_frame_on(False)

        n_distributions = len(distributions)
        mid_distance = (
            distance_between_values * (n_distributions - 1)
            + bar_width * n_distributions
        ) / 2

        distance_between_variables = mid_distance * gap_factor
        x_labels = distributions[0]["x"]
        offset_distance = (
            distance_between_values * (n_distributions - 1)
            + n_distributions * bar_width
            + distance_between_variables
        )

        x_label_positions = []
        scales = distributions[0].get("scale", None)
        modified_labels = []

        for i in range(len(x_labels)):
            if plot_scales and scales is not None:
                label = f"{x_labels[i]} ({scales[i][0]}-{scales[i][1]})"
            else:
                label = x_labels[i]
            modified_labels.append(label)

        for i in range(len(x_labels)):
            pos = i * offset_distance + mid_distance - bar_width / 2
            x_label_positions.append(pos)

        ax.set_xticks(x_label_positions)
        ax.set_xticklabels(modified_labels)

        if rotation:
            for label in ax.get_xticklabels():
                label.set_rotation(90)

        for i, dist in enumerate(distributions):
            x_tick_positions = [
                j * offset_distance + i * (bar_width + distance_between_values)
                for j in range(len(dist["x"]))
            ]

            bars = ax.bar(
                x_tick_positions,
                dist["y"],
                color=dist["color_bars"],
                width=bar_width,
                label=dist["label"],
            )

            if values_on_top:
                for bar in bars:
                    y_text = bar.get_height() + delta
                    x_text = bar.get_x() + bar.get_width() / 2
                    ax.text(
                        x_text,
                        y_text,
                        str(round(bar.get_height(), decimals)),
                        ha="center",
                    )

        if add_dividers:
            for i in range(1, len(x_labels)):
                divider_position = i * offset_distance - distance_between_variables / 2
                ax.axvline(divider_position, color="gray", linestyle="dotted", linewidth=1)

        ax.legend(loc="best")

        if ylims:
            ax.set_ylim(ylims)

        if variable_name:
            ax.set_ylabel(variable_name)

        if title:
            ax.set_title(title)

        fig.tight_layout()

        if save:
            fig.savefig(file_name, dpi=600, bbox_inches="tight")

        return ax

    def plot_sorted_horizontal_bar(
        self,
        category_labels,
        values,
        highlighted_categories=None,
        title="",
        xlabel="",
        colormap=cm.viridis,
        highlight_color=cm.viridis(0.2),
        width=12,
        height=10,
        value_label_offset=1,
        save=False,
        x_lim=(0, 120),
        file_name="sorted_horizontal_bar.png",
        units="%",
        min_offset=0,
        n_digits=1,
        ax=None,
    ):
        plt.rcParams.update({"font.size": 14})

        if highlighted_categories is None:
            highlighted_categories = set()

        sorted_indices = np.argsort(values)
        labels_sorted = [category_labels[i] for i in sorted_indices]
        values_sorted = [values[i] for i in sorted_indices]

        m = np.min(values_sorted) - min_offset
        colors = [
            colormap((v - m) / (max(values_sorted) - min(values_sorted)))
            for v in values_sorted
        ]

        if ax is None:
            fig, ax = plt.subplots(figsize=(width, height))
        else:
            fig = ax.figure

        bars = ax.barh(labels_sorted, values_sorted, color=colors)

        ax.set_xlabel(xlabel)
        ax.set_xlim(x_lim)
        ax.invert_yaxis()
        ax.grid(axis="x", linestyle="--", alpha=0.3)

        if title:
            ax.set_title(title, pad=15)

        for label in ax.get_yticklabels():
            base_label = label.get_text().split("\n")[0]
            if base_label in highlighted_categories:
                label.set_fontweight("bold")
                label.set_color(highlight_color)

        for bar, value in zip(bars, values_sorted):
            ax.text(
                value + value_label_offset,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.{n_digits}f}{units}",
                va="center",
            )

        fig.tight_layout()

        if save:
            fig.savefig(file_name, dpi=600, bbox_inches="tight", transparent=True)

        return ax
