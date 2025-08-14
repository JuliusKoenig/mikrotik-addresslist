import logging
import tempfile
from pathlib import Path

from wiederverwendbar.functions.download_file import simple_download_file

logger = logging.getLogger(__name__)


def generate_script(file: Path | None = None,
                    url: str | None = None,
                    force: bool = True) -> str:
    if file is None:
        if url is None:
            raise ValueError("Either 'file' or 'url' must be provided.")

        file = tempfile.TemporaryFile().name
        if not simple_download_file(download_url=url,
                                    local_file=file,
                                    overwrite=force):
            raise FileNotFoundError(f"Failed to download file from URL: {url}")

    # logger.debug(f"Fetching IP addresses from URL: {url}")
