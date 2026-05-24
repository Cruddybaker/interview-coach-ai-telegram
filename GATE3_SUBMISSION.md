# ДЗ 4 / Gate 3: инструкция проверки Telegram-прототипа

## Что это

Рабочий Telegram-прототип Interview Coach AI. Бот принимает резюме и вакансию, строит оценку готовности, показывает слабые места, подбирает вероятные вопросы и оценивает тренировочный ответ.

Ключевой сценарий:

```text
резюме + вакансия -> оценка готовности -> вопросы -> тренировочный ответ -> разбор ответа
```

## Быстрая проверка без Telegram-токена

```bash
cd "/Users/mac/Documents/ml продукты/telegram-bot-prototype"
/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 smoke_test.py
```

Ожидаемый результат:

```text
OK: Telegram bot smoke scenario passed without network calls.
```

## Проверка в Telegram

1. Создать бота через `@BotFather`.
2. Задать токен:

```bash
export TELEGRAM_BOT_TOKEN="ВАШ_ТОКЕН_ОТ_BOTFATHER"
export OPENAI_API_KEY=""
/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 bot.py
```

3. В Telegram открыть бота и пройти:

```text
/gate3
/demo
/questions
/mock
В проекте с воронкой заявок я через SQL нашла просадку на этапе отправки заявки. Мы сократили форму, после чего конверсия выросла на 7%, а качество заявок не ухудшилось.
/safety
/tests
/export
```

## Что покрывает прототип

- Целевой сценарий: подготовка по резюме и вакансии.
- Граничный сценарий: короткое резюме и сложная вакансия.
- Негативный сценарий: просьба придумать несуществующий опыт.
- Privacy/fallback: если `OPENAI_API_KEY` не задан, данные не отправляются во внешнюю AI-модель.

## AI/ML слой

- С `OPENAI_API_KEY`: OpenAI Responses API генерирует диагностику и оценивает ответ.
- Без `OPENAI_API_KEY`: локальная эвристика + `question_bank.json`, чтобы прототип оставался проверяемым без внешних ключей.
- `question_bank.json` работает как локальный банк кейсов для подбора релевантных вопросов.

## Решение Gate 3

Limited Go: технически ключевой сценарий работает, но перед MVP нужно провести 3 живых user-теста, расширить банк вопросов, добавить privacy-flow и сравнить результат с ручной подготовкой через ChatGPT.
