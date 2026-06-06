"""Deploy a static site directory to Vercel via the REST API.

Pure payload builders (collect_files/build_payload) are unit-tested without
network; deploy_vercel performs the HTTP I/O (httpx, from the [ai]/[deploy]
extra) and is kept thin.
"""
from __future__ import annotations

import base64
import os
import time
from pathlib import Path

from ...log import get_logger

log = get_logger(__name__)

_API = "https://api.vercel.com"


def collect_files(out_dir: Path) -> list[dict]:
    files: list[dict] = []
    for p in sorted(out_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(out_dir).as_posix()
        data = base64.b64encode(p.read_bytes()).decode("ascii")
        files.append({"file": rel, "data": data, "encoding": "base64"})
    return files


def build_payload(name: str, files: list[dict], *, production: bool) -> dict:
    return {
        "name": name,
        "files": files,
        "projectSettings": {"framework": None},
        "target": "production" if production else "preview",
    }


def deploy_vercel(out_dir: Path, cfg: dict) -> str:
    dcfg = cfg["deploy"]
    token = os.environ.get(dcfg["token_env"])
    if not token:
        raise RuntimeError(
            f"environment variable {dcfg['token_env']} is not set "
            f"(needed to deploy to Vercel)"
        )
    import httpx

    name = dcfg.get("project") or out_dir.resolve().name or "md2x-site"
    files = collect_files(out_dir)
    payload = build_payload(name, files, production=dcfg.get("production", True))
    params = {"teamId": dcfg["team_id"]} if dcfg.get("team_id") else {}
    headers = {"Authorization": f"Bearer {token}"}
    log.info("vercel: uploading %d file(s) as project %r (target=%s)",
             len(files), name, payload["target"])

    with httpx.Client(timeout=120) as client:
        r = client.post(f"{_API}/v13/deployments", params=params,
                        headers=headers, json=payload)
        r.raise_for_status()
        dep = r.json()
        dep_id = dep.get("id")
        url = dep.get("url", "")
        log.info("vercel: deployment %s created; polling for ready state", dep_id)
        # poll until ready
        for _ in range(60):
            if dep.get("readyState") in ("READY", "ERROR", "CANCELED"):
                break
            time.sleep(2)
            s = client.get(f"{_API}/v13/deployments/{dep_id}", params=params,
                           headers=headers)
            s.raise_for_status()
            dep = s.json()
            log.debug("vercel: deployment %s state=%s", dep_id,
                      dep.get("readyState"))
    state = dep.get("readyState")
    log.info("vercel: deployment %s final state=%s", dep_id, state)
    if state and state != "READY":
        raise RuntimeError(f"Vercel deployment ended in state {state}")
    return f"https://{url}" if url and not url.startswith("http") else url
