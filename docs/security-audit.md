# Security and repository hygiene audit

Date: 2026-09-08. Scope: application, analytics, ingestion, database code, development
helpers, tests, configuration, documentation, and installed Python dependencies.
This directory has no Git repository/history: the secret review covers working
files, not past commits or remote repositories. No secret was detected.

## Findings and fixes

| Finding | Resolution |
|---|---|
| CSV adapters allowed pandas to interpret paths/URLs and had no input bounds; manifests could reference files outside their directory | Restrict to local UTF-8 CSV; enforce file, row, topic and aggregate limits; resolve and contain manifest paths, including symlink escapes |
| Imported topic text could become a spreadsheet formula in CSV downloads | Neutralize formula-like text and headers without changing numeric data |
| Dataset errors exposed raw exception details; cache entries were unbounded | Generic browser errors, sanitized expected-error logs, bounded caches and expiry |
| Predictable staging filename could collide with or overwrite another build's staging file | Unique temporary staging directory, atomic replacement on success, cleanup on failure |
| Ignore rules missed environment variants, Streamlit secrets, keys and some generated artifacts | Expanded ignore rules and added a credential-free `.env.example` |
| Public deployment safety was implicit | Explicit loopback binding, retained CORS/XSRF, disabled static serving and detailed browser exceptions; documented public-data-only deployment |

Import boundaries primarily protect an operator processing supplied files: there
is no browser upload endpoint. Database reads also disable DuckDB external access
as defense in depth, not as permission to open untrusted native databases.

## Checks without actionable findings

- No detected hardcoded credentials or machine-specific application paths.
- SQL uses fixed queries and allowlisted table identifiers; data is registered as
  DataFrames rather than interpolated into SQL.
- No application `eval`/`exec`, unsafe pickle loading, or shell subprocess execution.
  The optional browser test evaluates fixed JavaScript through a local debugger.
- No upload surface, scraping, or live external API integration. Authorized local
  exports are the real-data input. Dynamic HTML labels are escaped.
- No automatic `.env` loading. The CLI and database path are trusted operator inputs.
- `pip-audit` scanned all 50 installed packages: zero known vulnerabilities and
  zero skipped packages. `uv pip check` found no dependency conflicts. No package
  upgrade was justified by this scan.

## Regression coverage

Security tests exercise URL/network rejection, path containment, file type/size,
UTF-8 and row validation, manifest validation, CSV formula neutralization, blocked
database external reads, staging isolation and failed-write preservation, browser
error disclosure, real Git ignore semantics, and Streamlit configuration. The full
suite also exercises analytics and all six application workspaces. An independent
HTTP smoke check starts and stops its own server.

Verification result: **47 tests passed**, compilation passed, and the independent
Streamlit health and HTML endpoints returned HTTP 200.

## Remaining limitations

There is no authentication or multi-tenant isolation. Public instances must use
public data and HTTPS hosting. Local files and operator settings remain trusted;
these checks are not an operating-system sandbox against a hostile local user.
Unexpected framework exceptions may still appear in operator-only server logs.
Known-vulnerability scanning is point-in-time, is not a security guarantee, and does
not fully assess vendored native libraries. Version ranges can resolve differently
on later installs. Git ignore rules cannot redact historical commits, which were
unavailable here. No generated datasets or user files were deleted by this audit.

## References

- [Streamlit configuration](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)
- [DuckDB security guidance](https://duckdb.org/docs/current/operations_manual/securing_duckdb/overview)
- [DuckDB trust boundaries](https://github.com/duckdb/duckdb/blob/main/SECURITY.md)
- [CSV injection](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/21-Testing_for_CSV_Injection)
- [pip-audit scope and usage](https://github.com/pypa/pip-audit)
