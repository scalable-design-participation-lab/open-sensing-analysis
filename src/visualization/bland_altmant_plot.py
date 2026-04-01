from typing import List
import numpy as np
import matplotlib.pyplot as plt
def plot_bland_altman(
        series1:List[float],
        series2:List[float],
        color_extreme_bars:str = "#1d65d1",
        color_mean_bar:str = "#ff1764",
        color_points:str = "#982ef0", 
        width:int = 5, 
        height:int = 5,
        xlabel:str = "Value averages",
        ylabel:str = "Value differences (test - reference)",
        title:str = "Bland-Altman plot",
        linewidth:int = 2

) -> None:
    """
    Parameters
    ----------
    series1
        List of test values to compare
    series2
        Lista de valores de referencia a comparar
    """
    
    if(len(series1) != len(series2)):
        print("The length of the provided data arrays should be equal.")
        return
    n = len(series1)
    averages = [(series1[i] + series2[i])/2 for i in range(0, n)]
    differences = [series1[i] - series2[i] for i in range(0,n)]

    sd = np.std(differences)
    upper_bar_value = 1.96*sd
    lower_bar_value = -1.96*sd

    mean_difference = np.mean(differences)

    plot_horizontal_line = lambda ax, min_x, max_x, height, color: ax.plot([min_x, max_x], [height, height], color = color, linewidth = linewidth) 

    min_x = np.min(averages)
    max_x = np.max(averages)



    fig, ax = plt.subplots(figsize = (width, height))
    ax.plot(averages, differences, marker = "o", markerfacecolor='none', markeredgecolor=color_points, linestyle = "none")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    #Add text to the lines
    ax.text(max_x, upper_bar_value + 0.05*(np.max(differences) - np.min(differences)), "1.96 SD", horizontalalignment = "right", verticalalignment = "baseline")
    ax.text(max_x, lower_bar_value - 0.05*(np.max(differences) - np.min(differences)), "-1.96 SD", horizontalalignment = "right", verticalalignment = "top")
    plot_horizontal_line(ax, min_x, max_x, upper_bar_value, color_extreme_bars)
    plot_horizontal_line(ax, min_x, max_x, lower_bar_value, color_extreme_bars)
    plot_horizontal_line(ax, min_x, max_x, mean_difference, color_mean_bar)





    

