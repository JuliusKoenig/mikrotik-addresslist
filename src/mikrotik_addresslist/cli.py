import sys
from pathlib import Path
from typing import NoReturn

import typer
from mikrotik_addresslist.generate_script import generate_script, ScriptLogLevel
from wiederverwendbar.typer import Typer
from wiederverwendbar.logger import LoggerSingleton

from mikrotik_addresslist import __name__ as __module_name__
from mikrotik_addresslist.settings import settings

# noinspection PyArgumentList
LoggerSingleton(name=__module_name__,
                ignored_loggers_like=[],
                settings=settings,
                init=True)

cli_app = Typer(settings=settings)


@cli_app.command(name="generate-script", help=f"Generate a Mikrotik RouterOS script from local file or URL.")
def generate_script_command(file: Path | None = typer.Option(None,
                                                             "-f", "--local-file",
                                                             help="Path to the local file containing the IP addresses.",
                                                             exists=True),
                            url: str | None = typer.Option(None,
                                                           "-u", "--url-file",
                                                           help="URL to the file containing the IP addresses."),
                            list_name: str = typer.Option(...,
                                                          "-n", "--list-name",
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
                            script_log_level: ScriptLogLevel = typer.Option(ScriptLogLevel.debug,
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
                                                       "-F", "--force",
                                                       help="Force overwrite the output file if it already exists."),
                            dynamic: bool = typer.Option(False,
                                                         "-d", "--dynamic",
                                                         help="Create dynamic address list entries."),
                            disabled: bool = typer.Option(False,
                                                          "-D", "--disabled",
                                                          help="Create disabled address list entries.")) -> NoReturn:

    try:
        output = generate_script(file=file,
                                 url=url,
                                 list_name=list_name,
                                 header=header,
                                 comment=comment,
                                 timeout=timeout,
                                 script_log_level=script_log_level,
                                 no_catch_errors=no_catch_errors,
                                 no_ipv4=no_ipv4,
                                 no_ipv6=no_ipv6,
                                 force=force,
                                 dynamic=dynamic,
                                 disabled=disabled)
    except Exception as e:
        cli_app.console.print(f"Error generating script: {e}", file=sys.stderr)
        sys.exit(1)
    if output_file:
        ...
    else:
        cli_app.console.print(output)
    sys.exit(0)
