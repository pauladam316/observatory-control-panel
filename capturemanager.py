import os
import glob
from astropy.io import fits
from PIL import Image
import shutil
import numpy as np

# Cache to store paths of converted images
converted_path = "/home/observatory/capture-tmp/capture.png" #"/Users/adampaul/capture-tmp/capture.png"
last_converted = None
source_dir = "/home/observatory/m106/M_106/Light" #/Users/adampaul/Local Documents/Astrophotography/Pixinsight Processing/M106/Raw"

def convert_fits_to_png():
    global last_converted
    # Ensure the temp directory exists
    temp_dir = os.path.join(source_dir, 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    
    # Find all FITS files in the directory
    fits_files = glob.glob(os.path.join(source_dir, '*.fits'))
    
    if not fits_files:
        raise FileNotFoundError("No FITS files found in the directory.")

    # Determine the most recent FITS file
    recent_fits = max(fits_files, key=os.path.getmtime)

    # Check if this file has already been converted
    if recent_fits == last_converted:
        return False


    # Load the FITS file
    with fits.open(recent_fits) as hdul:
        image_data = hdul[0].data

    image_data = np.nan_to_num(image_data)

    # Calculate the histogram of the image data
    histogram, bin_edges = np.histogram(image_data.flatten(), bins='auto', density=True)

    # Compute cumulative distribution from the histogram
    cdf = histogram.cumsum()
    cdf_normalized = cdf / cdf[-1]  # Normalize

    # Determine clipping points (e.g., 0.25% and 99.75%)
    cdf_min = np.searchsorted(cdf_normalized, 0.0025)
    cdf_max = np.searchsorted(cdf_normalized, 0.9975)

    # Clip the image data to these points and scale to 0-255
    clipped_data = np.clip(image_data, bin_edges[cdf_min], bin_edges[cdf_max])
    scaled_data = (clipped_data - bin_edges[cdf_min]) / (bin_edges[cdf_max] - bin_edges[cdf_min]) * 255
    image_uint8 = scaled_data.astype(np.uint8)

    # Convert to PIL image
    image = Image.fromarray(image_uint8)

    original_width, original_height = image.size
    
    # New width
    new_width = 900
    
    # Calculate the new height maintaining the aspect ratio
    new_height = int(new_width * original_height / original_width)
    
    # Resize the image
    resized_img = image.resize((new_width, new_height), Image.LANCZOS)

    
    # Save the image as PNG
    resized_img.save(converted_path, 'PNG')
    last_converted = recent_fits


    return True