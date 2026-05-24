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
    bot.trial_usage.clear()
    bot.UNLIMITED_TELEGRAM_IDS.clear()
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

    locked_chat_id = 1005
    bot.handle_message(locked_chat_id, "/demo")
    bot.handle_message(locked_chat_id, "/reset")
    bot.handle_message(locked_chat_id, "/demo")
    locked_text = "\n".join(message["text"] for message in messages if message["chat_id"] == locked_chat_id)
    assert "Новые резюме, вакансии и позиции в пробном режиме не разбираются" in locked_text
    assert bot.sessions[locked_chat_id]["analysis"]

    unlimited_chat_id = 7777
    bot.UNLIMITED_TELEGRAM_IDS.add(str(unlimited_chat_id))
    bot.handle_message(unlimited_chat_id, "/whoami")
    bot.handle_message(unlimited_chat_id, "/demo")
    bot.handle_message(unlimited_chat_id, "/reset")
    bot.handle_message(unlimited_chat_id, "Product analyst, SQL, Python, A/B tests.")
    bot.handle_message(unlimited_chat_id, "AI Product Manager, LLM, RAG, SQL, roadmap, metrics.")
    unlimited_text = "\n".join(message["text"] for message in messages if message["chat_id"] == unlimited_chat_id)
    assert "Безлимит включен: <b>да</b>" in unlimited_text
    assert "Диагностика готовности" in unlimited_text

    resume_library_chat_id = 2001
    bot.UNLIMITED_TELEGRAM_IDS.add(str(resume_library_chat_id))
    bot.handle_message(resume_library_chat_id, "/add_resume")
    bot.handle_message(resume_library_chat_id, "ML Product Manager")
    bot.handle_message(
        resume_library_chat_id,
        "3 года в AI-продуктах: LLM, RAG, custdev, roadmap, SQL, метрики качества модели.",
    )
    bot.handle_message(resume_library_chat_id, "/add_resume")
    bot.handle_message(resume_library_chat_id, "Backend Go")
    bot.handle_message(
        resume_library_chat_id,
        "4 года backend: Go, PostgreSQL, Kafka, кеши, highload, микросервисы.",
    )
    bot.handle_message(resume_library_chat_id, "/add_resume")
    bot.handle_message(resume_library_chat_id, "ml product manager")
    bot.handle_message(resume_library_chat_id, "да")
    bot.handle_message(
        resume_library_chat_id,
        "4 года в AI-продуктах: LLM, RAG, custdev, roadmap, SQL, метрики качества модели, запуск MVP.",
    )
    bot.handle_message(resume_library_chat_id, "/update_resume 2")
    bot.handle_message(
        resume_library_chat_id,
        "5 лет backend: Go, PostgreSQL, Kafka, Redis, highload, микросервисы, observability.",
    )
    bot.handle_message(resume_library_chat_id, "/resumes")
    bot.handle_message(resume_library_chat_id, "/use_resume 1")
    bot.handle_message(resume_library_chat_id, "/start")
    bot.handle_message(
        resume_library_chat_id,
        "Middle ML Product Manager. Нужны LLM/RAG, discovery, roadmap, SQL и оценка качества модели.",
    )
    resume_library_text = "\n".join(
        message["text"] for message in messages if message["chat_id"] == resume_library_chat_id
    )
    assert "Мои резюме" in resume_library_text
    assert "уже есть" in resume_library_text
    assert "Обновил резюме <b>ML Product Manager</b>" in resume_library_text
    assert "Обновил резюме <b>Backend Go</b>" in resume_library_text
    assert "Активное резюме: <b>ML Product Manager</b>" in resume_library_text
    assert len(bot.sessions[resume_library_chat_id]["resumes"]) == 2
    assert bot.sessions[resume_library_chat_id]["analysis"]
    assert "запуск MVP" in bot.sessions[resume_library_chat_id]["resume"]
    assert "observability" in bot.sessions[resume_library_chat_id]["resumes"][1]["text"]

    position_chat_id = 2002
    bot.UNLIMITED_TELEGRAM_IDS.add(str(position_chat_id))
    bot.handle_message(position_chat_id, "/position")
    bot.handle_message(position_chat_id, "Senior product analyst, marketplace, SQL, A/B tests, stakeholders")
    position_analysis = bot.sessions[position_chat_id]["analysis"]
    position_text = "\n".join(message["text"] for message in messages if message["chat_id"] == position_chat_id)
    assert position_analysis["mode"] == "position"
    assert position_analysis["grade"] == "senior"
    assert len(position_analysis["questions"]) == 5
    assert "Вопросы по позиции" in position_text
    assert "Грейд: <b>senior/lead</b>" in position_text

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
    print("Trial lock scenario: passed")
    print("Unlimited admin scenario: passed")
    print("Resume library scenario: passed")
    print("Resume duplicate/update scenario: passed")
    print("Position and grade scenario: passed")
    print("\nTranscript preview:")
    for message in messages[:8]:
        print("- " + strip_tags(message["text"]).replace("\n", " ")[:220])


if __name__ == "__main__":
    main()
