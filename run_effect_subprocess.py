import sys
import os
import cv2

# Import real effect implementations
from PedroVerse import pixelate
from PedroVerse import apply_brush_strokes
from PedroVerse import apply_voronoi
from PedroVerse import apply_brushstyle
from PedroVerse import apply_slic
from PedroVerse import apply_uv_mask_from_arrays
from PedroVerse import edge_detection, apply_bilateral_filter


def load_image(path):
    if not os.path.exists(path):
        print(f"[ERROR] Input image not found: {path}")
        sys.exit(1)
    return cv2.imread(path)


def save_image(image, path):
    cv2.imwrite(path, image)


def run_pixelate(args):
    input_path, downsample, palette = args[0], int(args[1]), int(args[2])
    print(f"[Pixelate] path={input_path}, downsample={downsample}, palette={palette}")
    image = load_image(input_path)
    return pixelate(image, downsample_ratio=downsample, palette=palette)


def run_brush(args):
    input_path, vertical_path, horizontal_path = args[0], args[1], args[2]
    print(f"[Brush] input={input_path}, vertical={vertical_path}, horizontal={horizontal_path}")
    image = load_image(input_path)
    vertical_brush = load_image(vertical_path)
    horizontal_brush = load_image(horizontal_path)
    return apply_brush_strokes(image, vertical_brush, horizontal_brush)


def run_voronoi(args):
    input_path = args[0]
    image = load_image(input_path)

    num_patterns = int(args[1])
    oil_size = int(args[2])
    dyn_ratio = int(args[3])
    bilateral = bool(int(args[4]))

    print(f"[Voronoi] image={input_path}, patterns={num_patterns}, size={oil_size}, dyn={dyn_ratio}, bilateral={bilateral}")
    return apply_voronoi(
        image,
        num_voronoi_patterns=num_patterns,
        oil_paint_size=oil_size,
        oil_paint_dyn_ratio=dyn_ratio,
        use_bilateral_filter=bilateral
    )


def run_brushstyle(args):
    input_path = args[0]
    style_flag = args[1] if len(args) > 1 else "--expressionist"
    print(f"[BrushStyle] input={input_path}, style={style_flag}")
    return apply_brushstyle(input_path, output_path=None, style_flag=style_flag)


def run_slicstylize(args):
    input_path = args[0]
    num_segments = int(args[1]) if len(args) > 1 else 300
    compactness = int(args[2]) if len(args) > 2 else 50

    print(f"[SLIC Stylize] input={input_path}, segments={num_segments}, compactness={compactness}")
    image = load_image(input_path)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    result_rgb = apply_slic(image_rgb, num_segments=num_segments, compactness=compactness)
    result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)
    return result_bgr


def apply_optional_normal_mask(result_img, input_path, is_normal_flag, effect):
    if is_normal_flag and effect != "pixelate":
        reference_img = load_image(input_path)
        print("[Mask] Applying UV mask to filtered normal map...")
        result_img = apply_uv_mask_from_arrays(result_img, reference_img)
    elif is_normal_flag:
        print("[Mask] Skipping UV mask for pixelate to prevent artifacting.")
    return result_img


def main():
    if len(sys.argv) < 4:
        print("Usage: run_effect_subprocess.py <effect> <input_path> <output_path> [args...]")
        sys.exit(1)

    effect = sys.argv[1]
    input_path = sys.argv[2]
    output_path = sys.argv[3]
    args = sys.argv[4:]

    print(f"\n[Subprocess] Effect: {effect}")
    print(f"[Subprocess] Input Path: {input_path}")
    print(f"[Subprocess] Output Path: {output_path}")
    print(f"[Subprocess] Extra Args: {args}\n")

    # Detect --normal flag and remove it from args
    is_normal_flag = False
    if "--normal" in args:
        is_normal_flag = True
        args.remove("--normal")

    try:
        if effect == "pixelate":
            result = run_pixelate([input_path] + args)
        elif effect == "brush":
            result = run_brush([input_path] + args)
        elif effect == "voronoi":
            result = run_voronoi([input_path] + args)
        elif effect == "brushstyle":
            result = run_brushstyle([input_path] + args)
        elif effect == "slicstylize":
            result = run_slicstylize([input_path] + args)
        else:
            print(f"[ERROR] Unknown effect: {effect}")
            sys.exit(1)

        # Post-process if it's a normal map (skip for pixelate)
        result = apply_optional_normal_mask(result, input_path, is_normal_flag, effect)

        save_image(result, output_path)
        print(f"[Subprocess] Image saved to {output_path}")

    except Exception as e:
        print(f"[ERROR] Failed to apply effect: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
