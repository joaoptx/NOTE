import matplotlib.colors as mcolors

def reflectance_cmap(name):
    return mcolors.LinearSegmentedColormap.from_list(name, [
        (0.0, "#000000"), (1.0, "#FFFFFF")
    ])

# Definições das bandas
cmap_band07 = mcolors.LinearSegmentedColormap.from_list(
    "Band07", ["#00FFFF", "#000000", "#FFFFFF"], N=256,
)

temps_8_10 = [-90, -80, -70, -60, -50, -40, -35, -30, -25, -20, -15, -10, -5, -2.5, 0]
colors_8_10 = [
    "#ffffff", "#00ffff", "#00ff00", "#0000ff", "#dddddd", "#cccccc", "#aaaaaa", "#aa5500",
    "#aa3300", "#550000", "#aa0000", "#ff0000", "#ffcc00", "#ffff00", "#ffff00"
]
norm_8_10 = mcolors.Normalize(vmin=min(temps_8_10), vmax=max(temps_8_10))
cmap_band08 = mcolors.LinearSegmentedColormap.from_list("Band08", list(zip(norm_8_10(temps_8_10), colors_8_10)), N=256)

temps_ir_std = [-90, -80, -70, -60, -50, -40, -30, -20, -10, 0, 10, 20, 30, 40]
colors_ir_std = [
    "#ff0000", "#ff8000", "#ffff00", "#00ff00", "#00ffff", "#70a0ff", "#a0c0ff", "#b0d0ff",
    "#d0e0e0", "#c0c0c0", "#a0a0a0", "#808080", "#403030", "#000000"
]
norm_ir_std = mcolors.Normalize(vmin=min(temps_ir_std), vmax=max(temps_ir_std))
cmap_ir_standard = mcolors.LinearSegmentedColormap.from_list("IRStandard", list(zip(norm_ir_std(temps_ir_std), colors_ir_std)), N=256)

temps_15 = temps_ir_std
colors_15 = [
    "#0000ff", "#4b0082", "#00ffff", "#00ff00", "#adff2f", "#ffff00", "#ff8000", "#ff0000",
    "#ff00ff", "#dcdcdc", "#a9a9a9", "#696969", "#404040", "#000000"
]
norm_15 = mcolors.Normalize(vmin=min(temps_15), vmax=max(temps_15))
cmap_band15 = mcolors.LinearSegmentedColormap.from_list("Band15", list(zip(norm_15(temps_15), colors_15)), N=256)

# Dicionários de exportação
colormaps_names = {
    1: "Blue Visible", 2: "Red Visible", 3: "Veggie (Near-IR)", 4: "Cirrus (Near-IR)",
    5: "Snow/Ice (Near-IR)", 6: "Cloud Particle Size (Near-IR)", 7: "Shortwave IR",
    8: "Upper-Level Water Vapor", 9: "Mid-Level Water Vapor", 10: "Lower-Level Water Vapor",
    11: "Cloud-Top Phase IR", 12: "Ozone IR", 13: "Clean Longwave IR",
    14: "IR Longwave Window", 15: "Dirty Longwave IR", 16: "CO₂ Longwave IR"
}

vmin_vmax = {
    **{i: (0, 100) for i in range(1, 7)},
    7: (-90, 100),
    **{i: (-90, 0) for i in [8, 9, 10]},
    **{i: (-90, 40) for i in [11, 12, 13, 14, 15, 16]}
}

cmap_lookup = {
    1: reflectance_cmap("Band01"), 2: reflectance_cmap("Band02"), 3: reflectance_cmap("Band03"),
    4: reflectance_cmap("Band04"), 5: reflectance_cmap("Band05"), 6: reflectance_cmap("Band06"),
    7: cmap_band07, 8: cmap_band08, 9: cmap_band08, 10: cmap_band08,
    11: cmap_ir_standard, 12: cmap_ir_standard, 13: cmap_ir_standard,
    14: cmap_ir_standard, 15: cmap_band15, 16: cmap_ir_standard
}