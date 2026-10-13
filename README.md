# nova-registry

Сборщик снимков состояния хоста 'nova'. Диск, память, uptime, docker, git-репозитории.

## Quickstart

    cd ~/nova-registry
    python3 nova_registry.py

Результат:
- JSON-снимок в 'records/NNN-snapshot-<timestamp>.json'
- HTML-дашборд в 'records/latest.html' (открыть в браузере)
- Favicon: 'records/favicon.svg'

## Запуск из меню приложений

После создания '.desktop'-файла Nova Snapshot появится в меню приложений. Запуск без терминала.

## Структура

| Файл | Назначение |
|------|-----------|
| 'nova_registry.py' | Скрипт сбора |
| 'records/' | Снимки и дашборд |
| 'docs/' | Документация |
| 'meta/' | Handoff, transitions, правила агента |

## Зависимости

Python 3.12+ (стандартная библиотека). Docker опционально.

## Лицензия

MIT
