# EPA AQS Air and Temperature Data for 2024 to 2026

library(tidyverse)
library(lubridate)
library(patchwork)

# palette
teal  <- "#3498BA"
coral <- "#E47C61"
blue  <- "#376ED2"
rose  <- "#D73693"
slate <- "#424A4C"
warm_bg <- "#F7F5EF"

data_dir <- getwd()
fig_dir <- file.path(data_dir, "figures")
dir.create(fig_dir, showWarnings = FALSE, recursive = TRUE)

read_filter <- function(pattern, dir) {
  fs <- list.files(dir, pattern = pattern, full.names = TRUE)
  if (!length(fs)) stop("no files matching ", pattern, " in ", dir)
  cat("reading:", basename(fs), "\n")
  map_dfr(fs, \(f) read_csv(f, show_col_types = FALSE) |>
            filter(`State Code` == "25", `County Code` == "025"))
}

pm_raw <- read_filter("^daily_88101_\\d{4}\\.csv$", data_dir) |>
  mutate(date = as.Date(`Date Local`))

tmp_raw <- read_filter("^daily_TEMP_\\d{4}\\.csv$", data_dir) |>
  mutate(date = as.Date(`Date Local`))

cat("\npm2.5:", nrow(pm_raw), "rows,", n_distinct(pm_raw$`Site Num`), "sites\n")
cat("temp: ", nrow(tmp_raw), "rows,", n_distinct(tmp_raw$`Site Num`), "sites\n\n")


pm <- pm_raw |>
  transmute(
    date, year = year(date), month = month(date),
    mo = month(date, label = TRUE), doy = yday(date),
    site = paste(`State Code`, `County Code`, `Site Num`, sep = "-"),
    site_name = `Local Site Name`,
    lat = Latitude, lon = Longitude,
    pm25 = `Arithmetic Mean`, aqi = AQI,
    units = `Units of Measure`, n_obs = `Observation Count`,
    method = `Method Name`
  )

tp <- tmp_raw |>
  transmute(
    date, year = year(date), month = month(date),
    mo = month(date, label = TRUE), doy = yday(date),
    site = paste(`State Code`, `County Code`, `Site Num`, sep = "-"),
    site_name = `Local Site Name`,
    lat = Latitude, lon = Longitude,
    temp_f = `Arithmetic Mean`, temp_max_f = `1st Max Value`,
    units = `Units of Measure`, n_obs = `Observation Count`,
    method = `Method Name`
  )

# Export CSVs

write_csv(pm, file.path(data_dir, "boston_pm25_combined.csv"))
write_csv(tp, file.path(data_dir, "boston_temp_combined.csv"))
cat("saved boston_pm25_combined.csv + boston_temp_combined.csv\n\n")

# Summary Stats

cat("=== pm2.5 (ug/m3) ===\n")
pm |> summarise(
  n = n(), sites = n_distinct(site),
  range = paste(min(date), "to", max(date)),
  mean = round(mean(pm25, na.rm = T), 2),
  sd = round(sd(pm25, na.rm = T), 2),
  med = round(median(pm25, na.rm = T), 2),
  p25 = round(quantile(pm25, .25, na.rm = T), 2),
  p75 = round(quantile(pm25, .75, na.rm = T), 2),
  p95 = round(quantile(pm25, .95, na.rm = T), 2),
  max = round(max(pm25, na.rm = T), 2),
  pct_over_35 = round(mean(pm25 > 35, na.rm = T) * 100, 2),
  pct_over_12 = round(mean(pm25 > 12, na.rm = T) * 100, 2)
) |> print()

cat("\npm2.5 by month:\n")
pm |> group_by(month, mo) |>
  summarise(mean = round(mean(pm25, na.rm = T), 2),
            med = round(median(pm25, na.rm = T), 2),
            sd = round(sd(pm25, na.rm = T), 2),
            max = round(max(pm25, na.rm = T), 2),
            n = n(), .groups = "drop") |> print(n = 12)

cat("\npm2.5 by site:\n")
pm |> group_by(site, site_name, lat, lon) |>
  summarise(mean = round(mean(pm25, na.rm = T), 2),
            med = round(median(pm25, na.rm = T), 2),
            max = round(max(pm25, na.rm = T), 2),
            n = n(), .groups = "drop") |> print()

