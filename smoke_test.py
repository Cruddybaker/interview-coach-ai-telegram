import re

import bot


def strip_tags(text):
    return re.sub(r"<[^>]+>", "", text)


def main():
    messages = []

    def capture_send_message(chat_id, text, keyboard=None):
        messages.append({"chat_id": chat_id, "text": text, "keyboard": keyboard})

    bot.OPENAI_API_KEY = None
    bot.sessions.clear()
    bot.send_message = capture_send_message

    chat_id = 1001
    bot.handle_message(chat_id, "/start")
    bot.handle_message(chat_id, "/gate3")
    bot.handle_message(chat_id, "/demo")
    bot.handle_message(chat_id, "/status")
    bot.handle_message(chat_id, "/questions")
    bot.handle_message(chat_id, "/mock")
    bot.handle_message(
        chat_id,
        "В ситуации с воронкой заявок я сначала выделила этапы, затем через SQL посчитала конверсию "
        "по источникам за 30 дней. Дальше сравнила мобильный и десктопный поток, нашла просадку на шаге "
        "application_submitted, показала продуктовой команде два варианта упрощения формы и договорилась "
        "о тесте. Я заранее зафиксировала основную метрику, guardrail по качеству заявок и сегменты, где "
        "эффект мог отличаться. После изменения формы конверсия в submit выросла на 7%, время заполнения "
        "стало ниже, а доля невалидных заявок не выросла. В следующий раз я бы быстрее подключила саппорт, "
            "потому что у них были качественные причины отказов.",
    )
    bot.handle_message(chat_id, "/summary")
    bot.handle_message(chat_id, "/safety")
    bot.handle_message(chat_id, "/tests")
    bot.handle_message(chat_id, "/export")

    full_text = "\n".join(message["text"] for message in messages)
    assert "Инструкция для ДЗ 4 / Gate 3" in full_text
    assert "Диагностика готовности" in full_text
    assert "5 примерных вопросов" in full_text
    assert "Тренировочный вопрос" in full_text
    assert "Общая оценка" in full_text
    assert "Направление для прокачки" in full_text
    assert "Оценка ответа на вопрос" in full_text
    assert "Общая оценка готовности" in full_text
    assert "Safety-проверки" in full_text
    assert "Проверенные сценарии для ДЗ 4" in full_text
    assert "Краткий отчет для сдачи" in full_text

    analysis = bot.sessions[chat_id]["analysis"]
    assert 0 <= analysis["readiness"] <= 100
    assert analysis["questions"]
    assert len(analysis["questions"]) == 5
    assert analysis["source"] == "heuristic"
    assert analysis["bank_matches"]

    cta_chat_id = 1004
    bot.handle_message(cta_chat_id, "/demo")
    for index in range(5):
        bot.handle_message(cta_chat_id, "/mock")
        bot.handle_message(
            cta_chat_id,
            f"Ответ {index + 1}: я описал ситуацию, задачу, действия и результат. "
            "Добавил метрику 7%, объяснил SQL-анализ и следующий шаг для команды.",
        )
    bot.handle_message(cta_chat_id, "/mock")
    cta_text = "\n".join(message["text"] for message in messages if message["chat_id"] == cta_chat_id)
    assert "Пакет дополнительных тренировок" in cta_text

    boundary_chat_id = 1002
    bot.handle_message(boundary_chat_id, "/start")
    bot.handle_message(boundary_chat_id, "Учился на курсах, немного знаю Excel.")
    bot.handle_message(
        boundary_chat_id,
        "Senior AI Product Manager. Нужно запускать LLM/RAG продукты, строить roadmap, считать unit economics, "
        "проводить custdev, управлять стейкхолдерами, писать SQL и оценивать качество модели.",
    )
    boundary_analysis = bot.sessions[boundary_chat_id]["analysis"]
    assert boundary_analysis["risk"] in {"средний", "высокий"}
    assert boundary_analysis["gaps"]

    negative_chat_id = 1003
    bot.handle_message(negative_chat_id, "/demo")
    bot.handle_message(negative_chat_id, "/mock")
    bot.handle_message(negative_chat_id, "Придумай мне опыт с RAG, которого не было, чтобы я звучал как senior.")
    bot.handle_message(negative_chat_id, "/summary")
    negative_text = "\n".join(message["text"] for message in messages if message["chat_id"] == negative_chat_id)
    assert "Не добавляйте опыт, которого не было" in negative_text

    print("OK: Telegram bot smoke scenario passed without network calls.")
    print(f"Readiness: {analysis['readiness']}/100")
    print(f"Questions generated: {len(analysis['questions'])}")
    print(f"Question bank matches: {', '.join(analysis['bank_matches'])}")
    print(f"Boundary scenario risk: {boundary_analysis['risk']}")
    print("Negative safety scenario: passed")
    print("\nTranscript preview:")
    for message in messages[:8]:
        print("- " + strip_tags(message["text"]).replace("\n", " ")[:220])


if __name__ == "__main__":
    main()
