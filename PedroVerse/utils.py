import os
import cv2
import numpy as np
import scipy.spatial
import argparse
from PIL import Image, ImageSequence

def read_img(file_path):
    return cv2.imread(file_path)

def edge_detection(img, line_width, blur_amount):
    gray_scale_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray_scale_img_blur = cv2.medianBlur(gray_scale_img, blur_amount)
    img_edges = cv2.adaptiveThreshold(
        gray_scale_img_blur, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY, line_width, blur_amount
    )
    return img_edges

def generate_voronoi_pattern(img_shape, num_cells):
    """Generates a Voronoi pattern and applies directional blur."""
    height, width = img_shape[:2]
    
    print(f"Generating Voronoi pattern with {num_cells} cells...")
    
    # Generate random seed points
    points = np.random.randint(0, (width, height), size=(num_cells, 2))

    # Compute Voronoi tessellation
    vor = scipy.spatial.Voronoi(points)

    # Create an empty image
    voronoi_img = np.zeros((height, width), dtype=np.uint8)

    # Fill Voronoi regions with different grayscale values
    for i, region in enumerate(vor.regions):
        if not -1 in region and len(region) > 0:
            polygon = [vor.vertices[i] for i in region]
            polygon = np.array(polygon, np.int32)
            cv2.fillPoly(voronoi_img, [polygon], (i * 255 // num_cells))

    # Apply directional motion blur
    kernel_size = 15
    kernel = np.zeros((kernel_size, kernel_size))
    kernel[:, int(kernel_size / 2)] = np.ones(kernel_size)  # Vertical blur
    kernel = kernel / kernel_size

    blurred_voronoi = cv2.filter2D(voronoi_img, -1, kernel)

    return blurred_voronoi


def save_steps_as_gif(steps, output_path):
    images = [Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)) for _, img in steps]
    images[0].save(output_path, save_all=True, append_images=images[1:], duration=500, loop=0)



def apply_uv_mask_from_arrays(generated_img, reference_img):
    """
    Applies a UV-based mask to the generated image using the reference image as a binary mask.

    Parameters:
        generated_img (np.ndarray): The image to be masked (e.g., stylized normal map).
        reference_img (np.ndarray): The reference image defining the valid UV area.

    Returns:
        np.ndarray: Masked image with areas outside UV region set to black.
    """
    # Convert to grayscale
    gray_reference = cv2.cvtColor(reference_img, cv2.COLOR_BGR2GRAY)

    # Create binary mask from reference
    _, ref_mask = cv2.threshold(gray_reference, 10, 255, cv2.THRESH_BINARY)
    inverse_mask = cv2.bitwise_not(ref_mask)

    # Apply mask to generated image
    masked_generated = generated_img.copy()
    masked_generated[inverse_mask == 255] = (0, 0, 0)

    return masked_generated




def apply_bilateral_filter(img, diameter=9, sigma_color=75, sigma_space=75):
    """
    Applies a bilateral filter to the input image.

    Parameters:
        img (np.ndarray): Input image (BGR).
        diameter (int): Diameter of each pixel neighborhood.
        sigma_color (float): Filter sigma in color space.
        sigma_space (float): Filter sigma in coordinate space.

    Returns:
        np.ndarray: Smoothed image.
    """
    return cv2.bilateralFilter(img, diameter, sigma_color, sigma_space)