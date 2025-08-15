import logging
import tempfile
from datetime import datetime
from enum import Enum
from ipaddress import ip_network, IPv4Network, IPv6Network
from pathlib import Path

from mikrotik_addresslist.settings import settings
from wiederverwendbar.functions.download_file import simple_download_file

logger = logging.getLogger(__name__)


class ScriptLogLevel(str, Enum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"


def generate_script(file: Path | None,
                    url: str | None,
                    list_name: str,
                    header: list[str] | None,
                    comment: str | None,
                    timeout: int | None,
                    script_log_level: ScriptLogLevel,
                    no_catch_errors: bool,
                    no_ipv4: bool,
                    no_ipv6: bool,
                    force: bool,
                    dynamic: bool,
                    disabled: bool) -> str:
    # if file is None try to download from url
    if file is None:
        if url is None:
            raise ValueError("Either 'file' or 'url' must be provided.")
        logger.debug(f"Downloading file from URL '{url}' ...")

        file = tempfile.TemporaryFile().name
        if not simple_download_file(download_url=url,
                                    local_file=file,
                                    overwrite=force):
            raise FileNotFoundError(f"Failed to download file from URL: {url}")

    script_body = f":log {script_log_level.value} \"Updating address list '{list_name}' ...\""
    script_body += "\n/ip/firewall/address-list"

    # count lines
    with open(file, "r") as f:
        line_count = sum(1 for _ in f)

    # read the file content
    logger.debug(f"Reading file '{file}' ...")
    script_entry_count = 0
    with open(file, "r") as f:
        for no, line in enumerate(f):
            no += 1
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # parse the line as an IP network
            try:
                network = ip_network(line)
            except ValueError as e:
                logger.error(f"[red][{no}/{line_count}] {e} [/red]")
                continue

            # skip if the network is not IPv4 or IPv6 based on the flags
            if isinstance(network, IPv4Network) and no_ipv4:
                logger.debug(f"[{no}/{line_count}] Skipping IPv4 network: {network}")
                continue
            if isinstance(network, IPv6Network) and no_ipv6:
                logger.debug(f"[{no}/{line_count}] Skipping IPv6 network: {network}")
                continue

            # generate the script line
            logger.debug(f"[{no}/{line_count}] Adding network '{network}' to script ...")
            script_body += "\n"
            if not no_catch_errors:
                script_body += ":onerror in={ "
            script_body += f"add address=\"{network}\" list=\"{list_name}\""
            if comment:
                script_body += f" comment=\"{comment}\""
            if timeout:
                script_body += f" timeout=\"{timeout}s\""
            if dynamic:
                script_body += " dynamic=yes"
            else:
                script_body += " dynamic=no"
            if disabled:
                script_body += " disabled=yes"
            else:
                script_body += " disabled=no"
            script_body += f"; :log {script_log_level.value} \"[{no}/{line_count}] Added address '{network}' to list '{list_name}'\""
            if not no_catch_errors:
                script_body += f" }} do={{ :log {script_log_level.value} \"[{no}/{line_count}] Skipped adding address '{network}' to list '{list_name}' because entry already exists\"; }}  error=cnt"
            script_entry_count += 1
    script_body += f"\n:log {script_log_level.value} \"Finished updating address list '{list_name}' with {script_entry_count} entries.\""

    # generate the script header
    script_header = (f"Generated script for Mikrotik RouterOS by {settings.branding_title} v{settings.branding_version}\n"
                     f"{datetime.now().strftime(settings.datetime_format)}\n"
                     f"{list_name}\n"
                     f"{script_entry_count}")

    if header:
        for line in header:
            script_header += f"\n{line.strip()}"

    # format the script header
    script_header = "\n".join([
        script_header.splitlines()[0],
        "Date: ".ljust(max(len(line) for line in script_header.splitlines()) - len(script_header.splitlines()[1]) - 1, ".") + " " + script_header.splitlines()[1],
        "Address: List ".ljust(max(len(line) for line in script_header.splitlines()) - len(script_header.splitlines()[2]) - 1, ".") + " " + script_header.splitlines()[2],
        "Entries: ".ljust(max(len(line) for line in script_header.splitlines()) - len(script_header.splitlines()[3]) - 1, ".") + " " + script_header.splitlines()[3],
        *script_header.splitlines()[4:]
    ])

    # pad the header with dashes
    script_header = "\n".join([
        "# ╔" + "═" * (max(len(line) for line in script_header.splitlines()) + 2) + "╗",
        *[f"# ║ {script_header.splitlines()[0].strip():<{max(len(line) for line in script_header.splitlines())}} ║"],
        "# ╠" + "═" * (max(len(line) for line in script_header.splitlines()) + 2) + "╣",
        *[f"# ║ {line.strip():<{max(len(line) for line in script_header.splitlines())}} ║" for line in script_header.splitlines()[1:4]],
        "# ╠" + "═" * (max(len(line) for line in script_header.splitlines()) + 2) + "╣",
        *[f"# ║ {line.strip():<{max(len(line) for line in script_header.splitlines())}} ║" for line in script_header.splitlines()[4:]],
        "# ╚" + "═" * (max(len(line) for line in script_header.splitlines()) + 2) + "╝"
    ])

    script = f"{script_header}\n\n{script_body}"

    logger.debug("Script generated successfully.")
    return script
