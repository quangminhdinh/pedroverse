import cv2
import numpy as np
import subprocess

import torch
import torch.nn.functional as F
import os
import math
import pyxelate
from pyxelate import Pyx, Pal
from .painterlybrush import painterlybrush
from skimage.segmentation import slic
from skimage.util import img_as_float


from .neural_paint_transformer.inference import execute_paint_transformer
from .water_color import generate_water_color


BASE_MODEL_DIR = os.path.join(os.path.dirname(__file__), "model_weights")
PAINTER_MODEL_PATH = os.path.join(BASE_MODEL_DIR, "paint_transformer.pth")

def pixelate(image_bgr, downsample_ratio=4, palette=7):
    """
    Inverts the colors of the input image.
    `intensity` is a placeholder – full invert for now.
    """


    downsample_by = downsample_ratio  # new image will be 1/14th of the original in size
    palette = palette  # find 7 colors

    # 1) Instantiate Pyx transformer
    pyx = Pyx(factor=downsample_by, palette=palette)

    # 2) fit an image, allow Pyxelate to learn the color palette
    pyx.fit(image_bgr)

    # 3) transform image to pixel art using the learned color palette
    new_image = pyx.transform(image_bgr)
    return new_image





def apply_brush_strokes(image_bgr, vertical_brush , horizontal_brush , model_path=PAINTER_MODEL_PATH):
    """
    Applies a painterly brush stroke effect to simulate hand-painted strokes.

    Parameters:
    - image_bgr: Input image in BGR format.
    - stroke_width: Width of the simulated brush strokes.
    - orientation: Direction of strokes; 'random', 'horizontal', or 'vertical'.

    Returns:
    - Image with a brush stroke style overlay.
    """
    output = execute_paint_transformer(image_bgr, vertical_brush=vertical_brush, horizontal_brush=horizontal_brush , model_path=model_path , output_dir=None)
    return output




def apply_voronoi(img,
    num_voronoi_patterns=3,
    oil_paint_size=12,
    oil_paint_dyn_ratio=10,
    use_bilateral_filter=True,):
    """
    Generates a Voronoi-style mosaic effect based on color clustering.
    
    Parameters:
    - image_bgr: Input image in BGR format.
    - cell_count: Approximate number of Voronoi regions.

    Returns:
    - Image stylized with Voronoi tessellation.
    """
    output  = generate_water_color(
        img,
        num_voronoi_patterns=num_voronoi_patterns,
        oil_paint_size=oil_paint_size,
        oil_paint_dyn_ratio=oil_paint_dyn_ratio,
        use_bilateral_filter=use_bilateral_filter,
    )
    return output



# Preset styles
IMPRESSIONIST = [100, [8, 4, 2], 1, 0.5, 1, 1, 4, 16]
EXPRESSIONIST = [50, [8, 4, 2], 0.25, 0.5, 0.7, 1, 10, 16]
COLORIST_WASH = [200, [8, 4, 2], 1, 0.5, 0.5, 1, 4, 16]
POINTILLIST = [100, [4, 2], 1, 0.5, 0.1, 0.5, 0, 0]

STYLE_MAP = {
    "--impressionist": IMPRESSIONIST,
    "--expressionist": EXPRESSIONIST,
    "--colorist_wash": COLORIST_WASH,
    "--pointillist": POINTILLIST
}

def apply_brushstyle(img_path, output_path=None, style_flag="--expressionist"):
    if style_flag not in STYLE_MAP:
        raise ValueError(f"Unknown style_flag '{style_flag}'. Valid options are: {list(STYLE_MAP.keys())}")

    params = STYLE_MAP[style_flag]
    source_img = cv2.imread(img_path)
    if source_img is None:
        raise FileNotFoundError(f"Image not found at: {img_path}")

    painter = painterlybrush()
    result = painter.paint(source_img, *params)

    if output_path:
        cv2.imwrite(output_path, result)

    return result


def stylize_normals_with_slic(normal_map, num_segments=300, compactness=50):
    # Convert image to float and run SLIC
    normal_float = img_as_float(normal_map)
    segments = slic(normal_float, n_segments=num_segments, compactness=compactness, start_label=1)

    # Output image initialized
    output = np.zeros_like(normal_float)

    # Stylize each superpixel by averaging
    for label in np.unique(segments):
        mask = segments == label
        for c in range(3):  # R, G, B
            avg_val = np.mean(normal_float[:, :, c][mask])
            output[:, :, c][mask] = avg_val

    return (output * 255).astype(np.uint8)

def apply_slic(img, num_segments=300, compactness=50):


    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    stylized = stylize_normals_with_slic(img_rgb, num_segments=num_segments, compactness=compactness)
    return stylized
    