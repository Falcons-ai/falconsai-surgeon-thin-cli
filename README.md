# falconsai-surgeon — the command line and Python client for FALCONS.AI Model Surgeon

**Model Surgeon** — https://surgeon.falcons.ai — is a visual operating theatre for neural networks: load a real checkpoint in the browser, see its anatomy in 3-D, operate on it with reversible tools (excise, graft, merge, quantize, fold), measure every consequence, and export a package whose signed record anyone can verify.

`falconsai-surgeon` is the thin client for that server. It holds no server code, is standard library throughout, and depends on one package (`cryptography`, for the verifier's ed25519 check). Version 7.116.

```
pip install falconsai-surgeon
surgeon doctor --server https://surgeon.falcons.ai --key <your account key>
```

Your account key is the one the theatre keeps under **◈ ACCOUNT** (the key box has a ⧉ copy icon). Every command that talks to the server takes it as `--key`; the client reads no environment variable for it. Surgery and jobs need a **Practitioner** key; `upload`, `report` and `doctor` run on any recognised key; `verify` needs no key and no server. Tiers and limits: https://surgeon.falcons.ai/pricing

## The commands

| command | what it does | needs |
| --- | --- | --- |
| `surgeon doctor --server URL [--key KEY]` | reads the server's health and version, whether the key is recognised and its tier, whether this client's version matches the server's, whether a model is on the table, and prints the next action | — |
| `surgeon upload <checkpoint> --server URL --key KEY [--open]` | loads a checkpoint into a server session through the browser's own chunk protocol (resumable); `--open` mints the 60-second single-use hand-off link `URL/#claim=<token>` and opens the theatre on it | a key (`--open`: Practitioner) |
| `surgeon report <checkpoint> --server URL --key KEY` | uploads the checkpoint and prints what the server read: the architecture label and the vitals (`params` · `modules` · `tensors` · `size_bytes` · `format`) | a key |
| `surgeon verify <package.zip> [--key K]` | verifies a Surgeon package offline: every file's SHA-256 against the signed digest, the ed25519 signature, the lineage chain; prints `VERDICT: VERIFIED` or the failing file; exit `0` VERIFIED · `1` TAMPERED/INCOMPLETE · `2` not a Surgeon package. Apache-2.0, free for everyone, forever. To also learn **who** signed it, run the module form: `python -m surgeon.verify <package.zip> --bind` fetches the publisher's own fingerprint list and prints `bound`, `retired (date)` or `unbound` | nothing |
| `surgeon replay <recipe> <checkpoint> --server URL --key KEY [--open]` | the server reads the recipe (`ops.yaml` or `.json`, the one ⧉ Export Recipe wrote) against its contract, the checkpoint is uploaded, and the ops run as one job through the same edit door the browser uses; the server's record is printed (`N of M op(s) applied`, every refusal in its words); `--open` hands you the edited table in the browser | Practitioner |
| `surgeon fleet <recipe> <folder> --server URL --key KEY` | `replay` on every `.safetensors` · `.pt` · `.pth` · `.bin` · `.ckpt` file in the folder, one job each, then `N of M checkpoint(s) clean` | Practitioner |
| `surgeon excise <checkpoint> <node> --server URL --key KEY [--open]` | one excision (a dotted node name, as the Nodes & Layers panel shows it) as a one-op job | Practitioner |
| `surgeon merge <checkpoint> <name> --server URL --key KEY [--method lerp\|slerp] [--alpha 0.5] [--open]` | one weight merge as a one-op job; the donor must already be on the table | Practitioner |
| `surgeon watch-definition --server URL --key KEY --token T [--out model_definition.py] [--interval 2]` | keeps a local `model_definition.py` equal to the model on the theatre's table as you edit it: click **⇄ Link CLI** in the theatre and paste the one command the card prints (the token is 16 hex characters, single-use, 60 seconds). The client binds to your browser's session, polls the definition's etag every `--interval` seconds (default 2, never below 0.5) and rewrites the file atomically each time the table changes — the same bytes the ⬇ Model Definition button serves. Prints `linked : …`, `watching : …`, then one `wrote …` line per change. Ctrl+C stops it; when the session ends or the table is cleared the client says so and stops. Receive only — editing the file changes nothing on the table | Practitioner · a server at 7.107 or later |
| `surgeon compare` · `quantize` · `fold` | refuse in words: the server does not run these as job kinds yet. Today they run from a copy of the Model Surgeon repository (`tools/surgeon_cli.py`) | — |

Global flags: `--verbose` prints every request and its status to stderr; `--no-session-cache` keeps nothing between runs (a dropped upload cannot resume).

Exit codes for every command: `0` clean · `1` the server refused one or more ops (the job ran; its words are printed) · `2` the client refused (its message says why and what next). Every HTTP refusal is printed with the server's own words and a `next:` line.

**What the client does not do:** it does not export or download the package — finish in the browser (`--open`) with ⬇ Package Model, or call `/api/export` from Python (below); it does not read the key from the environment; it does not push to Hugging Face.

## From Python

The same client is importable; the notebooks FALCONS.AI publishes use it this way.

```python
from surgeon.client import Remote, ClientError

r = Remote("https://surgeon.falcons.ai", key=KEY, timeout=1800)
meta = r.get("/api/meta")                       # signed_in · tier · version · the model on the table
state = r.upload("model.safetensors",           # the chunk protocol; resumable
                 on_progress=lambda i, n: print(f"chunk {i}/{n}"))
url, ttl = r.claim()                            # the 60-second hand-off link
rec = r.recipe(open("ops.yaml").read())         # {source_model, ops, count} — read by the server
job = r.job(rec["ops"])                         # {id, state, done, total, refused[]}
res = r.call("/api/export", {})                 # build the signed package; res["download"] is the GET path
link = Remote(server, key, session_cache=False) # a fresh jar for a Link CLI token
link.attach(token); link.watch_definition("model_definition.py", interval=2.0)
```

`Remote(server, key=None, timeout=600, opener=None, verbose=False, session_cache=True)` · `.call(path, body)` POST JSON · `.get(path)` GET JSON · `.get_text(path)` GET text · `.upload(path, purpose="model", on_progress=None)` · `.claim()` · `.recipe(text)` · `.job(ops, kind="replay")` · `.attach(token)` · `.watch_definition(out, interval=2.0)`. Every refusal raises `ClientError` with the server's words and the next action; nothing calls `sys.exit`. For a binary download (the package) use `r.opener` with the `X-Surgeon-Key` header, as the published notebook cells do.

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

Python 3.9 or newer, any OS. Output is ASCII-safe on piped Windows consoles. `surgeon doctor` says when the server runs a different version than this client: install the wheel the server serves. `watch-definition` needs a client at 7.109 or later and a server at 7.107 or later (an older client does not list the command in `surgeon --help`).

## Sessions, resume and safety

- The session cookie is kept per server under `~/.falconsai-surgeon/` (directory `0700`, file `0600`), so a dropped upload resumes: rerun the same command and the server says which chunks it already holds (`--verbose` shows `resuming: …`). `--no-session-cache` turns that off.
- The key travels only as the `X-Surgeon-Key` header to the host you named. A redirect to another host is refused in words; the key is never sent there.
- A reply that is not JSON (an edge or proxy page) is reported with its first bytes, never a traceback.
- Sessions are ephemeral: the model is deleted when the browser session ends or after 30 idle minutes. The client never stores a checkpoint.

## Troubleshooting

Run `surgeon doctor --server URL --key KEY` first.

| You see | Meaning | Next |
| --- | --- | --- |
| `could not reach <server>` | nothing answered at that address | is the server up, is the address the one the proxy serves? `surgeon doctor --server URL` |
| `HTTP 401 ... No session` | the session expired (30 idle minutes, a restart) or the cache is stale | run the command again - a new session is minted |
| `HTTP 403 ...` | the key was refused for this command | `surgeon doctor` shows the tier; surgery and jobs need Practitioner; verification needs no key |
| `HTTP 413 ...` | the file is over the tier's ceiling (the message states it) | a smaller checkpoint, `.safetensors` for the larger ceiling, or Practitioner |
| `HTTP 422 ...` | the recipe or job body is not what the server reads | re-export the recipe from a current session |
| `HTTP 429 ...` | rate limited (jobs: 50 per day per Practitioner account) | wait a minute and retry |
| `REFUSED <file>: ... refused: <op> <node>: ...` | the server applied the job and refused an op (name not on the table, already excised, donor missing) | read the server's words; check the name with `surgeon report` or the Nodes & Layers panel |
| `the link token is 16 hex characters` | the pasted `--token` is not the card's | copy the card's whole command with its ⧉ |
| `watch: the table is empty or the session ended` | the theatre has no model, or the session is gone | load a model, click ⇄ Link CLI, run `watch-definition` again |
| `<path>: no such file` | the checkpoint or recipe path is wrong | check the path; `surgeon --help` shows the argument order |
| `Traceback` | a client defect | report it at https://github.com/Falcons-ai/falconsai-surgeon-thin-cli/issues with `--verbose` output |

## How this package is built

The source of truth is the Model Surgeon tree's `client/`; the repository at https://github.com/Falcons-ai/falconsai-surgeon-thin-cli mirrors it at each release and publishes through Trusted Publishing (no stored token). The wheel is built with a pinned build backend and a pinned `SOURCE_DATE_EPOCH` on both sides, and the server prints the sha256 of the wheel it serves at `/download/`; compare it with the hash PyPI shows for the same version.

## Licensing

The client is proprietary; `surgeon/verify.py` — the offline package verifier — is Apache-2.0 and free for everyone, forever. See `LICENSE.txt`.
