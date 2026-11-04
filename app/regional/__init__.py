"""MITA's regional reference data: official statistics, ingested and normalized.

A batch job (``python -m app.regional.ingest``), never part of a tool call:
it fetches a small, fixed set of indicators from Eurostat, the World Bank and
the OECD for a fixed set of countries, normalizes every value with its unit,
classification, period and provenance, checks it, and upserts it into
``regional_observations`` (migration 0044). The MCP service only reads that
table (``app/mcp/queries/regional.py``), so a provider outage can never slow
or break a budget, and no user data is ever sent to a provider.

docs/chatgpt-app/personalization-2.8.md (Milestone 2).
"""
