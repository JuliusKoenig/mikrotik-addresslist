import sys
from typing import NoReturn
import tempfile
from datetime import datetime
from ipaddress import (ip_network,
                       IPv4Network,
                       IPv6Network)
from pathlib import Path
import os
from enum import Enum

import typer
from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import (BaseModel,
                      Field,
                      FileUrl,
                      HttpUrl,
                      ValidationError)
from pydantic_settings import BaseSettings
from wiederverwendbar.functions.download_file import simple_download_file
from wiederverwendbar.fastapi import (FastAPI,
                                      FastAPISettings)
from wiederverwendbar.typer import (Typer,
                                    TyperSettings)
from wiederverwendbar.logger import (LoggerSingleton,
                                     LoggerSettings)
from wiederverwendbar.pydantic import Version
from wiederverwendbar.uvicorn import (UvicornServer,
                                      UvicornServerSettings)

from mikrotik_addresslist import (__name__ as __module_name__,
                                  __title__,
                                  __description__,
                                  __author__,
                                  __author_email__,
                                  __version__,
                                  __license__,
                                  __license_url__,
                                  __terms_of_service__,
                                  __env_prefix__)

if f"{__env_prefix__}LOG_LEVEL" not in os.environ:
    os.environ[f"{__env_prefix__}LOG_LEVEL"] = "DEBUG"  # ToDo #"INFO"
os.environ[f"{__env_prefix__}SCRIPTS"] = """{
    "test": {
        "source": "file:///example_blocklist.txt",
        "name": "hg_test"
    }
}""" # ToDo: remove this line after testing


class Settings(BaseSettings, LoggerSettings, TyperSettings, FastAPISettings, UvicornServerSettings):
    model_config = {
        "env_prefix": __env_prefix__,
        "case_sensitive": False
    }

    datetime_format: str = Field(default="%d.%m.%Y - %H:%M:%S",
                                 title="Date and Time Format",
                                 description="Format for date and time in the generated script.")
    file_encoding: str = Field(default="utf-8",
                               title="File Encoding",
                               description="Encoding used for reading and writing files.")

    class Script(BaseModel):
        source: FileUrl | HttpUrl = Field(default=...,
                                          title="Source",
                                          description="Source of the IP addresses, either a local file or a URL.")
        name: str = Field(default=...,
                          title="Address List Name",
                          description="Name of the address list to be created in RouterOS.")
        header: list[str] | None = Field(default=None,
                                         title="Script Header",
                                         description="Header comment for the generated script.")
        comment: str | None = Field(default=None,
                                    title="Comment",
                                    description="Comment for the address list entries.")
        timeout: int | None = Field(default=None,
                                    title="Timeout",
                                    description="Timeout for dynamic address list entries in seconds.")

        class LogLevel(str, Enum):
            debug = "debug"
            info = "info"
            warning = "warning"
            error = "error"

        log_level: LogLevel = Field(default=LogLevel.debug,
                                    title="Script Log Level",
                                    description="Log level for the generated script.")
        no_catch_errors: bool = Field(default=False,
                                      title="No Catch Errors",
                                      description="Disable error catching in the generated script.")
        no_ipv4: bool = Field(default=False,
                              title="No IPv4",
                              description="Disable IPv4 addresses in the generated script.")
        no_ipv6: bool = Field(default=False,
                              title="No IPv6",
                              description="Disable IPv6 addresses in the generated script.")
        dynamic: bool = Field(default=False,
                              title="Dynamic",
                              description="Create dynamic address list entries.")
        disabled: bool = Field(default=False,
                               title="Disabled",
                               description="Create disabled address list entries.")

    scripts: dict[str, Script] = Field(default_factory=dict,
                                       title="Scripts",
                                       description="Configuration for the scripts to be generated.")


try:
    settings = Settings(branding_title=__title__,
                        branding_description=__description__,
                        branding_version=Version(__version__),
                        branding_author=__author__,
                        branding_author_email=__author_email__,
                        branding_license=__license__,
                        branding_license_url=__license_url__,
                        branding_terms_of_service=__terms_of_service__)
except ValidationError as _e:
    print(_e, file=sys.stderr)
    sys.exit(1)

# noinspection PyArgumentList
logger = LoggerSingleton(name=__module_name__,
                         ignored_loggers_like=[],
                         settings=settings,
                         init=True)


def get_script(script_name: str, server: bool) -> NoReturn | Settings.Script:
    if script_name not in settings.scripts:
        msg = f"Script configuration with name '{script_name}' not found in settings."
        if server:
            raise HTTPException(status_code=404, detail=msg)
        else:
            raise FileNotFoundError(msg)
    return settings.scripts[script_name]


