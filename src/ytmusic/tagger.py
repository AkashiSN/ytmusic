"""Opus tagger using mutagen: Vorbis Comments + artwork + R128."""

from __future__ import annotations

import base64
import logging
import struct
from pathlib import Path

from mutagen.oggopus import OggOpus
from mutagen.flac import Picture

from .models import TrackMetadata

logger = logging.getLogger(__name__)


def _make_flac_picture(image_path: Path) -> str:
    """Create base64-encoded FLAC Picture block for METADATA_BLOCK_PICTURE."""
    suffix = image_path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"

    img_data = image_path.read_bytes()

    pic = Picture()
    pic.type = 3  # Cover (front)
    pic.mime = mime
    pic.data = img_data

    return base64.b64encode(pic.write()).decode("ascii")


def tag_opus(opus_path: Path, metadata: TrackMetadata) -> None:
    """Write Vorbis Comment tags to an Opus file.

    Tags written:
        TITLE, ARTIST (multiple), ALBUM, ALBUMARTIST, TRACKNUMBER,
        R128_TRACK_GAIN, METADATA_BLOCK_PICTURE
    """
    audio = OggOpus(opus_path)

    audio["TITLE"] = [metadata.tag_title]
    audio["ARTIST"] = metadata.artists
    audio["ALBUM"] = [metadata.album]
    audio["ALBUMARTIST"] = [metadata.album_artist]
    audio["TRACKNUMBER"] = [str(metadata.track_number)]

    if metadata.r128_track_gain is not None:
        audio["R128_TRACK_GAIN"] = [str(metadata.r128_track_gain)]

    if metadata.artwork_path and metadata.artwork_path.exists():
        pic_b64 = _make_flac_picture(metadata.artwork_path)
        audio["METADATA_BLOCK_PICTURE"] = [pic_b64]
        logger.info("Embedded artwork: %s", metadata.artwork_path.name)

    audio.save()
    logger.info("Tagged: %s", opus_path.name)