cat("\n=== temperature (F) ===\n")
tp |> summarise(
  n = n(), sites = n_distinct(site),
  range = paste(min(date), "to", max(date)),
  mean = round(mean(temp_f, na.rm = T), 2),
  sd = round(sd(temp_f, na.rm = T), 2),
  min = round(min(temp_f, na.rm = T), 2),
  max = round(max(temp_f, na.rm = T), 2),
  days_over_90 = sum(temp_max_f > 90, na.rm = T),
  days_over_95 = sum(temp_max_f > 95, na.rm = T)
) |> print()

cat("\ntemp by month:\n")
tp |> group_by(month, mo) |>
  summarise(mean = round(mean(temp_f, na.rm = T), 2),
            mean_max = round(mean(temp_max_f, na.rm = T), 2),
            abs_max = round(max(temp_max_f, na.rm = T), 2),
            n = n(), .groups = "drop") |> print(n = 12)

theme_p <- function(sz = 11) {
  theme_minimal(base_size = sz) +
    theme(
      plot.title = element_text(face = "bold", size = sz + 2,
                                family = "Crimson Text"),
      plot.subtitle = element_text(color = "grey40", size = sz - 1),
      panel.grid.minor = element_blank(),
      legend.position = "bottom",
      plot.background = element_rect(fill = warm_bg, color = NA)
    )
}

# Fig 1: pm2.5 time series 

p1 <- ggplot(pm, aes(date, pm25)) +
  geom_point(alpha = .3, size = .8, color = teal) +
  geom_smooth(method = "loess", span = .15, se = TRUE,
              color = blue, fill = "#B0C8E8", linewidth = .8) +
  geom_hline(yintercept = 35, lty = "dashed", color = coral, linewidth = .5) +
  geom_hline(yintercept = 12, lty = "dotted", color = rose, linewidth = .5) +
  annotate("text", x = min(pm$date) + 15, y = 36.5,
           label = "24-hr NAAQS (35)", size = 3, color = coral, hjust = 0) +
  annotate("text", x = min(pm$date) + 15, y = 13.5,
           label = "Annual NAAQS (12)", size = 3, color = rose, hjust = 0) +
  labs(title = "Daily PM2.5, Boston (Suffolk County)",
       subtitle = paste(min(pm$date), "to", max(pm$date)),
       x = NULL, y = expression(PM[2.5]~"(µg/m"^3*")")) +
  theme_p()

ggsave(file.path(fig_dir, "pm25_timeseries.png"), p1,
       width = 10, height = 5, dpi = 300, bg = warm_bg)

# Fig 2: PM2.5 monthly 

p2 <- ggplot(pm, aes(mo, pm25)) +
  geom_boxplot(fill = alpha(teal, .35), color = teal, outlier.size = .8,
               outlier.alpha = .4) +
  geom_hline(yintercept = 12, lty = "dotted", color = rose) +
  labs(title = "PM2.5 by Month", x = NULL,
       y = expression(PM[2.5]~"(µg/m"^3*")")) +
  theme_p()

ggsave(file.path(fig_dir, "pm25_monthly.png"), p2,
       width = 8, height = 5, dpi = 300, bg = warm_bg)

# Fig 3: temp time series 

p3 <- ggplot(tp, aes(date, temp_f)) +
  geom_point(alpha = .3, size = .8, color = coral) +
  geom_smooth(method = "loess", span = .15, se = TRUE,
              color = "#8B3A1A", fill = alpha(coral, .25), linewidth = .8) +
  geom_hline(yintercept = 90, lty = "dashed", color = rose, linewidth = .5) +
  annotate("text", x = min(tp$date) + 15, y = 92,
           label = "90°F", size = 3, color = rose, hjust = 0) +
  labs(title = "Daily Mean Temperature, Boston (Suffolk County)",
       subtitle = paste(min(tp$date), "to", max(tp$date)),
       x = NULL, y = "Temperature (°F)") +
  theme_p()

ggsave(file.path(fig_dir, "temp_timeseries.png"), p3,
       width = 10, height = 5, dpi = 300, bg = warm_bg)

# Fig 4: temp monthly 

p4 <- ggplot(tp, aes(mo, temp_max_f)) +
  geom_boxplot(fill = alpha(coral, .35), color = coral, outlier.size = .8,
               outlier.alpha = .4) +
  geom_hline(yintercept = 90, lty = "dashed", color = rose) +
  labs(title = "Daily Max Temperature by Month", x = NULL,
       y = "Max Temperature (°F)") +
  theme_p()

ggsave(file.path(fig_dir, "temp_monthly.png"), p4,
       width = 8, height = 5, dpi = 300, bg = warm_bg)

# Fig 5: pm2.5 histogram

