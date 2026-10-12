"""Entry point for the `kuanflow` command."""

import typer

from kuanflow_cli import __version__

app = typer.Typer(help="Kuanflow - AI-assisted SDLC workflows.", no_args_is_help=True)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"kuanflow {__version__}")
        raise typer.Exit(0)


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Kuanflow - AI-assisted SDLC workflows."""