def generate_script(script: Settings.Script) -> str:
    # if file is None try to download from url
    if isinstance(script.source, HttpUrl):
        logger.debug(f"Downloading file from URL '{script.source}' ...")

        source = Path(tempfile.TemporaryFile().name)
        if not simple_download_file(download_url=str(script.source),
                                    local_file=source):
            raise FileNotFoundError(f"Failed to download file from URL: {script.source}")
    elif isinstance(script.source, FileUrl):
        source = Path(script.source.path[1:])
    if not source.is_file():
        raise FileNotFoundError(f"Source file '{source}' does not exist or is not a file.")

    script_body = f":log {script.log_level.value} \"Updating address list '{script.name}' ...\""
    script_body += "\n/ip/firewall/address-list"

    # count lines
    with open(source, "r") as f:
        line_count = sum(1 for _ in f)

    # read the file content
    logger.debug(f"Reading source file '{source}' ...")
    script_entry_count = 0
    with open(source, "r") as f:
        for no, line in enumerate(f):
            no += 1
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # parse the line as an IP network
            try:
                network = ip_network(line, strict=False)
            except ValueError as e:
                logger.error(f"[red][{no}/{line_count}] {e} [/red]")
                continue

            # skip if the network is not IPv4 or IPv6 based on the flags
            if isinstance(network, IPv4Network) and script.no_ipv4:
                logger.debug(f"[{no}/{line_count}] Skipping IPv4 network: {network}")
                continue
            if isinstance(network, IPv6Network) and script.no_ipv6:
                logger.debug(f"[{no}/{line_count}] Skipping IPv6 network: {network}")
                continue

            # generate the script line
            logger.debug(f"[{no}/{line_count}] Adding network '{network}' to script ...")
            script_body += "\n"
            if not script.no_catch_errors:
                script_body += ":onerror in={ "
            script_body += f"add address=\"{network}\" list=\"{script.name}\""
            if script.comment:
                script_body += f" comment=\"{script.comment}\""
            if script.timeout:
                script_body += f" timeout=\"{script.timeout}s\""
            if script.dynamic:
                script_body += " dynamic=yes"
            else:
                script_body += " dynamic=no"
            if script.disabled:
                script_body += " disabled=yes"
            else:
                script_body += " disabled=no"
            script_body += f"; :log {script.log_level.value} \"[{no}/{line_count}] Added address '{network}' to list '{script.name}'\""
            if not script.no_catch_errors:
                script_body += f" }} do={{ :log {script.log_level.value} \"[{no}/{line_count}] Skipped adding address '{network}' to list '{script.name}' because entry already exists\"; }}  error=cnt"
            script_entry_count += 1
    script_body += f"\n:log {script.log_level.value} \"Finished updating address list '{script.name}' with {script_entry_count} entries.\""

    # generate the script header
    script_header = (f"Generated script for Mikrotik RouterOS by {settings.branding_title} v{settings.branding_version}\n"
                     f"{datetime.now().strftime(settings.datetime_format)}\n"
                     f"{script.name}\n"
                     f"{script.source}\n"
                     f"{script_entry_count}")

    if script.header:
        for line in script.header:
            script_header += f"\n{line.strip()}"

    # format the script header
    script_header = "\n".join([
        script_header.splitlines()[0],
        "Date: ".ljust(max(len(line) for line in script_header.splitlines()) - len(script_header.splitlines()[1]) - 1, ".") + " " + script_header.splitlines()[1],
        "Address: List ".ljust(max(len(line) for line in script_header.splitlines()) - len(script_header.splitlines()[2]) - 1, ".") + " " + script_header.splitlines()[2],
        "Source: ".ljust(max(len(line) for line in script_header.splitlines()) - len(script_header.splitlines()[3]) - 1, ".") + " " + script_header.splitlines()[3],
        "Entries: ".ljust(max(len(line) for line in script_header.splitlines()) - len(script_header.splitlines()[4]) - 1, ".") + " " + script_header.splitlines()[4],
        *script_header.splitlines()[4:]
    ])

    # pad the header with dashes
    script_header = "\n".join([
        "# ╔" + "═" * (max(len(line) for line in script_header.splitlines()) + 2) + "╗",
        *[f"# ║ {script_header.splitlines()[0].strip():<{max(len(line) for line in script_header.splitlines())}} ║"],
        "# ╠" + "═" * (max(len(line) for line in script_header.splitlines()) + 2) + "╣",
        *[f"# ║ {line.strip():<{max(len(line) for line in script_header.splitlines())}} ║" for line in script_header.splitlines()[1:5]],
        "# ╠" + "═" * (max(len(line) for line in script_header.splitlines()) + 2) + "╣",
        *[f"# ║ {line.strip():<{max(len(line) for line in script_header.splitlines())}} ║" for line in script_header.splitlines()[5:]],
        "# ╚" + "═" * (max(len(line) for line in script_header.splitlines()) + 2) + "╝"
    ])

    script = f"{script_header}\n\n{script_body}"

    logger.debug("Script generated successfully.")
    return script


