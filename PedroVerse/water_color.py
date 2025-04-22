import os
import cv2
import numpy as np
import scipy.spatial
import argparse
from PIL import Image, ImageSequence
from .utils import generate_voronoi_pattern


def generate_water_color(
    img,
    num_voronoi_patterns=3,
    oil_paint_size=12,
    oil_paint_dyn_ratio=10,
    use_bilateral_filter=True,
    return_steps=False
):
    """
    Applies a cartoonizing effect to an image using oil painting and Voronoi patterns.

    Args:
        img: Input image (numpy array).
        num_voronoi_patterns: Number of Voronoi layers to blend.
        oil_paint_size: Size parameter for oil painting effect.
        oil_paint_dyn_ratio: dynRatio parameter for oil painting effect.
        use_bilateral_filter: Whether to apply bilateral filtering before oil painting.
        return_steps: If True, return a list of (label, image) steps. If False, return only the final image.

    Returns:
        Final cartoonized image, or list of intermediate steps if return_steps=True.
    """

    steps = []
    if return_steps:
        steps.append(("01_Original_Image", img))

    if use_bilateral_filter:
        print("Applying bilateral filter...")
        img = cv2.bilateralFilter(img, d=7, sigmaColor=200, sigmaSpace=200)
        if return_steps:
            steps.append(("02_Smooth_Bilateral_Filter", img))

    print("Applying oil painting effect...")
    oil_paint_img = cv2.xphoto.oilPainting(img, size=oil_paint_size, dynRatio=oil_paint_dyn_ratio)
    if return_steps:
        steps.append(("03_Oil_Painting_Effect", oil_paint_img))

    print("Generating and blending Voronoi patterns...")
    accumulated_voronoi = np.ones_like(oil_paint_img) * 255
    for i in range(num_voronoi_patterns):
        num_cells = np.random.randint(500, 1000)
        voronoi_pattern = generate_voronoi_pattern(oil_paint_img.shape, num_cells)
        voronoi_pattern = cv2.merge([voronoi_pattern] * 3)

        if return_steps:
            steps.append((f"04_Voronoi_Pattern_{i+1}", voronoi_pattern))

        accumulated_voronoi = cv2.multiply(accumulated_voronoi, voronoi_pattern, scale=1/255.0)

    print("Blending final image...")
    final_img = cv2.addWeighted(oil_paint_img, 0.85, accumulated_voronoi, 0.15, 0)
    if return_steps:
        steps.append(("05_Final_Cartoonized", final_img))
        return steps
    else:
        return final_img