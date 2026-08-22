"""Structural fingerprint of a PostgreSQL schema, for comparing sources of truth.

Production ran for months with alembic_version reading 0035 while several of
0022's constraints were absent, and nothing detected it. The reason is that
three different things can each claim to be "the schema":

    1. the SQLAlchemy models      (what create_all builds)
    2. the migration chain        (what alembic upgrade head builds)
    3. the live database          (what actually exists)

They are not automatically equal, and in this project all three differ. This
module reduces any of them to the same comparable structure so a test - or a
human - can say exactly where.

Deliberately compares only what the ORM can also express, so model-built and
migration-built schemas are judged on equal terms: tables, columns, types,
nullability, primary keys, foreign keys with ON DELETE, unique constraints and
indexes. Server defaults are normalised because PostgreSQL echoes them back in
a canonicalised form that never matches the literal a migration wrote.
"""

from __future__ import annotations

import re

import sqlalchemy as sa

# Tables that are bookkeeping rather than application schema.
IGNORED_TABLES = {"alembic_version"}


def _norm_type(type_) -> str:
    """Compare types by their PostgreSQL spelling, not the Python class.

    VARCHAR and VARCHAR(255) are genuinely different; String and VARCHAR are
    the same thing said two ways.
    """
    text = str(type_).upper()
    text = text.replace("CHARACTER VARYING", "VARCHAR")
    text = text.replace("TIMESTAMP WITH TIME ZONE", "TIMESTAMPTZ")
    text = text.replace("TIMESTAMP WITHOUT TIME ZONE", "TIMESTAMP")
    text = text.replace("DOUBLE PRECISION", "FLOAT")
    # SQLAlchemy spells it DATETIME; PostgreSQL reports TIMESTAMP. Same type.
    text = text.replace("DATETIME", "TIMESTAMP")
    text = re.sub(r"\bSERIAL\b", "INTEGER", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _norm_default(default) -> str | None:
    """Normalise a server default to something comparable across sources."""
    if default is None:
        return None
    text = str(getattr(default, "arg", default))
    text = text.strip().strip("'\"")
    # postgres re-renders defaults with casts and quoting of its own
    text = re.sub(r"::[a-zA-Z ]+(\[\])?", "", text)
    text = text.strip("'\"").lower()
    if text in {"now()", "current_timestamp", "clock_timestamp()"}:
        return "now()"
    if text in {"true", "false"}:
        return text
    if text in {"gen_random_uuid()", "uuid_generate_v4()"}:
        return "uuid()"
    # SERIAL/BIGSERIAL: the sequence default is materialised by the database
    # and never present in the metadata. It carries no comparable information.
    if text.startswith("nextval("):
        return None
    return text


def fingerprint_inspector(insp: sa.Inspector) -> dict:
    """Fingerprint a live database through a SQLAlchemy Inspector."""
    out = {}
    for table in sorted(insp.get_table_names()):
        if table in IGNORED_TABLES:
            continue
        cols = {}
        for c in insp.get_columns(table):
            cols[c["name"]] = {
                "type": _norm_type(c["type"]),
                "nullable": bool(c["nullable"]),
                "default": _norm_default(c.get("default")),
            }
        pk = tuple(
            sorted(insp.get_pk_constraint(table).get("constrained_columns") or [])
        )
        fks = set()
        for fk in insp.get_foreign_keys(table):
            fks.add(
                (
                    tuple(sorted(fk["constrained_columns"])),
                    fk["referred_table"],
                    tuple(sorted(fk["referred_columns"])),
                    (fk.get("options") or {}).get("ondelete", "NO ACTION").upper()
                    or "NO ACTION",
                )
            )
        uniques = {
            tuple(sorted(u["column_names"] or []))
            for u in insp.get_unique_constraints(table)
        }
        indexes = set()
        for i in insp.get_indexes(table):
            cols_t = tuple(sorted(i["column_names"] or []))
            if i.get("unique"):
                # PostgreSQL implements a UNIQUE constraint AS a unique index;
                # counting it in both sets would report a phantom difference.
                uniques.add(cols_t)
            else:
                indexes.add((cols_t, False))
        out[table] = {
            "columns": cols,
            "pk": pk,
            "fks": fks,
            "uniques": uniques,
            "indexes": indexes,
        }
    return out


def fingerprint_metadata(metadata: sa.MetaData) -> dict:
    """Fingerprint the ORM models without needing a database."""
    out = {}
    for name, table in sorted(metadata.tables.items()):
        if name in IGNORED_TABLES:
            continue
        cols = {}
        for c in table.columns:
            cols[c.name] = {
                "type": _norm_type(c.type),
                "nullable": bool(c.nullable),
                "default": _norm_default(c.server_default),
            }
        pk = tuple(sorted(c.name for c in table.primary_key.columns))
        fks = set()
        for c in table.columns:
            for fk in c.foreign_keys:
                fks.add(
                    (
                        (c.name,),
                        fk.column.table.name,
                        (fk.column.name,),
                        (fk.ondelete or "NO ACTION").upper(),
                    )
                )
        uniques = set()
        indexes = set()
        for con in table.constraints:
            if isinstance(con, sa.UniqueConstraint):
                uniques.add(tuple(sorted(c.name for c in con.columns)))
        for idx in table.indexes:
            cols_t = tuple(sorted(c.name for c in idx.columns))
            if idx.unique:
                uniques.add(cols_t)
            else:
                indexes.add((cols_t, False))
        # a single-column unique=True renders as a unique constraint in PG
        for c in table.columns:
            if c.unique:
                uniques.add((c.name,))
        out[name] = {
            "columns": cols,
            "pk": pk,
            "fks": fks,
            "uniques": uniques,
            "indexes": indexes,
        }
    return out


def diff(left: dict, right: dict, left_name="left", right_name="right") -> list[str]:
    """Human-readable differences. Empty list means structurally equivalent."""
    problems = []
    lt, rt = set(left), set(right)
    for t in sorted(lt - rt):
        problems.append(f"table {t}: in {left_name} only")
    for t in sorted(rt - lt):
        problems.append(f"table {t}: in {right_name} only")

    for t in sorted(lt & rt):
        lc, rc = left[t]["columns"], right[t]["columns"]
        for col in sorted(set(lc) - set(rc)):
            problems.append(f"{t}.{col}: column in {left_name} only")
        for col in sorted(set(rc) - set(lc)):
            problems.append(f"{t}.{col}: column in {right_name} only")
        for col in sorted(set(lc) & set(rc)):
            for attr in ("type", "nullable", "default"):
                if lc[col][attr] != rc[col][attr]:
                    problems.append(
                        f"{t}.{col}.{attr}: {left_name}={lc[col][attr]!r} "
                        f"{right_name}={rc[col][attr]!r}"
                    )
        if left[t]["pk"] != right[t]["pk"]:
            problems.append(
                f"{t}: PK {left_name}={left[t]['pk']} {right_name}={right[t]['pk']}"
            )
        for key in ("fks", "uniques", "indexes"):
            only_l = left[t][key] - right[t][key]
            only_r = right[t][key] - left[t][key]
            for item in sorted(map(str, only_l)):
                problems.append(f"{t}: {key[:-1]} in {left_name} only: {item}")
            for item in sorted(map(str, only_r)):
                problems.append(f"{t}: {key[:-1]} in {right_name} only: {item}")
    return problems
