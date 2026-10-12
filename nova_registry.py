#!/usr/bin/env python3
"""nova-registry: сборщик снимков состояния хоста nova.

Собирает: диск, память, uptime, docker-контейнеры, git-репозитории в ~.
Записывает JSON в records/NNN-snapshot-<timestamp>.json
"""

import subprocess
import json
import datetime
import os
import re
from pathlib import Path


def run_cmd(cmd_list, shell=False):
    """Выполнить команду, вернуть stdout или (None, error_str)."""
    try:
        result = subprocess.run(
            cmd_list,
            capture_output=True,
            text=True,
            check=True,
            shell=shell
        )
        return result.stdout.strip(), None
    except subprocess.CalledProcessError as e:
        return None, f"{' '.join(cmd_list)}: exit {e.returncode}, stderr: {e.stderr.strip()}"
    except FileNotFoundError as e:
        return None, f"{' '.join(cmd_list)}: not found"


def get_disk():
    stdout, err = run_cmd(["df", "-h"])
    return stdout if stdout is not None else "UNKNOWN", err


def get_memory():
    stdout, err = run_cmd(["free", "-h"])
    return stdout if stdout is not None else "UNKNOWN", err


def get_uptime():
    stdout, err = run_cmd(["uptime"])
    return stdout if stdout is not None else "UNKNOWN", err


def get_docker():
    stdout, err = run_cmd(["docker", "ps", "--format", "json"])
    if stdout is None:
        return "UNKNOWN", err
    containers = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            containers.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return containers, None


def get_git_repos(base_path=None):
    if base_path is None:
        base_path = Path.home()
    else:
        base_path = Path(base_path).expanduser()

    repos = []
    unknown = []

    try:
        for git_dir in base_path.rglob(".git"):
            repo_path = git_dir.parent
            try:
                branch_out, branch_err = run_cmd(
                    ["git", "-C", str(repo_path), "branch", "--show-current"]
                )
                status_out, status_err = run_cmd(
                    ["git", "-C", str(repo_path), "status", "--short"]
                )

                size_out, _ = run_cmd(["du", "-sh", str(repo_path)])
                size = size_out.split()[0] if size_out else "UNKNOWN"

                repos.append({
                    "path": str(repo_path),
                    "branch": branch_out if branch_out else "UNKNOWN",
                    "status": status_out if status_out else "",
                    "size": size
                })
            except Exception as e:
                unknown.append(f"git repo {repo_path}: {e}")
    except PermissionError as e:
        unknown.append(f"scan {base_path}: permission denied")

    return repos, unknown if unknown else None


def get_next_serial(records_dir):
    records_dir = Path(records_dir)
    if not records_dir.exists():
        records_dir.mkdir(parents=True, exist_ok=True)
        return 1

    max_num = 0
    pattern = re.compile(r"^(\d{3})-snapshot-.*\.json$")
    for f in records_dir.iterdir():
        if f.is_file():
            m = pattern.match(f.name)
            if m:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
    return max_num + 1


def build_snapshot():
    unknown_errors = []

    disk, err = get_disk()
    if err:
        unknown_errors.append(err)

    memory, err = get_memory()
    if err:
        unknown_errors.append(err)

    uptime, err = get_uptime()
    if err:
        unknown_errors.append(err)

    docker, err = get_docker()
    if err:
        unknown_errors.append(err)

    git_repos, git_err = get_git_repos()
    if git_err:
        unknown_errors.extend(git_err)

    snapshot = {
        "timestamp": datetime.datetime.now().isoformat(),
        "host": "nova",
        "disk": disk,
        "memory": memory,
        "uptime": uptime,
        "docker": docker,
        "git_repos": git_repos,
        "unknown": unknown_errors
    }

    return snapshot


def write_snapshot(data, records_dir="records"):
    serial = get_next_serial(records_dir)
    filename = f"{serial:03d}-snapshot-{data['timestamp'].replace(':', '-').replace('+', '_plus_')}.json"
    filepath = Path(records_dir) / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filepath


def main():
    snapshot = build_snapshot()
    path = write_snapshot(snapshot)
    print(f"Snapshot written to: {path}")


if __name__ == "__main__":
    main()
