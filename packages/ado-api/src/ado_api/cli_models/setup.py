"""Pydantic-settings CLI model for the ``setup`` command."""

from pydantic import BaseModel

from ado_api.commands.setup import cmd_setup


class Setup(BaseModel):
    """Check and install az CLI prerequisites."""

    def cli_cmd(self) -> None:
        cmd_setup()
