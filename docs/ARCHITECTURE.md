# docs/ARCHITECTURE.md
Архитектура nova-registry.

## Язык и инструмент

- **Язык:** Python 3 (версия 3.12.3, путь /usr/bin/python3).
- **Зависимости:** только стандартная библиотека (subprocess, json, datetime, pathlib, os).
- **Ограничение:** без sudo, только прямой запуск от пользователя shaen.

## Компоненты

### 1. Скрипт сбора: nova_registry.py

Расположение: корень проекта (~/nova-registry/nova_registry.py).

Функции:
- get_disk() - вызов df -h, возврат stdout или UNKNOWN.
- get_memory() - вызов free -h, возврат stdout или UNKNOWN.
- get_uptime() - вызов uptime, возврат stdout или UNKNOWN.
- get_docker() - вызов docker ps --format json, возврат список контейнеров или UNKNOWN (если нет прав или docker не установлен).
- get_git_repos(base_path=~/) - рекурсивный поиск каталогов .git, для каждого: путь, текущая ветка (git branch --show-current), статус (git status --short), приблизительный объем.
- build_snapshot() - сборка словаря с полями: timestamp, host, disk, memory, uptime, docker, git_repos, unknown (список несработавших команд).
- write_snapshot(data) - запись JSON в records/NNN-snapshot-<timestamp>.json.

### 2. Выходной формат

Файл: records/NNN-snapshot-<ISO8601-timestamp>.json

Структура (пример):
{
  "timestamp": "2026-10-13T01:41:04+03:00",
  "host": "nova",
  "disk": "<stdout df -h>",
  "memory": "<stdout free -h>",
  "uptime": "<stdout uptime>",
  "docker": [ { "ID": "...", "Image": "...", "Status": "..." } ] или "UNKNOWN",
  "git_repos": [
    { "path": "/home/shaen/project", "branch": "main", "status": " M file.py", "size": "12M" }
  ],
  "unknown": [ "docker: permission denied" ]
}

### 3. Каталоги

- records/ - выходные JSON-снимки.
- docs/ - документация.
- meta/ - handoff, transitions, agent-rules.
- ARCHIVE/ - устаревшие документы.

## Именование снимков

Формат: NNN-snapshot-<timestamp>.json
- NNN - сквозной порядковый номер, три цифры.
- timestamp - ISO 8601 из datetime.datetime.now().isoformat().

## Обработка ошибок

- Любая команда, завершившаяся с ненулевым кодом или вызвавшая исключение subprocess.CalledProcessError, фиксируется в поле unknown с причиной.
- Скрипт не падает при ошибке отдельной команды: собирает максимум доступного.
- docker ps без прав группы docker -> UNKNOWN с пояснением.

## Безопасность

- Скрипт только читает состояние, не модифицирует хост.
- Не требует sudo.
- Не записывает чувствительные данные (пароли, токены).

## Источник истины по архитектуре

Этот документ (после заполнения).
