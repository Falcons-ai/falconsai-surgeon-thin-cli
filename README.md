# falconsai-surgeon — the command line for FALCONS.AI Model Surgeon

**Model Surgeon** — https://surgeon.falcons.ai — is a visual operating theatre for neural networks: load a real checkpoint in the browser, see its anatomy in 3-D, operate on it with reversible tools (excise, merge, quantize, fold), measure every consequence, and export a package whose signed record anyone can verify.

`falconsai-surgeon` is the thin client for that server. It holds no server code and depends on one library (`cryptography`, for the verifier's ed25519 check). Version 7.70.

```
pip install falconsai-surgeon
surgeon doctor --server https://surgeon.falcons.ai --key <your key>
```

## What you can do from the terminal

- **Hand a checkpoint to the browser** — `surgeon upload <checkpoint> --server URL --key KEY --open` uploads it into a session and opens the theatre on it. Large uploads are chunked and resume if the connection drops.
- **Verify any Surgeon package, offline, with no account** — `surgeon verify <package.zip>` checks the package's signed lineage and prints the verdict. This verifier is Apache-2.0 and free for everyone, forever.
- **Replay a recipe** — `surgeon replay <recipe> <checkpoint>` applies a surgery you finalized in the browser (`ops.yaml`) to a new checkpoint, through the same edit door the browser uses; the server's record is printed, and `--open` hands you the edited table in the browser.
- **Run a fleet** — `surgeon fleet <recipe> <folder>` applies one recipe to every checkpoint in a folder, one job each: the server's record per checkpoint and a closing `N of M checkpoint(s) clean` line; exit 1 if any op was refused.
- **Report, excise, merge headlessly** — `surgeon report <checkpoint>` prints what the server read; `surgeon excise <checkpoint> <node>` and `surgeon merge <checkpoint> <name> [--method lerp|slerp --alpha 0.5]` run as one-op jobs (the merge donor must already be on the table).
- **Know where you stand** — `surgeon doctor` prints the server's health and version, whether your key is recognised and its tier, whether the client version matches the server, and the next action.

Every command that runs a job returns the server's own words; exit codes are `0` clean · `1` the server refused one or more ops (the job ran) · `2` the client refused (its message says why). Surgery and jobs need a Practitioner key; `verify` needs none. Tiers and limits: https://surgeon.falcons.ai/pricing

**Not yet from the client:** `compare`, `quantize` and `fold` refuse in words until the server runs them as job kinds; today those run from a copy of the Model Surgeon repository (`tools/surgeon_cli.py`).

## Install

From PyPI (the ordinary path):

```
pip install falconsai-surgeon
```

Air-gapped, or to match exactly the wheel your server serves — the server that runs your session publishes its own wheel and its sha256, no account needed:

```
curl -O https://<your-surgeon-host>/download/falconsai_surgeon-<version>-py3-none-any.whl
curl -O https://<your-surgeon-host>/download/falconsai_surgeon-<version>-py3-none-any.whl.sha256
sha256sum -c falconsai_surgeon-<version>-py3-none-any.whl.sha256
pip install falconsai_surgeon-<version>-py3-none-any.whl
```

Python 3.9 or newer, any OS. Output is ASCII-safe on piped Windows consoles.

## Troubleshooting

Run `surgeon doctor --server URL --key KEY` first.

| You see | Meaning | Next |
| --- | --- | --- |
| `could not reach <server>` | nothing answered at that address | is the server up, is the address the one the proxy serves? `surgeon doctor --server URL` |
| `HTTP 401 ... No session` | the session expired (30 idle minutes, a restart) or the cache is stale | run the command again - a new session is minted |
| `HTTP 403 ...` | the key was refused for this command | `surgeon doctor` shows the tier; surgery and jobs need Practitioner; verification needs no key |
| `HTTP 413 ...` | the file is over the tier's ceiling (the message states it) | a smaller checkpoint, `.safetensors` for the larger ceiling, or Practitioner |
| `HTTP 429 ...` | rate limited | wait a minute and retry |
| `REFUSED <file>: ... refused: <op> <node>: ...` | the server applied the job and refused an op (name not on the table, already excised, donor missing) | read the server's words; check the name with `surgeon report` or the Nodes & Layers panel |
| `<path>: no such file` | the checkpoint or recipe path is wrong | check the path; `surgeon --help` shows the argument order |
| `Traceback` | a client defect | report it at https://github.com/Falcons-ai/falconsai-surgeon-thin-cli/issues with `--verbose` output |

A dropped upload resumes: the session is kept per server under `~/.falconsai-surgeon/`; rerun the same command and the server says which chunks it already holds (`--verbose` shows `resuming: ...`). `--no-session-cache` turns that off.

## How this package is built

The source of truth is the Model Surgeon tree's `client/`; the repository at https://github.com/Falcons-ai/falconsai-surgeon-thin-cli mirrors it at each release and publishes through Trusted Publishing (no stored token). The wheel is built with a pinned build backend and a pinned `SOURCE_DATE_EPOCH` on both sides, and the server prints the sha256 of the wheel it serves at `/download/`; compare it with the hash PyPI shows for the same version.

## Licensing

The client is proprietary; `surgeon/verify.py` — the offline package verifier — is Apache-2.0 and free for everyone, forever. See `LICENSE.txt`.
