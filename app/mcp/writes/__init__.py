"""Write paths of the MCP service: thin adapters over the canonical domain
writers (ledger, monthly plan, scheduled expenses, goals). Each function runs
on the caller's session and never commits — the tool commits once."""
