
from datetime import datetime
from itertools import cycle
from math import ceil
from typing import List
import matplotlib.pyplot as plt
import seaborn as sns

class TimeSeriesPlotter:
    def __init__(self):
        self.colors = sns.color_palette("tab10")

    @staticmethod
    def _break_gaps(time_axis_data, time_series, max_gap):
        """Insert a NaN wherever consecutive samples are separated by more than
        max_gap, so matplotlib draws disconnected segments instead of bridging
        the gap. max_gap is a timedelta for datetime axes, a float otherwise."""
        if max_gap is None or len(time_axis_data) < 2:
            return time_axis_data, time_series

        x_out = [time_axis_data[0]]
        y_out = [time_series[0]]
        for previous_time, current_time, value in zip(time_axis_data, time_axis_data[1:], time_series[1:]):
            if current_time - previous_time > max_gap:
                x_out.append(previous_time)
                y_out.append(float("nan"))
            x_out.append(current_time)
            y_out.append(value)
        return x_out, y_out

    def plot(self,
             time_axis_data: List[datetime]| List[float],
             time_series_data:List[List[float]],
             arrangement: str = "vertical",
             max_plots_per_row: int = 3,
             row_spacing:float = 0.5,
             row_width: float = 5,
             graph_height: float = 3,
             colors: List[str] = sns.color_palette("tab10"),
             x_label: str = "Time",
             y_labels: List[str] = None,
             titles: List[str] = None,
             rotate_date_labels: bool = False,
             show_in_same_plot: bool = False,
             labels: List[str] = None,
             show_legend: bool = True,
             max_gap = None,
             ax: plt.Axes = None,
             )-> plt.Axes:

        num_plots = len(time_series_data)
        if y_labels is None or len(y_labels) != num_plots:
            y_label = "Value"
        if num_plots == 0:
            raise ValueError("time_series_data must contain at least one series.")

        label_rotation = 90 if rotate_date_labels else 0

        if ax is not None and not show_in_same_plot:
            raise ValueError("ax can only be used together with show_in_same_plot=True.")

        if show_in_same_plot:
            if ax is None:
                fig, ax = plt.subplots(figsize=(row_width, graph_height))
            color_cycle = cycle(colors)
            for i, time_series in enumerate(time_series_data):
                if labels and i < len(labels):
                    series_label = labels[i]
                elif y_labels and i < len(y_labels):
                    series_label = y_labels[i]
                else:
                    series_label = f"Series {i}"
                x_plot, y_plot = self._break_gaps(time_axis_data, time_series, max_gap)
                ax.plot(x_plot, y_plot, color=next(color_cycle), label=series_label)
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_labels[0] if y_labels and len(y_labels) == 1 else "Value")
            if titles:
                ax.set_title(titles[0])
            if show_legend:
                ax.legend()
            plt.setp(ax.get_xticklabels(), rotation=label_rotation, ha="right" if rotate_date_labels else "center")
            return ax

        if arrangement == "vertical":
            num_rows = num_plots
            num_cols = 1
        else:
            num_cols = min(num_plots, max_plots_per_row)
            num_rows = ceil(num_plots / num_cols)

        fig, axes = plt.subplots(
            nrows=num_rows,
            ncols=num_cols,
            figsize=(row_width * num_cols, graph_height * num_rows),
            squeeze=False,
        )
        axes = axes.flatten()

        color_cycle = cycle(colors)
        for i, time_series in enumerate(time_series_data):
            if y_labels and i < len(y_labels):
                y_label = y_labels[i]
            ax = axes[i]
            x_plot, y_plot = self._break_gaps(time_axis_data, time_series, max_gap)
            ax.plot(x_plot, y_plot, color=next(color_cycle))
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)
            if titles and i < len(titles):
                ax.set_title(titles[i])
            plt.setp(ax.get_xticklabels(), rotation=label_rotation, ha="right" if rotate_date_labels else "center")

        for j in range(num_plots, len(axes)):
            axes[j].set_visible(False)

        fig.subplots_adjust(hspace=row_spacing)
        return axes[:num_plots]
