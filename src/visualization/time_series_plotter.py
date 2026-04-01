
from datetime import datetime
from itertools import cycle
from math import ceil
from typing import List
import matplotlib.pyplot as plt
import seaborn as sns

class TimeSeriesPlotter:
    def __init__(self):
        self.colors = sns.color_palette("tab10")

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
             )-> plt.Axes:
        """
        Docstring for plot
        
        :param self: Description
        :param ax: Description
        :param time_axis_data: Description
        :type time_axis_data: List[datetime] | List[float]
        :param time_series_data: Description
        :type time_series_data: List[List[float]]
        :param arrangement: Description
        :type arrangement: str
        :param max_plots_per_row: Description
        :type max_plots_per_row: int
        :param row_spacing: Description
        :type row_spacing: float
        :param row_width: Description
        :type row_width: float
        :param graph_height: Description
        :type graph_height: float
        """

        num_plots = len(time_series_data)
        if y_labels is None or len(y_labels) != num_plots:
            y_label = "Value"
        if num_plots == 0:
            raise ValueError("time_series_data must contain at least one series.")

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
            ax.plot(time_axis_data, time_series, color=next(color_cycle))
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)
            if titles and i < len(titles):
                ax.set_title(titles[i])

        for j in range(num_plots, len(axes)):
            axes[j].set_visible(False)

        fig.subplots_adjust(hspace=row_spacing)
        return axes[:num_plots]
