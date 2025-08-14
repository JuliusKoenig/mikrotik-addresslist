import sys
from pathlib import Path
from typing import NoReturn

import typer
from mikrotik_addresslist.generate_script import generate_script
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
                                                      "-l", "--local-file",
                                                      help="Path to the local file containing the IP addresses.",
                                                      exists=True),
                            url: str | None = typer.Option(None,
                                                    "-u", "--url-file",
                                                    help="URL to the file containing the IP addresses."),
                            output_file: Path = typer.Option(None,
                                                             "-o", "--output-file",
                                                             help="Path to the output file where the generated script will be saved."),
                            force: bool = typer.Option(False,
                                                       "-f", "--force",
                                                       help="Force overwrite the output file if it already exists.")) -> NoReturn:
    cli_app.console.print(f"Generating script from {'local file' if file else 'URL'} '{file or url}' ...")

    try:
        result = generate_script(file=file, url=url, force=force)
    except Exception as e:
        cli_app.console.print(f"[red]Error generating script: {e}[/red]")
        sys.exit(1)

    cli_app.console.print(f"Script generated successfully:\n{result}")
    sys.exit(0)
