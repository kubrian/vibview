"""Animation export: PNG sequence, GIF, and MP4 generation."""

import shutil
from collections.abc import Callable
from pathlib import Path

import imageio.v3 as iio
import numpy as np
from PIL import Image
from vispy.app.canvas import Canvas


def save_png_sequence(images: list[np.ndarray], prefix: str) -> list[Path]:
    """Save each frame as a PNG file.

    Files are named ``{prefix}_000000.png``, ``{prefix}_000001.png``, etc.
    ``prefix`` is a path prefix that may include directories, e.g.
    ``frames/anim`` produces ``frames/anim_000000.png``.
    Returns the list of created file paths.
    """
    stem = Path(prefix)
    parent = stem.parent

    paths: list[Path] = []
    digits = len(str(len(images)))
    for i, img in enumerate(images):
        path = parent / f"{stem.name}_{i:0{digits}d}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(img).save(path, format="PNG")
        paths.append(path)
    return paths


def save_gif(
    images: list[np.ndarray],
    output_path: str,
    duration: float,
    loop: int = 0,
) -> Path:
    """Combine frames into an animated GIF.

    Args:
        images: RGBA frames as (H, W, 4) uint8 arrays.
        output_path: Path for the output GIF file.
        duration: Time between frames in milliseconds (1000/fps).
        loop: Number of loops (0 = infinite).

    Returns:
        Path to the saved GIF file.
    """
    pil_images = [Image.fromarray(img) for img in images]
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pil_images[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=pil_images[1:],
        duration=duration,
        loop=loop,
    )
    return path


def save_mp4(
    images: list[np.ndarray],
    output_path: str,
    fps: int = 30,
) -> Path:
    """Combine frames into an MP4 video (H.264) via imageio/ffmpeg.

    Args:
        images: RGBA frames as (H, W, 4) uint8 arrays.
        output_path: Path for the output MP4 file.
        fps: Frames per second (default 30).

    Raises:
        RuntimeError: If ffmpeg is not found on $PATH.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "MP4 export requires ffmpeg on $PATH. Install it with:\n"
            "  conda install ffmpeg\n"
            "  apt install ffmpeg        # Debian/Ubuntu\n"
            "  brew install ffmpeg       # macOS\n"
            "  conda install ffmpeg      # Windows (via conda)"
        )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rgb_images = [img[..., :3] for img in images]
    iio.imwrite(path, rgb_images, fps=fps, codec="libx264", pixelformat="yuv420p")
    return path


def render_frames(
    canvas: Canvas,
    frame_positions: np.ndarray,
    apply_frame_fn: Callable[[int], None],
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[np.ndarray]:
    """Render each frame position to an RGBA image.

    Args:
        canvas: The scene canvas to render from.
        frame_positions: Precomputed atomic positions, shape (N, Natoms, 3).
        apply_frame_fn: Updates atom positions for a given frame index.
            Called as ``apply_frame_fn(frame_idx)``.
        progress_callback: Called as ``progress_callback(current, total)``
            after each frame.

    Returns:
        RGBA images as (H, W, 4) uint8 arrays.
    """
    images: list[np.ndarray] = []
    n_frames = len(frame_positions)
    for i in range(n_frames):
        apply_frame_fn(i)
        img = canvas.render()
        images.append(img)
        if progress_callback:
            progress_callback(i + 1, n_frames)
    return images
