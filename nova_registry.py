#!/usr/bin/env python3
"""nova-registry: сборщик снимков состояния хоста nova.

Собирает: диск, память, uptime, docker-контейнеры, git-репозитории в ~.
Записывает JSON в records/NNN-snapshot-<timestamp>.json
Генерирует HTML-дашборд в records/latest.html
"""

import subprocess
import json
import datetime
import os
import re
import locale
from pathlib import Path


DOCKER_KEEP_FIELDS = [
    "ID", "Image", "Names", "State", "Status", "Ports", "RunningFor"
]

GIT_SKIP_PATHS = [
    "node_modules", ".cache", "venv", "__pycache__", ".git/modules"
]


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
            obj = json.loads(line)
            filtered = {k: v for k, v in obj.items() if k in DOCKER_KEEP_FIELDS}
            containers.append(filtered)
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
            repo_path_str = str(git_dir)
            if any(skip in repo_path_str for skip in GIT_SKIP_PATHS):
                continue
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


def write_snapshot(data, records_dir=None):
    if records_dir is None:
        script_dir = Path(__file__).resolve().parent
        records_dir = script_dir / "records"
    serial = get_next_serial(records_dir)
    filename = f"{serial:03d}-snapshot-{data['timestamp'].replace(':', '-').replace('+', '_plus_')}.json"
    filepath = Path(records_dir) / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filepath


def generate_dashboard(snapshot, output_path):
    """Генерирует HTML-дашборд из снимка."""
    host = snapshot.get("host", "UNKNOWN")
    timestamp = snapshot.get("timestamp", "UNKNOWN")
    uptime = snapshot.get("uptime", "UNKNOWN")
    disk = snapshot.get("disk", "UNKNOWN")
    memory = snapshot.get("memory", "UNKNOWN")
    docker = snapshot.get("docker", [])
    git_repos = snapshot.get("git_repos", [])
    unknown = snapshot.get("unknown", [])

    docker_rows = ""
    if docker == "UNKNOWN":
        docker_rows = '<tr><td colspan="7">Docker недоступен</td></tr>'
    elif not docker:
        docker_rows = '<tr><td colspan="7">Нет запущенных контейнеров</td></tr>'
    else:
        for c in docker:
            docker_rows += f"""<tr>
                <td>{c.get('ID', '')}</td>
                <td>{c.get('Names', '')}</td>
                <td>{c.get('Image', '')}</td>
                <td>{c.get('State', '')}</td>
                <td>{c.get('Status', '')}</td>
                <td>{c.get('Ports', '')}</td>
                <td>{c.get('RunningFor', '')}</td>
            </tr>"""

    git_rows = ""
    if not git_repos:
        git_rows = '<tr><td colspan="4">Репозитории не найдены</td></tr>'
    else:
        for r in git_repos:
            status_escaped = r.get('status', '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            git_rows += f"""<tr>
                <td>{r.get('path', '')}</td>
                <td>{r.get('branch', '')}</td>
                <td>{r.get('size', '')}</td>
                <td><pre>{status_escaped}</pre></td>
            </tr>"""

    unknown_html = ""
    if unknown:
        unknown_html = '<div class="section"><h2>Unknown / Ошибки</h2><ul>'
        for u in unknown:
            unknown_html += f"<li>{u}</li>"
        unknown_html += "</ul></div>"

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>nova-registry | {host}</title>
    <link rel="icon" type="image/svg+xml" href="favicon.svg">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        .meta {{
            background: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .meta p {{
            margin: 5px 0;
        }}
        .section {{
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 5px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #3498db;
            color: white;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        pre {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 3px;
            overflow-x: auto;
            font-size: 0.9em;
            margin: 0;
        }}
        .unknown {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
        }}
        ul {{
            margin: 0;
            padding-left: 20px;
        }}
    </style>
</head>
<body>
    <h1>nova-registry Dashboard</h1>
    <div class="meta">
        <p><strong>Host:</strong> {host}</p>
        <p><strong>Timestamp:</strong> {timestamp}</p>
        <p><strong>Uptime:</strong> {uptime}</p>
    </div>

    <div class="section">
        <h2>Disk</h2>
        <pre>{disk}</pre>
    </div>

    <div class="section">
        <h2>Memory</h2>
        <pre>{memory}</pre>
    </div>

    <div class="section">
        <h2>Docker Containers</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Names</th>
                    <th>Image</th>
                    <th>State</th>
                    <th>Status</th>
                    <th>Ports</th>
                    <th>RunningFor</th>
                </tr>
            </thead>
            <tbody>
                {docker_rows}
            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>Git Repositories</h2>
        <table>
            <thead>
                <tr>
                    <th>Path</th>
                    <th>Branch</th>
                    <th>Size</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {git_rows}
            </tbody>
        </table>
    </div>

    {unknown_html}
</body>
</html>"""
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    snapshot = build_snapshot()
    path = write_snapshot(snapshot)
    print(f"Snapshot written to: {path}")

    script_dir = Path(__file__).resolve().parent
    records_dir = script_dir / "records"
    dashboard_path = records_dir / "latest.html"
    generate_dashboard(snapshot, dashboard_path)
    print(f"Dashboard written to: {dashboard_path}")


if __name__ == "__main__":
    main()
