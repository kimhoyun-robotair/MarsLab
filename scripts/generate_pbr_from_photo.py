"""Mars photo -> PBR texture set (albedo + normal + roughness).

Converts NASA HiRISE orthoimages or Mars surface photos into a
PBR texture set usable by MarsLab's material pipeline.
- Albedo: crop + resize + Mars color tint (grayscale -> reddish-brown)
- Normal: auto-generated via Sobel filter
- Roughness: derived from albedo luminance

Usage:
    python3 scripts/generate_pbr_from_photo.py
    python3 scripts/generate_pbr_from_photo.py --input photo.jpg --size 4096
"""

import argparse
import os

import numpy as np
from PIL import Image
from scipy import ndimage


def photo_to_albedo(
    input_path: str,
    output_path: str,
    size: int = 2048,
    mars_tint: tuple[float, float, float] = (0.72, 0.45, 0.30),
) -> None:
    """Convert a photo to Mars-tinted albedo texture.

    For grayscale HiRISE images, applies Mars regolith color tint.
    For RGB images, applies color correction.

    Args:
        input_path: Source image (JPG/PNG/JP2).
        output_path: Output albedo PNG.
        size: Output texture size (square).
        mars_tint: RGB tint for grayscale -> Mars color conversion.
    """
    Image.MAX_IMAGE_PIXELS = None  # Allow large HiRISE images
    img = Image.open(input_path)

    # Center crop to square
    w, h = img.size
    crop_size = min(w, h)
    left = (w - crop_size) // 2
    top = (h - crop_size) // 2
    img = img.crop((left, top, left + crop_size, top + crop_size))

    # Resize to target
    img = img.resize((size, size), Image.LANCZOS)

    if img.mode == "L":
        # Grayscale HiRISE -> apply Mars reddish-brown tint
        gray = np.array(img, dtype=np.float32) / 255.0
        rgb = np.stack(
            [
                gray * mars_tint[0] * 255,
                gray * mars_tint[1] * 255,
                gray * mars_tint[2] * 255,
            ],
            axis=-1,
        )
        img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    else:
        img = img.convert("RGB")

    img.save(output_path)


def albedo_to_normal(albedo_path: str, output_path: str, strength: float = 2.0) -> None:
    """Generate normal map from albedo using Sobel filter.

    Args:
        albedo_path: Input albedo texture.
        output_path: Output normal map PNG.
        strength: Normal map intensity (higher = more pronounced).
    """
    img = np.array(Image.open(albedo_path).convert("L"), dtype=np.float32)

    # Sobel gradients
    gx = ndimage.sobel(img, axis=1) * strength
    gy = ndimage.sobel(img, axis=0) * strength

    # Encode as tangent-space normal map (OpenGL convention)
    normals = np.stack(
        [
            np.clip(gx + 128, 0, 255),  # R: X gradient
            np.clip(-gy + 128, 0, 255),  # G: Y gradient (flipped for GL)
            np.full_like(gx, 255),  # B: Z (up)
        ],
        axis=-1,
    )
    Image.fromarray(normals.astype(np.uint8)).save(output_path)


def albedo_to_roughness(
    albedo_path: str,
    output_path: str,
    base_roughness: float = 0.7,
    variation: float = 0.25,
) -> None:
    """Estimate roughness from albedo luminance.

    Brighter areas = rougher (exposed regolith).
    Darker areas = smoother (compacted soil).

    Args:
        albedo_path: Input albedo texture.
        output_path: Output roughness map PNG (grayscale).
        base_roughness: Base roughness level (0-1).
        variation: How much luminance affects roughness.
    """
    img = np.array(Image.open(albedo_path).convert("L"), dtype=np.float32)
    img = img / 255.0
    roughness = np.clip(base_roughness + img * variation, 0, 1)
    Image.fromarray((roughness * 255).astype(np.uint8), mode="L").save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mars photo -> PBR texture conversion")
    parser.add_argument(
        "--input",
        default=os.path.expanduser("~/Downloads/jezero_ortho_red_c.jp2"),
        help="Source Mars photo (JPG/PNG/JP2)",
    )
    parser.add_argument(
        "--output-dir",
        default="assets/materials/mars_hirise",
        help="Output PBR texture directory",
    )
    parser.add_argument("--size", type=int, default=4096)
    parser.add_argument("--normal-strength", type=float, default=2.0)
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    albedo, normal, rough = (
        os.path.join(args.output_dir, f"{n}.png") for n in ("albedo", "normal", "roughness")
    )

    print(f"[generate_pbr] Input: {args.input}")
    print(f"[generate_pbr] Output: {args.output_dir}/ ({args.size}x{args.size})")

    print("  Generating albedo (Mars tint)...")
    photo_to_albedo(args.input, albedo, size=args.size)
    print("  Generating normal map (Sobel)...")
    albedo_to_normal(albedo, normal, strength=args.normal_strength)
    print("  Generating roughness map...")
    albedo_to_roughness(albedo, rough)

    for f in (albedo, normal, rough):
        print(f"  {os.path.basename(f)}: {os.path.getsize(f) / 1024 / 1024:.1f} MB")

    print("\n[generate_pbr] Done. Set in YAML:")
    print(f'  texture_dir: "{args.output_dir}"')


if __name__ == "__main__":
    main()
