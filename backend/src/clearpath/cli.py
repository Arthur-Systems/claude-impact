import typer

app = typer.Typer(help="ClearPath operator CLI.")
data = typer.Typer(help="Dataset operations (commands arrive in Task 2).")
app.add_typer(data, name="data")


@data.callback()
def data_callback() -> None:
    """Dataset operations."""


if __name__ == "__main__":
    app()
