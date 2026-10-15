"""Headless backup entry point for Windows Task Scheduler.

This command never starts the web server and never creates a database. It only
backs up an existing, valid NovelTrad library when its persisted schedule is due.
"""
from __future__ import annotations

import sys

from noveltrad.main import (
    database_path,
    run_scheduled_backup_if_due,
    validate_database_file,
)


def main() -> int:
    database = database_path()
    if not database.is_file():
        print("NovelTrad: no existe una biblioteca; no se creó ninguna base vacía.", file=sys.stderr)
        return 2

    try:
        validate_database_file(database)
    except (OSError, ValueError) as exc:
        print(f"NovelTrad: la biblioteca no superó la validación; no se creó una copia: {exc}", file=sys.stderr)
        return 2

    result = run_scheduled_backup_if_due()
    status = result.get("status")
    if status == "created":
        print(f"NovelTrad: copia creada: {result.get('created')}")
        for name in result.get("removed", []):
            print(f"NovelTrad: retención; eliminada copia antigua: {name}")
        return 0
    if status == "not_due":
        print(f"NovelTrad: todavía no corresponde una copia. Próxima fecha: {result.get('next_due_at')}")
        return 0
    if status == "disabled":
        print("NovelTrad: las copias automáticas están desactivadas en la configuración.")
        return 0
    if status == "retry_wait":
        print("NovelTrad: reintento aplazado hasta " + str(result.get("retry_after_at")) + "; último error: " + str(result.get("error")))
        return 0
    print(f"NovelTrad: falló la copia programada: {result.get('error', 'error desconocido')}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
