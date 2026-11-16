# Передача дел директору проекта Экономическая стратегия

Порядок чтения: README.md, docs/AI_RULES.md, docs/PORTAL_PROTOCOL.md, docs/WORK_PLAN.md, docs/gdd/DECISIONS_APPROVED.md.
Работа: `python tools/work_plan.py next` показывает, что выдавать; `prompt <id>` печатает задание; после приёмки и слияния `set <id> done`.
Приёмка: пробное слияние с main, тесты проекта, проверка зоны файлов (`git diff --name-only`), CI, затем слияние squash.
Чего не делать: менять общие файлы без решения владельца; хранить секреты; действовать на серверах без команды владельца.