cli_app = Typer(settings=settings)


@cli_app.command(name="generate-script", help=f"Generate a Mikrotik RouterOS script from local file or URL.")
def generate_script_command(script_name: str = typer.Argument(None,
                                                              help="Name of script configuration in settings."),
                            source: str = typer.Option(None,
                                                       "-s", "--source",
                                                       help="Source of the IP addresses, either a local file or a URL"),
                            name: str = typer.Option(None,
                                                     "-n", "--name",
                                                     help="Name of the address list to be created in RouterOS."),
                            output_file: Path = typer.Option(None,
                                                             "-o", "--output-file",
                                                             help="Path to the output file where the generated script will be saved."),
                            header: list[str] | None = typer.Option(None,
                                                                    "-h", "--header",
                                                                    help="Header comment for the generated script."),
                            comment: str | None = typer.Option(None,
                                                               "-c", "--comment",
                                                               help="Comment for the address list entries."),
                            timeout: int | None = typer.Option(None,
                                                               "-t", "--timeout",
                                                               help="Timeout for dynamic address list entries in seconds."),
                            log_level: Settings.Script.LogLevel = typer.Option(Settings.Script.LogLevel.debug,
                                                                               "-l", "--log-level",
                                                                               help="Log level for the generated script."),
                            no_catch_errors: bool = typer.Option(False,
                                                                 "-nce", "--no-catch-errors",
                                                                 help="Disable error catching in the generated script."),
                            no_ipv4: bool = typer.Option(False,
                                                         "-n4", "--no-ipv4",
                                                         help="Disable IPv4 addresses in the generated script."),
                            no_ipv6: bool = typer.Option(False,
                                                         "-n6", "--no-ipv6",
                                                         help="Disable IPv6 addresses in the generated script."),
                            force: bool = typer.Option(False,
                                                       "-f", "--force",
                                                       help="Force overwrite the output file if it already exists."),
                            dynamic: bool = typer.Option(False,
                                                         "-d", "--dynamic",
                                                         help="Create dynamic address list entries."),
                            disabled: bool = typer.Option(False,
                                                          "-D", "--disabled",
                                                          help="Create disabled address list entries.")) -> NoReturn:

    if script_name:
        try:
            script = get_script(script_name=script_name, server=False)
        except FileNotFoundError as e:
            cli_app.console.print(f"{e}", file=sys.stderr)
            sys.exit(1)
    else:
        if source is None:
            cli_app.console.print("Source URL must be provided when script name is not specified.", file=sys.stderr)
            sys.exit(1)
        # noinspection HttpUrlsUsage
        if source.startswith("http://") or source.startswith("https://"):
            source = HttpUrl(source)
        else:
            source = FileUrl(Path(source).absolute().as_uri())
        if name is None:
            cli_app.console.print("Name must be provided when script name is not specified.", file=sys.stderr)
            sys.exit(1)
        script = Settings.Script(source=source,
                                 name=name,
                                 header=header,
                                 comment=comment,
                                 timeout=timeout,
                                 log_level=log_level,
                                 no_catch_errors=no_catch_errors,
                                 no_ipv4=no_ipv4,
                                 no_ipv6=no_ipv6,
                                 dynamic=dynamic,
                                 disabled=disabled)


    try:
        output = generate_script(script=script)
    except Exception as e:
        cli_app.console.print(f"Error generating script: {e}", file=sys.stderr)
        sys.exit(1)
    if output_file:
        if output_file.is_file():
            if not force:
                cli_app.console.print(f"Output file '{output_file}' already exists. Use --force to overwrite.", file=sys.stderr)
                sys.exit(1)
        output_file.unlink()
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding=settings.file_encoding) as f:
            f.write(output)
        cli_app.console.print(f"Script saved to '{output_file}'.")
    else:
        cli_app.console.print(output)
    sys.exit(0)


@cli_app.command(name="server", help=f"Start the server.")
def server_command() -> NoReturn:
    api_app = FastAPI(settings=settings)

    @api_app.get("/{script_name}", tags=["Script"])
    def get_script_content(script_name: str) -> FileResponse:
        script = get_script(script_name, server=True)
        output = generate_script(script)
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding=settings.file_encoding) as f:
            f.write(output)
        return FileResponse(f.name, filename=f"{script_name}.rsc", media_type="text/plain")

    @api_app.get("/{script_name}/settings", tags=["Script"])
    def get_script_settings(script_name: str) -> Settings.Script:
        return get_script(script_name, server=True)

    @api_app.get("/{script_name}/setup", tags=["Script"])
    def get_script_settings(script_name: str) -> Settings.Script:
        return get_script(script_name, server=True)

    UvicornServer(app=api_app, settings=settings)
    sys.exit(0)


if __name__ == "__main__":
    cli_app()
