"""Audio processing: ffmpeg and AtomicParsley wrappers."""

from __future__ import annotations

import json
import logging
import math
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_opus(webm_path: Path, output_path: Path, ffmpeg: str = "ffmpeg") -> None:
    """Extract Opus audio from webm container (codec copy, no re-encode).

    Args:
        webm_path: Input webm file.
        output_path: Output .opus file.
        ffmpeg: Path to ffmpeg binary.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y", "-i", str(webm_path),
        "-c:a", "copy", "-vn",
        str(output_path),
    ]
    logger.info("Extracting Opus: %s", output_path.name)
    subprocess.run(cmd, check=True, capture_output=True)


def extract_artwork(m4a_path: Path, atomicparsley: str) -> Path | None:
    """Extract artwork image from m4a using AtomicParsley.

    Returns path to extracted image file, or None if no artwork.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [atomicparsley, str(m4a_path), "--extractPixToPath", tmpdir + "/art"]
        logger.info("Extracting artwork from: %s", m4a_path.name)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("AtomicParsley failed: %s", result.stderr)
            return None

        # AtomicParsley creates files like art_artwork_1.jpg
        tmppath = Path(tmpdir)
        images = list(tmppath.glob("art*"))
        if not images:
            logger.warning("No artwork extracted from: %s", m4a_path.name)
            return None

        # Copy to a persistent location next to the m4a
        src = images[0]
        dst = m4a_path.with_suffix(src.suffix)
        if dst.suffix not in (".jpg", ".jpeg", ".png"):
            dst = m4a_path.with_suffix(".jpg")
        import shutil
        shutil.copy2(str(src), str(dst))
        return dst


def calculate_r128_gain(opus_path: Path, ffmpeg: str = "ffmpeg") -> int:
    """Calculate R128 track gain using ffmpeg loudnorm filter.

    Returns gain in Q7.8 format (1/256 dB units) for Vorbis Comment R128_TRACK_GAIN.
    """
    cmd = [
        ffmpeg, "-i", str(opus_path),
        "-af", "loudnorm=I=-23:TP=-1:LRA=11:print_format=json",
        "-f", "null", "-",
    ]
    logger.info("Calculating R128 gain: %s", opus_path.name)
    result = subprocess.run(cmd, capture_output=True, text=True)

    # ffmpeg outputs the loudnorm JSON to stderr
    stderr = result.stderr
    # Find the JSON block in stderr
    json_start = stderr.rfind("{")
    json_end = stderr.rfind("}") + 1
    if json_start < 0 or json_end <= json_start:
        raise RuntimeError(f"Failed to parse loudnorm output for {opus_path}")

    data = json.loads(stderr[json_start:json_end])
    input_i = float(data["input_i"])

    # R128 gain = target loudness (-23 LUFS) - measured loudness
    # In Q7.8 format: multiply by 256
    gain_db = -23.0 - input_i
    gain_q78 = math.floor(gain_db * 256)

    logger.info("R128 gain for %s: %.2f dB (%d Q7.8)", opus_path.name, gain_db, gain_q78)
    return gain_q78
