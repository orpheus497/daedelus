# src/daedelus/plugins/hello_world/main.py
import click

from daedelus.core.plugin_interface import DaedalusAPI, DaedalusPlugin


# The command we want to add
@click.command()
@click.argument("name", default="world")
def hello(name):
    """A simple command that prints a greeting."""
    click.echo(f"Hello, {name}! This command is from a plugin.")


# The main plugin class
class HelloWorldPlugin(DaedalusPlugin):
    def __init__(self, api: DaedalusAPI):
        super().__init__(api)
        self.logger.info("Hello World plugin initialized.")

    def load(self):
        """Load the plugin and register its components."""
        self.logger.info("Registering 'hello' command.")
        self.api.register_cli_command(hello)

    def unload(self):
        """Unload the plugin."""
        self.logger.info("Hello World plugin is shutting down.")
