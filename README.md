# falconsai-surgeon — the thin client (THIN-1 ②, V7.53; V7.54 ASCII-safe output, `cryptography` declared)

A wheel built from this directory by `tools/build_client.py`. It depends on `cryptography` (the verifier's ed25519 check) and nothing else; it imports nothing from the server (`app`) — proven in a clean virtual environment at every ship.

Today (V7.57, THIN-1 step 4): `surgeon upload <checkpoint> --server URL --key KEY [--open]`, `surgeon verify <package.zip>` (offline), and through the job API `surgeon replay <recipe> <checkpoint>`, `surgeon fleet <recipe> <folder>`, `surgeon report <checkpoint>`, `surgeon excise <checkpoint> <node>`, `surgeon merge <checkpoint> <name>` - the checkpoint is uploaded into a session, the server reads the recipe, the job runs, the record is printed (exit 1 if any op was refused). `compare`, `quantize`, `fold` refuse in words until the server runs them as job kinds; those run from a copy of the repository (`tools/surgeon_cli.py`).

**Install.** From the server that runs your session (no account needed for the download):

```
curl -O https://<your-surgeon-host>/download/falconsai_surgeon-<version>-py3-none-any.whl
curl -O https://<your-surgeon-host>/download/falconsai_surgeon-<version>-py3-none-any.whl.sha256
sha256sum -c falconsai_surgeon-<version>-py3-none-any.whl.sha256
pip install falconsai_surgeon-<version>-py3-none-any.whl
surgeon doctor --server https://<your-surgeon-host> --key <your key>
```

PyPI (`pip install falconsai-surgeon`) follows once the project is published; this repository holds the publishing workflow (`.github/workflows/publish-client.yml`, Trusted Publishing — no token). Source of truth for the code is the Model Surgeon tree's `client/`; this repo mirrors it at each release and the wheel it builds is byte-identical (both pin `SOURCE_DATE_EPOCH`).

**Licensing.** The client is proprietary; `surgeon/verify.py` — the offline package verifier — is Apache-2.0 and free for everyone, forever. See `LICENSE.txt`.

## Troubleshooting (V7.58)

Run `surgeon doctor --server URL --key KEY` first: it prints the server's health and version, whether the key is recognised and its tier, whether the client version matches the server, and the next action.

| You see | Meaning | Next |
|---|---|---|
| `could not reach <server>` | nothing answered at that address | is the server up, is the address the one the proxy serves? `surgeon doctor --server URL` |
| `HTTP 401 ... No session` | the session expired (30 idle minutes, a restart) or the cache is stale | run the command again - a new session is minted |
| `HTTP 403 ...` | the key was refused for this command | `surgeon doctor` shows the tier; surgery and jobs need Practitioner; verification needs no key |
| `HTTP 413 ...` | the file is over the tier's ceiling (the message states it) | a smaller checkpoint, `.safetensors` for the larger ceiling, or Practitioner |
| `HTTP 429 ...` | rate limited | wait a minute and retry |
| `REFUSED <file>: ... refused: <op> <node>: ...` | the server applied the job and refused an op (name not on the table, already excised, donor missing) | read the server's words; check the name with `surgeon report` or the Nodes & Layers panel |
| `<path>: no such file` | the checkpoint or recipe path is wrong | check the path; `surgeon --help` shows the argument order |
| `Traceback` | a client defect | report it with `--verbose` output |

Exit codes: `0` clean - `1` the server refused one or more ops (the job ran) - `2` the client refused (its message says why).

A dropped upload resumes: the session is kept per server under `~/.falconsai-surgeon/`; rerun the same command and the server says which chunks it already holds (`--verbose` shows `resuming: ...`). `--no-session-cache` turns that off.
