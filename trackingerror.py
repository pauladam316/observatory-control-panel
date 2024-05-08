import os
import numpy as np
from astropy.io import fits
from astropy.stats import sigma_clipped_stats
from photutils import DAOStarFinder
from nicegui import ui
from scipy.spatial import cKDTree

# Directory containing the FITS files
fits_dir = '/Users/adampaul/Local Documents/Astrophotography/M106/Good Frames'

def find_stars(fits_file):
    """Detect stars in a FITS image."""
    with fits.open(fits_file) as hdul:
        data = hdul[0].data
        mean, median, std = sigma_clipped_stats(data)
        daofind = DAOStarFinder(fwhm=3.0, threshold=5.*std)
        stars = daofind(data - median)
        if stars is not None:
            return stars['xcentroid'], stars['ycentroid']
        return np.array([]), np.array([])

def match_stars(positions1, positions2):
    """Match stars from two different images based on their positions."""
    tree1 = cKDTree(positions1)
    tree2 = cKDTree(positions2)
    dists, indices = tree1.query(positions2, k=1)
    
    # Filter out matches with large distances if necessary
    max_distance = 5  # pixels, adjust as needed
    match_indices = indices[dists < max_distance]
    matched_positions1 = positions1[match_indices]
    matched_positions2 = positions2

    return matched_positions1, matched_positions2

def compute_differences():
    """Compute differences in star positions between consecutive images."""
    files = sorted([os.path.join(fits_dir, f) for f in os.listdir(fits_dir) if f.endswith('.fits')], key=os.path.getmtime, reverse=True)[:10]
    files = sorted(files)  # Optional: Sort the selected files by name if needed

    positions = [find_stars(file) for file in files]
    
    differences = []
    for i in range(1, len(positions)):
        if positions[i][0].size == 0 or positions[i-1][0].size == 0:
            continue  # Skip if no stars were found in one of the images

        matched_positions1, matched_positions2 = match_stars(
            np.column_stack((positions[i-1][0], positions[i-1][1])), 
            np.column_stack((positions[i][0], positions[i][1]))
        )

        x_diff = matched_positions2[:, 0] - matched_positions1[:, 0]
        y_diff = matched_positions2[:, 1] - matched_positions1[:, 1]
        differences.append((x_diff.mean(), y_diff.mean()))

    return differences

def plot_differences():
    """Plot the differences on a NiceGUI graph."""
    diffs = compute_differences()
    x_diffs = [diff[0] for diff in diffs]
    y_diffs = [diff[1] for diff in diffs]
    
    with ui.plot() as plot:
        plot.line(x_diffs, name='X Differences')
        plot.line(y_diffs, name='Y Differences')
        plot.xlabel('Image Pair')
        plot.ylabel('Position Difference (pixels)')
        plot.legend()

ui.button('Plot Star Position Differences', on_click=plot_differences)
ui.run()