p5 <- ggplot(pm, aes(pm25)) +
  geom_histogram(binwidth = 1, fill = teal, color = "white", linewidth = .2) +
  geom_vline(xintercept = 12, lty = "dotted", color = rose, linewidth = .7) +
  geom_vline(xintercept = 35, lty = "dashed", color = coral, linewidth = .7) +
  labs(title = "Distribution of Daily PM2.5",
       x = expression(PM[2.5]~"(µg/m"^3*")"), y = "Count") +
  theme_p()

ggsave(file.path(fig_dir, "pm25_histogram.png"), p5,
       width = 7, height = 5, dpi = 300, bg = warm_bg)

# Fig 6: calendar heatmap 

pm_daily <- pm |>
  group_by(date, year, month, doy) |>
  summarise(pm25 = mean(pm25, na.rm = T), .groups = "drop") |>
  mutate(week = isoweek(date),
         wday = wday(date, label = TRUE, week_start = 1))

p6 <- ggplot(pm_daily, aes(week, fct_rev(wday), fill = pm25)) +
  geom_tile(color = "white", linewidth = .3) +
  scale_fill_gradient2(low = teal, mid = "#F5E6A3", high = coral,
                       midpoint = 12, name = expression(PM[2.5])) +
  facet_wrap(~year, ncol = 1) +
  labs(title = "Daily PM2.5 Calendar", x = "Week", y = NULL) +
  theme_p() +
  theme(panel.grid = element_blank())

ggsave(file.path(fig_dir, "pm25_calendar.png"), p6,
       width = 12, height = 4 * n_distinct(pm_daily$year),
       dpi = 300, bg = warm_bg)

# Fig 7: pm2.5 vs temp scatterplot

pm_j <- pm |> group_by(date) |>
  summarise(pm25 = mean(pm25, na.rm = T), .groups = "drop")
tp_j <- tp |> group_by(date) |>
  summarise(temp_f = mean(temp_f, na.rm = T),
            temp_max_f = max(temp_max_f, na.rm = T), .groups = "drop")

combo <- inner_join(pm_j, tp_j, by = "date") |>
  mutate(
    month = month(date),
    season = case_when(
      month %in% c(12, 1, 2) ~ "Winter",
      month %in% 3:5  ~ "Spring",
      month %in% 6:8  ~ "Summer",
      month %in% 9:11 ~ "Fall"
    ) |> factor(levels = c("Winter", "Spring", "Summer", "Fall"))
  )

season_pal <- c(Winter = blue, Spring = "#45BD8F", Summer = coral, Fall = "#D4943A")

p7 <- ggplot(combo, aes(temp_f, pm25, color = season)) +
  geom_point(alpha = .5, size = 1.2) +
  geom_smooth(method = "lm", se = FALSE, linewidth = .7) +
  scale_color_manual(values = season_pal) +
  geom_hline(yintercept = 12, lty = "dotted", color = "grey50") +
  labs(title = "PM2.5 vs. Temperature by Season",
       x = "Mean Daily Temperature (°F)",
       y = expression(PM[2.5]~"(µg/m"^3*")"), color = NULL) +
  theme_p()

ggsave(file.path(fig_dir, "pm25_vs_temp.png"), p7,
       width = 8, height = 6, dpi = 300, bg = warm_bg)

# correlation
cat("\n=== pm2.5 ~ temp correlation ===\n")
cat("pearson r:", round(cor(combo$pm25, combo$temp_f, use = "complete.obs"), 3), "\n\n")
combo |> group_by(season) |>
  summarise(r = round(cor(pm25, temp_f, use = "complete.obs"), 3),
            n = n(), .groups = "drop") |> print()

# Fig 8: site comparison 

if (n_distinct(pm$site) > 1) {
  pm_site_mo <- pm |>
    group_by(site, site_name, year, month, mo) |>
    summarise(pm25 = mean(pm25, na.rm = T), .groups = "drop") |>
    mutate(dt = make_date(year, month, 1))
  
  p8 <- ggplot(pm_site_mo, aes(dt, pm25, color = site_name)) +
    geom_line(linewidth = .7) + geom_point(size = 1.5) +
    labs(title = "Monthly PM2.5 by Monitor",
         x = NULL, y = expression(PM[2.5]~"(µg/m"^3*")"), color = NULL) +
    theme_p()
  
  ggsave(file.path(fig_dir, "pm25_by_site.png"), p8,
         width = 10, height = 5, dpi = 300, bg = warm_bg)
}

cat("\ndone. figures ->", fig_dir, "\n")