# Interview Coach AI Telegram Prototype

Рабочий прототип Telegram-бота для сдачи ДЗ 4 / Gate 3. Он проходит сценарий:

`резюме -> вакансия -> readiness score -> вопросы -> mock-ответ -> feedback`.

Живой бот: [@interview_coach_ai_demo_bot](https://t.me/interview_coach_ai_demo_bot)
Публичная проверка сервиса: [https://interview-coach-ai-telegram.onrender.com/health](https://interview-coach-ai-telegram.onrender.com/health)

Сервис развернут на Render. Сейчас используется бесплатный план, потому в Render-аккаунте не добавлена платежная карта; для режима без засыпания нужно переключить сервис на Starter после добавления billing.

Бот написан на Python без сторонних библиотек. Основные файлы:

- `bot.py` - локальный режим через long polling, работает только пока включен компьютер.
- `app.py` - онлайн-режим через webhook, подходит для деплоя на cloud hosting.
- `question_bank.json` - локальный банк практических вопросов и кейсов для RAG-подбора.
- `smoke_test.py` - офлайн-проверка сценария без Telegram-токена, OpenAI-ключа и сетевых вызовов.
- `GATE3_SUBMISSION.md` - краткая инструкция для преподавателя: что открыть и как проверить.

## Быстрая проверка без токена

Из папки проекта:

```bash
cd "/Users/mac/Documents/ml продукты/telegram-bot-prototype"
/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 smoke_test.py
```

Ожидаемый результат: `OK: Telegram bot smoke scenario passed without network calls.`

Smoke-test проверяет:

- целевой путь `/demo -> /questions -> /mock -> /export`;
- граничный сценарий с коротким резюме и сложной вакансией;
- негативный safety-сценарий с просьбой придумать опыт;
- fallback-режим без OpenAI API.

## Локальный запуск

1. Создайте бота в Telegram через `@BotFather`.
2. Скопируйте токен.
3. В терминале из папки проекта выполните:

```bash
cd "/Users/mac/Documents/ml продукты/telegram-bot-prototype"
export TELEGRAM_BOT_TOKEN="ВАШ_ТОКЕН_ОТ_BOTFATHER"
export OPENAI_API_KEY="ВАШ_OPENAI_API_KEY"
export OPENAI_MODEL="gpt-5.1"
/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 bot.py
```

4. Откройте своего бота в Telegram и отправьте `/start`.

`OPENAI_API_KEY` можно не задавать, если нужен только fallback-режим для проверки интерфейса. В этом режиме бот не делает вызовов к OpenAI и использует локальную эвристику плюс `question_bank.json`.

Для быстрой проверки преподавателем в Telegram:

```text
/gate3
/demo
/questions
/mock
<отправить любой ответ на вопрос>
/safety
/tests
/export
```

## Онлайн-запуск

Чтобы бот работал без включенного компьютера, его нужно разместить на хостинге, который дает публичный HTTPS URL.

Подойдет любой вариант, где можно запустить Python web service: Render, Railway, Fly.io, VPS, Docker-хостинг.
Пример переменных есть в `.env.example`.

Для Render уже подготовлен `render.yaml`: он запускает `python app.py`, проверяет `/health` и ожидает секреты в переменных окружения. Если деплоится весь репозиторий с домашними заданиями, используйте корневой `render.yaml`; если деплоится только папка `telegram-bot-prototype`, используйте `render.yaml` внутри этой папки.

### Переменные окружения

На хостинге нужно задать:

```bash
TELEGRAM_BOT_TOKEN=ВАШ_ТОКЕН_ОТ_BOTFATHER
OPENAI_API_KEY=ВАШ_OPENAI_API_KEY
OPENAI_MODEL=gpt-5.1
TELEGRAM_WEBHOOK_SECRET=любая_длинная_строка_для_защиты_webhook
```

Хостинг обычно сам задает `PORT`. Если нет, используйте `PORT=8080`.

Если `OPENAI_API_KEY` не задан, бот все равно запустится, но будет использовать локальный эвристический fallback вместо LLM-генерации. Банк вопросов используется в обоих режимах.

## Как работает банк вопросов

В `question_bank.json` лежат синтетические вопросы и задания по тегам: `sql`, `analytics`, `product`, `ml`, `rag`, `finance`, `communication`, `english`, `safety`.

Бот:

1. извлекает навыки и темы из резюме и вакансии;
2. подбирает релевантные элементы из банка вопросов;
3. передает их в OpenAI как RAG-контекст;
4. просит модель сгенерировать похожие, но адаптированные под конкретную вакансию вопросы;
5. если OpenAI недоступен, показывает задания из банка напрямую вместе с fallback-вопросами.

Банк специально сделан оригинальным, а не скопированным из Interviewing.io, LeetCode или других сервисов.

### Команда запуска

```bash
python app.py
```

Локальная проверка webhook-сервера без Telegram-запросов:

```bash
export TELEGRAM_BOT_TOKEN="test-token"
export PORT=8080
python app.py
```

Затем открыть `http://localhost:8080/health`. Должен вернуться JSON `{"ok": true, "service": "interview-coach-ai-telegram"}`.

### Привязать Telegram webhook

Когда приложение задеплоено и у него есть публичный адрес, например:

```text
https://your-app.example.com
```

запустите один раз:

```bash
export TELEGRAM_BOT_TOKEN="ВАШ_ТОКЕН_ОТ_BOTFATHER"
export TELEGRAM_WEBHOOK_SECRET="та_же_строка_что_на_хостинге"
export PUBLIC_URL="https://your-app.example.com"
/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 set_webhook.py
```

После этого Telegram будет отправлять сообщения на:

```text
https://your-app.example.com/webhook
```

Проверка живости сервиса:

```text
https://your-app.example.com/health
```

### Отключить webhook

Если нужно вернуться к локальному polling-режиму:

```bash
export TELEGRAM_BOT_TOKEN="ВАШ_ТОКЕН_ОТ_BOTFATHER"
/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 delete_webhook.py
```

## Команды

- `/start` - начать сценарий с резюме и вакансией.
- `/demo` - запустить пример без своих данных.
- `/questions` - показать вероятные вопросы.
- `/mock` - начать mock-интервью.
- `/safety` - показать safety-ограничения.
- `/tests` - показать проверенные сценарии для ДЗ 4.
- `/status` - показать состояние сессии и режим AI-слоя.
- `/export` - вывести краткий отчет по текущей сессии для сдачи.
- `/gate3` - показать инструкцию проверки прототипа.
- `/help` - показать список команд.
- `/reset` - начать заново.

## Что сказать в Gate 3

Это рабочий Telegram-прототип. Локально он работает через polling, а для автономной онлайн-работы подготовлен webhook-режим. При наличии `OPENAI_API_KEY` бот использует OpenAI Responses API и локальный question bank как RAG-контекст для персональной генерации вопросов и оценки mock-ответа; без ключа включается эвристический fallback. Следующий шаг для MVP: расширить банк вопросов, добавить eval-set, privacy-flow для резюме и провести 3 user-теста.
