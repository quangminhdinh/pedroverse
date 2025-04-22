from PIL import Image
import os

# Path to your folder with JPGs
folder_path = "./output/albedo"
output_gif = "output/output.gif"
duration = 100  # duration per frame in milliseconds
num_frames = 20  # number of images to include in the GIF

# Get all JPG files and sort them (important for correct order)
image_files = sorted([
    file for file in os.listdir(folder_path)
    if file.lower().endswith(".jpg")
])

# Sample evenly spaced frames
total_images = len(image_files)
step = max(total_images // num_frames, 1)
sampled_files = image_files[::step][:num_frames]

# Load images
images = [Image.open(os.path.join(folder_path, file)) for file in sampled_files]

# Save as GIF
if images:
    os.makedirs(os.path.dirname(output_gif), exist_ok=True)
    images[0].save(
        output_gif,
        save_all=True,
        append_images=images[1:],
        duration=duration,
        loop=0
    )
    print(f"GIF saved as {output_gif} using {len(images)} frames.")
else:
    print("No JPG images found in the folder.")
