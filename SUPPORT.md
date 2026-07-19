# Support

## Start Here

1. Read the [README](README.md) for setup and project boundaries.
2. Use the [documentation index](docs/README.md) to find architecture and demo material.
3. Run the health endpoint at <http://127.0.0.1:8000/api/health>.
4. Run the test suite before reporting a reproducible defect.

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
```

## Questions and Ideas

Use GitHub Discussions when enabled. Otherwise, open an issue with the **Question** or **Feature request** form. Describe the outcome you need, not only a proposed implementation.

## Bug Reports

Use the bug-report form and include:

- Operating system and Python version
- Local or Docker mode
- Exact command used to start Aura
- Steps to reproduce from a reset state
- Expected and observed behavior
- Relevant status codes and sanitized logs
- Whether the full test suite passes

Do not include secrets or private incident data.

## Common Checks

### Port 8000 is already in use

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen
```

Stop only the process that belongs to this workspace, or start Aura on another port.

### API is unavailable

Confirm the virtual environment dependencies are installed and run:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

### Docker services are degraded

Run `docker compose ps` and inspect the service health checks. Aura reports optional adapters as connected, fallback, or degraded; it does not silently restore a failed adapter.

## Security Reports

Use the private process in [SECURITY.md](SECURITY.md). Do not publish a vulnerability as a support request.
