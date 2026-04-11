"""Earth PBR texture → Mars color grading.

Transforms generic brown/earth ground textures into Mars regolith
color palette: reddish-brown with reduced saturation and brightness.
Parameters configurable for iterative tuning (G5).

Usage:
    python3 scripts/color_grade_mars.py
    python3 scripts/color_grade_mars.py --red-boost 1.4 --saturation 0.5
"""

import argparse
import os
import shutil

import numpy as np
from PIL import Image, ImageEnhance


def mars_color_grade(
    input_path: str,
    output_path: str,
    red_boost: float = 1.3,
    green_scale: float = 0.85,
    blue_scale: float = 0.70,
    saturation: float = 0.6,
    brightness: float = 0.8,
) -> None:
    """Apply Mars color grading to an RGB texture.

    Args:
        input_path: Source texture (PNG/JPG).
        output_path: Output Mars-graded texture.
        red_boost: Red channel multiplier (>1 = more red).
        green_scale: Green channel multiplier (<1 = less green).
        blue_scale: Blue channel multiplier (<1 = less blue).
        saturation: Color saturation (0=gray, 1=original).
        brightness: Brightness multiplier (<1 = darker).
    """
    img = Image.open(input_path).convert("RGB")
    arr = np.array(img, dtype=np.float32)

    # Channel scaling for Mars reddish-brown
    arr[:, :, 0] = np.clip(arr[:, :, 0] * red_boost, 0, 255)
    arr[:, :, 1] = np.clip(arr[:, :, 1] * green_scale, 0, 255)
    arr[:, :, 2] = np.clip(arr[:, :, 2] * blue_scale, 0, 255)

    result = Image.fromarray(arr.astype(np.uint8))
    result = ImageEnhance.Color(result).enhance(saturation)
    result = ImageEnhance.Brightness(result).enhance(brightness)
    result.save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mars color grading for PBR textures")
    parser.add_argument("--input-dir", default="assets/materials/mars_terrain")
    parser.add_argument("--output-dir", default="assets/materials/mars_terrain_graded")
    parser.add_argument("--red-boost", type=float, default=1.3)
    parser.add_argument("--green-scale", type=float, default=0.85)
    parser.add_argument("--blue-scale", type=float, default=0.70)
    parser.add_argument("--saturation", type=float, default=0.6)
    parser.add_argument("--brightness", type=float, default=0.8)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Color grade albedo only
    albedo_in = os.path.join(args.input_dir, "albedo.png")
    albedo_out = os.path.join(args.output_dir, "albedo.png")

    if not os.path.isfile(albedo_in):
        print(f"[color_grade] ERROR: {albedo_in} not found")
        return

    print(f"[color_grade] Grading albedo: {albedo_in}")
    print(
        f"  red_boost={args.red_boost}, green={args.green_scale}, "
        f"blue={args.blue_scale}, sat={args.saturation}, bright={args.brightness}"
    )
    mars_color_grade(
        albedo_in,
        albedo_out,
        red_boost=args.red_boost,
        green_scale=args.green_scale,
        blue_scale=args.blue_scale,
        saturation=args.saturation,
        brightness=args.brightness,
    )
    print(f"  → {albedo_out}")

    # Copy normal and roughness unchanged (color-independent)
    for fname in ["normal.png", "roughness.png"]:
        src = os.path.join(args.input_dir, fname)
        dst = os.path.join(args.output_dir, fname)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            print(f"  Copied {fname}")

    print("\n[color_grade] Done. Set in YAML:")
    print(f'  texture_dir: "{args.output_dir}"')


if __name__ == "__main__":
    main()
