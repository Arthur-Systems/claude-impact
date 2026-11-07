"""Operator commands: file-only validation first, explicit DB transactions second."""
from collections.abc import Iterator
from contextlib import contextmanager
import json
from pathlib import Path
from typing import Annotated
from uuid import UUID

from pydantic import SecretStr, ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import typer

from clearpath.core.config import Settings
from clearpath.db.models import DatasetRelease
from clearpath.db.session import SessionLocal
from clearpath.domain.errors import DomainError
from clearpath.ingestion.service import (
    IngestionError, bundle_counts, import_bundle, import_cities, publish_release,
)
from clearpath.ingestion.validation import BundleValidationError, ValidationIssue, validate_bundle

DEFAULT_CITIES_PATH = Path(__file__).resolve().parents[3] / "lanes/2-clear-it/data/oc-cities.json"

app = typer.Typer(help="ClearPath operator CLI.", pretty_exceptions_enable=False)
data = typer.Typer(help="Dataset validation, import and publication.")
app.add_typer(data, name="data")


@app.callback()
def main(ctx: typer.Context, debug: Annotated[bool, typer.Option("--debug")] = False) -> None:
    """Use --debug before the subcommand to expose exception tracebacks."""
    ctx.ensure_object(dict)["debug"] = debug


@data.callback()
def data_callback() -> None:
    """Dataset operations."""


@contextmanager
def _command_errors(ctx: typer.Context) -> Iterator[None]:
    try:
        yield
    except Exception as error:
        if ctx.find_root().obj.get("debug", False):
            raise
        if isinstance(error, BundleValidationError):
            for issue in error.issues:
                typer.echo(f"{issue.code}: {issue.path}", err=True)
        elif isinstance(error, DomainError):
            typer.echo(f"{error.code}: {error.details.get('path', '$')}", err=True)
        elif isinstance(error, ValidationError):
            typer.echo("configuration_invalid: $", err=True)
        elif isinstance(error, SQLAlchemyError):
            typer.echo("database_error: $", err=True)
        elif isinstance(error, (OSError, ValueError, KeyError, TypeError)):
            typer.echo("input_invalid: $", err=True)
        else:
            # Never echo SQL, connection URLs, excerpts or arbitrary exception text.
            typer.echo("internal_error: $", err=True)
        raise typer.Exit(1) from None


@contextmanager
def _transaction() -> Iterator[tuple[Session, Settings]]:
    # Data commands do not authenticate to the HTTP API and need no API key.
    # Other configuration, especially CLEARPATH_MODE, still comes from Settings.
    settings = Settings(api_key=SecretStr(""))
    with SessionLocal(settings) as session:
        try:
            yield session, settings
            session.commit()
        except Exception:
            session.rollback()
            raise


@data.command("import-cities")
def import_cities_command(
    ctx: typer.Context,
    path: Annotated[Path, typer.Option("--path")] = DEFAULT_CITIES_PATH,
) -> None:
    with _command_errors(ctx):
        with _transaction() as (session, _settings):
            count = import_cities(session, path.resolve())
        typer.echo(f"cities={count}")


@data.command("import")
def import_command(
    ctx: typer.Context,
    manifest: Annotated[Path, typer.Option("--manifest")],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    with _command_errors(ctx):
        # Resolve against the caller's CWD. Never override validation's allowed roots.
        bundle = validate_bundle(manifest.resolve())
        if dry_run:
            typer.echo("dry_run=true")
            typer.echo(f"counts={json.dumps(bundle_counts(bundle), sort_keys=True)}")
            return
        with _transaction() as (session, _settings):
            result = import_bundle(session, bundle)
        typer.echo(f"release_id={result.release_id}")
        typer.echo(f"no_op={str(result.no_op).lower()}")
        typer.echo(f"counts={json.dumps(result.counts, sort_keys=True)}")


@data.command("publish")
def publish_command(
    ctx: typer.Context,
    release: Annotated[str, typer.Option("--release")],
    reviewed: Annotated[bool, typer.Option("--reviewed")] = False,
) -> None:
    with _command_errors(ctx):
        try:
            release_id = UUID(release)
        except ValueError:
            raise BundleValidationError([ValidationIssue("schema_invalid", "release")]) from None
        already_active = False
        with _transaction() as (session, settings):
            try:
                publish_release(session, release_id, reviewed=reviewed, mode=settings.mode)
            except IngestionError as error:
                # Seed convenience only: the service remains strictly draft-only.
                # Its jurisdiction lock is still held, and it already checked review.
                current = session.get(DatasetRelease, release_id)
                if error.code != "release_not_draft" or current is None or current.status != "active":
                    raise
                expected_kind = {"public": "reviewed_public", "synthetic": "synthetic"}[settings.mode]
                if current.kind != expected_kind:
                    raise IngestionError(
                        "release_kind_mismatch", "Release kind does not match the operating mode.", {"path": "kind"},
                    ) from None
                already_active = True
        typer.echo(f"release_id={release_id}")
        typer.echo("already active" if already_active else "status=active")


if __name__ == "__main__":
    app()
