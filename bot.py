import html
import json
import os
import re
import time
from pathlib import Path
import urllib.parse
import urllib.request


TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else None
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.1")
OPENAI_API_URL = "https://api.openai.com/v1/responses"
OPENAI_TIMEOUT_SECONDS = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "35"))
QUESTION_BANK_PATH = Path(__file__).with_name("question_bank.json")
BOT_VERSION = "gate3-dz4-v1.1"
TRIAL_QUESTION_LIMIT = 5
UNLIMITED_TELEGRAM_IDS = {
    item.strip()
    for item in os.environ.get("UNLIMITED_TELEGRAM_IDS", "").replace(";", ",").split(",")
    if item.strip()
}

MAIN_KEYBOARD = [
    ["/questions", "/mock"],
    ["/reset", "/help"],
]

POST_TRIAL_KEYBOARD = [
    ["/mock", "/summary"],
    ["/reset", "/help"],
]

STOP_WORDS = {
    "для", "или", "это", "как", "что", "при", "над", "без", "вам", "мы", "вы",
    "the", "and", "with", "from", "this", "that", "will", "are", "job", "role",
    "team", "work", "опыт", "работа", "команда", "кандидат", "задачи", "задача",
    "навыки", "умение", "нужно", "нужен", "нужна", "будет", "наш", "наша",
    "требуется", "требования", "понимание", "знание", "middle", "junior", "senior",
}

SKILL_ALIASES = {
    "python": ["python", "pandas", "numpy", "sklearn", "jupyter"],
    "sql": ["sql", "postgresql", "mysql", "clickhouse", "database", "базы данных"],
    "analytics": ["аналитика", "analyst", "dashboards", "metabase", "tableau", "power bi", "looker"],
    "communication": ["презентация", "stakeholders", "коммуникация", "переговоры", "storytelling"],
    "finance": ["финансы", "unit economics", "p&l", "бюджет", "forecast", "экономика"],
    "ml": ["machine learning", "ml", "llm", "rag", "prompt", "model", "модель", "ai", "ии"],
    "product": ["product", "roadmap", "jtbd", "hypothesis", "custdev", "метрики", "продукт"],
    "english": ["english", "английский", "b2", "c1"],
    "backend": ["backend", "бэкенд", "go", "golang", "php", "java", "микросервис", "rpc", "http", "api"],
    "frontend": ["frontend", "фронтенд", "javascript", "typescript", "react", "html", "css", "браузер"],
    "system_design": ["system design", "highload", "rps", "шард", "кеш", "cache", "kafka", "очеред"],
    "systems": ["linux", "kernel", "syscall", "runtime", "память", "горутины", "goroutine", "канал"],
    "database": ["рсубд", "субд", "postgres", "transaction", "транзакц", "индекс", "scd", "cdc"],
    "algorithms": ["алгоритм", "структур", "сложность", "сортиров", "дерево", "список", "матриц"],
    "business_analysis": ["системный аналитик", "bpmn", "uml", "требован", "интеграц", "er-модель"],
    "banking": ["банк", "сбер", "тинькофф", "т-банк", "кредит", "бирж", "инвестиц"],
    "marketplace": ["ozon", "озон", "авито", "маркетплейс"],
}

SKILL_LABELS = {
    "python": "Python",
    "sql": "SQL",
    "analytics": "аналитика",
    "communication": "коммуникация",
    "finance": "финансы",
    "ml": "ML/LLM",
    "product": "product discovery",
    "english": "английский",
    "backend": "backend",
    "frontend": "frontend",
    "system_design": "system design",
    "systems": "системное программирование",
    "database": "базы данных",
    "algorithms": "алгоритмы",
    "business_analysis": "системный анализ",
    "banking": "банковский домен",
    "marketplace": "маркетплейс",
}

SAMPLE_RESUME = (
    "Junior product/data analyst. 1.5 года опыта в финтех-проекте: строила SQL-дашборды, "
    "анализировала воронку заявок, готовила презентации для product manager и marketing team. "
    "Использовала Python, pandas, Metabase, Excel. Делала A/B анализ промо-кампаний, описывала "
    "метрики, собирала требования у стейкхолдеров. Английский B2. Хочу перейти в ML/AI product role."
)

SAMPLE_JOB = (
    "Middle ML Product Manager / AI Product Analyst. Нужен опыт запуска AI/ML функций, понимание "
    "LLM, RAG, метрик качества модели, custdev, roadmap, unit economics. Задачи: формулировать "
    "гипотезы, проводить пользовательские интервью, описывать requirements для ML-инженеров, "
    "оценивать качество прототипов, считать бизнес-эффект. Плюс: SQL, Python, английский B2+."
)

sessions = {}
trial_usage = {}
question_bank_cache = None


def is_unlimited_user(chat_id):
    return str(chat_id) in UNLIMITED_TELEGRAM_IDS


def trial_state(chat_id):
    return trial_usage.setdefault(
        str(chat_id),
        {"analysis_used": False, "questions_answered": 0, "completed": False},
    )


def has_used_trial(chat_id):
    return (not is_unlimited_user(chat_id)) and bool(trial_state(chat_id).get("analysis_used"))


def mark_trial_analysis_used(chat_id):
    if not is_unlimited_user(chat_id):
        trial_state(chat_id)["analysis_used"] = True


def mark_trial_answered(chat_id, answered_count):
    if is_unlimited_user(chat_id):
        return
    state = trial_state(chat_id)
    state["analysis_used"] = True
    state["questions_answered"] = max(state.get("questions_answered", 0), answered_count)
    if state["questions_answered"] >= TRIAL_QUESTION_LIMIT:
        state["completed"] = True


def normalize(text):
    return re.sub(r"[^\w\s+#.-]", " ", text.lower(), flags=re.UNICODE)


def tokenize(text):
    return [
        word
        for word in normalize(text).split()
        if len(word) > 2 and word not in STOP_WORDS
    ]


def unique_keywords(text):
    counts = {}
    for token in tokenize(text):
        counts[token] = counts.get(token, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:22]]


def detect_skills(text):
    lowered = normalize(text)
    found = []
    for skill, aliases in SKILL_ALIASES.items():
        if any(alias.lower() in lowered for alias in aliases):
            found.append(skill)
    return found


def score_seniority(resume, job):
    resume_text = normalize(resume)
    job_text = normalize(job)
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(года|год|лет|year|years)", resume_text)
    years = float(match.group(1).replace(",", ".")) if match else 0
    requires_middle = bool(re.search(r"middle|senior|3\+|3 лет|от 3", job_text))
    requires_junior = bool(re.search(r"junior|intern|стажер|стажёр", job_text))
    if requires_middle and years < 2:
        return {"penalty": 18, "label": "seniority gap"}
    if requires_middle and years < 3:
        return {"penalty": 8, "label": "partial gap"}
    if requires_junior or years >= 3:
        return {"penalty": 0, "label": "ok"}
    return {"penalty": 4, "label": "unclear"}


def label_skill(skill):
    return SKILL_LABELS.get(skill, skill)


def load_question_bank():
    global question_bank_cache
    if question_bank_cache is not None:
        return question_bank_cache
    try:
        with QUESTION_BANK_PATH.open("r", encoding="utf-8") as file:
            question_bank_cache = json.load(file)
    except Exception as exc:
        print(f"Question bank fallback: {exc}")
        question_bank_cache = []
    return question_bank_cache


def infer_tags(resume, job):
    tags = set(detect_skills(resume) + detect_skills(job))
    lowered = normalize(f"{resume} {job}")
    keyword_tags = {
        "rag": ["rag", "retrieval", "vector", "вектор", "поиск"],
        "safety": ["safety", "guardrail", "этика", "безопасность", "pii"],
        "statistics": ["a/b", "ab test", "статист", "эксперимент"],
        "product": ["roadmap", "hypothesis", "jtbd", "custdev", "продукт", "метрик"],
        "backend": ["backend", "бэкенд", "микросервис", "ручка", "rpc", "http"],
        "frontend": ["frontend", "фронтенд", "react", "typescript", "javascript", "html", "css"],
        "system_design": ["highload", "rps", "шард", "кеш", "cache", "kafka", "очеред", "нагруз"],
        "systems": ["linux", "syscall", "kernel", "runtime", "goroutine", "горутины", "каналы"],
        "database": ["postgres", "рсубд", "субд", "транзакц", "индекс", "scd", "cdc"],
        "algorithms": ["алгоритм", "структур", "сортиров", "сложность", "дерево", "список"],
        "business_analysis": ["системный аналитик", "bpmn", "требован", "интеграц", "er"],
        "banking": ["банк", "сбер", "тинькофф", "т-банк", "кредит", "инвестиц"],
        "marketplace": ["ozon", "озон", "авито", "маркетплейс"],
        "go": ["go", "golang", "горутины", "goroutine", "каналы", "runtime"],
        "php": ["php"],
        "java": ["java", "jvm", "optional", "hibernate"],
        "javascript": ["javascript", "typescript", "js", "ts", "react"],
        "cache": ["cache", "кеш", "lru", "ttl"],
        "kafka": ["kafka", "дубликаты", "at-least-once", "exactly-once"],
        "scd": ["scd", "slowly changing dimensions"],
        "cdc": ["cdc", "change data capture"],
        "testing": ["pytest", "unittest", "jest", "тесты", "mock", "моки"],
    }
    for tag, keywords in keyword_tags.items():
        if any(keyword in lowered for keyword in keywords):
            tags.add(tag)
    return tags


def retrieve_question_bank(resume, job, limit=6):
    tags = infer_tags(resume, job)
    query_words = set(tokenize(f"{resume} {job}"))
    scored = []
    for item in load_question_bank():
        item_tags = set(item.get("tags", []))
        score = len(tags & item_tags) * 5
        item_text = normalize(
            " ".join(
                [
                    str(item.get("company", "")),
                    str(item.get("source", "")),
                    str(item.get("type", "")),
                    str(item.get("difficulty", "")),
                    str(item.get("prompt", "")),
                    " ".join(item.get("signals", [])),
                    " ".join(item_tags),
                ]
            )
        )
        keyword_hits = sum(1 for word in query_words if len(word) > 3 and word in item_text)
        score += min(keyword_hits, 8)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("difficulty", ""), pair[1].get("id", "")))
    return [item for _, item in scored[:limit]]


def bank_items_to_questions(items):
    questions = []
    for item in items:
        prompt = str(item.get("prompt", "")).strip()
        if not prompt:
            continue
        signals = ", ".join(item.get("signals", [])[:4])
        source = item.get("company") or item.get("source")
        prefix = f"Из банка реальных задач: {source}. " if source else "Из банка практических задач. "
        rationale = f"{prefix}Проверяет: {signals}." if signals else f"{prefix}Подходит для этой роли."
        questions.append({"title": prompt[:280], "rationale": rationale[:240]})
    return questions


def extract_response_text(payload):
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    parts = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if isinstance(content.get("text"), str):
                parts.append(content["text"])
    return "\n".join(parts).strip()


def extract_json_object(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def openai_json(developer_prompt, user_prompt, max_output_tokens=1600):
    if not OPENAI_API_KEY:
        return None

    body = {
        "model": OPENAI_MODEL,
        "input": [
            {"role": "developer", "content": developer_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_output_tokens": max_output_tokens,
    }
    request = urllib.request.Request(
        OPENAI_API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=OPENAI_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = extract_response_text(payload)
        return extract_json_object(text)
    except Exception as exc:
        print(f"OpenAI fallback: {exc}")
        return None


def clamp_int(value, default, min_value=0, max_value=100):
    try:
        return max(min_value, min(max_value, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def clean_list(value, limit, fallback):
    if not isinstance(value, list):
        return fallback
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned[:limit] or fallback


def clean_questions(value, fallback):
    if not isinstance(value, list):
        return fallback
    questions = []
    for item in value:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        rationale = str(item.get("rationale", "")).strip()
        if title:
            questions.append(
                {
                    "title": title[:280],
                    "rationale": rationale[:240] or "Вопрос связан с требованиями вакансии и опытом кандидата.",
                }
            )
    return questions[:TRIAL_QUESTION_LIMIT] or fallback[:TRIAL_QUESTION_LIMIT]


def heuristic_analyze(resume, job):
    job_keywords = unique_keywords(job)
    resume_tokens = set(tokenize(resume))
    matched = [word for word in job_keywords if word in resume_tokens]
    missing = [word for word in job_keywords if word not in resume_tokens][:8]
    required_skills = detect_skills(job)
    resume_skills = detect_skills(resume)
    missing_skills = [skill for skill in required_skills if skill not in resume_skills]
    seniority = score_seniority(resume, job)
    match = round((len(matched) / max(1, len(job_keywords))) * 100)
    skill_coverage = (
        (len(required_skills) - len(missing_skills)) / len(required_skills)
        if required_skills
        else 0.45
    )
    readiness = round(
        32
        + skill_coverage * 38
        + match * 0.25
        + len(resume_skills) * 2
        - len(missing_skills) * 3
        - seniority["penalty"]
    )
    readiness = max(8, min(94, readiness))
    bank_items = retrieve_question_bank(resume, job)
    questions = build_questions(required_skills, resume_skills, missing_skills, bank_items)
    gaps = []
    if seniority["label"] != "ok":
        gaps.append("Роль может требовать более высокий уровень seniority, чем явно показан в резюме.")
    gaps += [f"Нет явного доказательства по требованию: {label_skill(skill)}." for skill in missing_skills]
    gaps += [f"Слабый сигнал по ключевому слову вакансии: {word}." for word in missing[:4]]
    return {
        "readiness": readiness,
        "match": match,
        "risk": "низкий" if readiness >= 68 else "средний" if readiness >= 43 else "высокий",
        "focus": label_skill(missing_skills[0] if missing_skills else missing[0] if missing else "story"),
        "gaps": gaps[:7] or ["Явных пробелов мало: фокус на структуре ответов и примерах с метриками."],
        "questions": questions,
        "bank_matches": [item.get("id") for item in bank_items],
        "source": "heuristic",
    }


def llm_analyze(resume, job, baseline):
    bank_items = retrieve_question_bank(resume, job)
    bank_context = [
        {
            "id": item.get("id"),
            "company": item.get("company"),
            "source": item.get("source"),
            "tags": item.get("tags", []),
            "difficulty": item.get("difficulty"),
            "type": item.get("type"),
            "prompt": item.get("prompt"),
            "signals": item.get("signals", []),
            "rubric": item.get("rubric", []),
        }
        for item in bank_items
    ]
    developer_prompt = (
        "Ты карьерный AI interview coach для русскоязычных junior/middle кандидатов. "
        "Сравни резюме и вакансию, но не придумывай опыт кандидата. "
        "Если в резюме нет доказательства навыка, пометь это как gap. "
        "Не помогай скрытно отвечать во время реального интервью; продукт только для подготовки. "
        "Используй банк вопросов как RAG-контекст: генерируй похожие по типу и навыкам задания, "
        "но не копируй формулировки дословно, если можешь адаптировать их под вакансию. "
        "Верни только валидный JSON без markdown."
    )
    user_prompt = (
        "Собери персональную диагностику подготовки к интервью.\n\n"
        "Формат JSON:\n"
        "{\n"
        '  "readiness": 0-100,\n'
        '  "match": 0-100,\n'
        '  "risk": "низкий|средний|высокий",\n'
        '  "focus": "главный фокус подготовки, 1-4 слова",\n'
        '  "gaps": ["до 7 коротких слабых мест"],\n'
        '  "questions": [{"title": "вопрос", "rationale": "почему этот вопрос вероятен"}]\n'
        "}\n\n"
        f"Верни ровно {TRIAL_QUESTION_LIMIT} примерных вопросов по вакансии. Не больше.\n\n"
        f"Baseline heuristic JSON, можно уточнить, но не игнорировать полностью:\n{json.dumps(baseline, ensure_ascii=False)}\n\n"
        f"Релевантные элементы банка вопросов:\n{json.dumps(bank_context, ensure_ascii=False)}\n\n"
        f"Резюме:\n{resume[:6000]}\n\n"
        f"Вакансия:\n{job[:6000]}"
    )
    result = openai_json(developer_prompt, user_prompt, max_output_tokens=1800)
    if not result:
        return None

    risk = str(result.get("risk", baseline["risk"])).strip().lower()
    if risk not in {"низкий", "средний", "высокий"}:
        risk = baseline["risk"]

    return {
        "readiness": clamp_int(result.get("readiness"), baseline["readiness"]),
        "match": clamp_int(result.get("match"), baseline["match"]),
        "risk": risk,
        "focus": str(result.get("focus", baseline["focus"])).strip()[:80] or baseline["focus"],
        "gaps": clean_list(result.get("gaps"), 7, baseline["gaps"]),
        "questions": clean_questions(result.get("questions"), baseline["questions"]),
        "bank_matches": [item.get("id") for item in bank_items],
        "source": "openai",
    }


def analyze(resume, job):
    baseline = heuristic_analyze(resume, job)
    return llm_analyze(resume, job, baseline) or baseline


def build_questions(required_skills, resume_skills, missing_skills, bank_items=None):
    bank_questions = bank_items_to_questions(bank_items or [])
    base_skills = (required_skills or ["product", "analytics"])[:4]
    questions = []
    for skill in base_skills:
        if skill in resume_skills:
            rationale = "Есть сигнал в резюме, нужен конкретный пример с результатом."
        else:
            rationale = "Требование есть в вакансии, но в резюме сигнал слабый или отсутствует."
        questions.append(
            {
                "title": f"Как вы применяли {label_skill(skill)} в проекте?",
                "rationale": rationale,
            }
        )
    for skill in missing_skills[:3]:
        questions.append(
            {
                "title": f"Что вы будете делать, если в задаче потребуется {label_skill(skill)}, а опыта мало?",
                "rationale": "Проверка честности, обучаемости и способности снижать риск для команды.",
            }
        )
    questions = bank_questions + questions + [
        {
            "title": "Расскажите о случае, когда вы улучшили метрику продукта.",
            "rationale": "Проверяет связку задача - действие - измеримый результат.",
        },
        {
            "title": "Как вы приоритизируете гипотезы, если данных мало?",
            "rationale": "Для ML-продукта важно отделять продуктовый риск от технического.",
        },
        {
            "title": "Опишите ситуацию, где вы ошиблись в анализе и как исправили вывод.",
            "rationale": "Проверка зрелости и работы с неопределенностью.",
        },
    ]
    return questions[:TRIAL_QUESTION_LIMIT]


def readiness_label(score):
    if score >= 72:
        return "в целом готов к интервью"
    if score >= 50:
        return "есть база, но нужно усилить подачу"
    return "пока рискованно идти без подготовки"


def combined_readiness_score(analysis, answer_score):
    base_score = analysis.get("readiness", answer_score) if analysis else answer_score
    try:
        return max(0, min(100, round(base_score * 0.65 + answer_score * 0.35)))
    except (TypeError, ValueError):
        return answer_score


def render_training_direction(analysis, advice):
    focus = html.escape(str(analysis.get("focus", "структура ответа")))
    gaps = analysis.get("gaps") or []
    gap_text = html.escape(gaps[0]) if gaps else "добавить больше конкретики, метрик и примеров из опыта"
    advice_text = advice[:2] if advice else ["Соберите 2-3 истории по STAR и потренируйте ответы вслух."]
    safety_advice = next((item for item in advice if "опыт" in item.lower() and item not in advice_text), None)
    if safety_advice:
        advice_text.append(safety_advice)
    return (
        f"<b>Направление для прокачки</b>\n"
        f"Главный фокус: <b>{focus}</b>.\n"
        f"Что усилить перед интервью: {gap_text}\n"
        f"{fmt_list(advice_text)}"
    )


def render_more_questions_cta():
    return (
        "<b>Нужны еще вопросы?</b>\n"
        "Пакет дополнительных тренировок под конкретную компанию и роль уже в разработке. "
        "Оплату пока не подключили: сейчас это заглушка, а позже здесь появится переход к покупке."
    )


def render_trial_choice():
    return (
        "Что делаем дальше?\n"
        "• /mock - продолжить тренировку\n"
        "• /summary - получить общую оценку готовности"
    )


def render_trial_locked(has_current_analysis=False):
    if has_current_analysis:
        return (
            "У тебя уже активирован пробный набор из 5 вопросов. "
            "Новые резюме и вакансии в пробном режиме не разбираются.\n\n"
            "Можно продолжить текущую тренировку через /mock, посмотреть вопросы через /questions "
            "или получить общую оценку через /summary.\n\n"
            + render_more_questions_cta()
        )
    return (
        "Пробный лимит уже использован: новые резюме, вакансии, вопросы и оценки в бесплатном режиме "
        "больше не выдаются.\n\n"
        + render_more_questions_cta()
    )


def render_whoami(chat_id):
    status = "да" if is_unlimited_user(chat_id) else "нет"
    return (
        "<b>Telegram ID</b>\n\n"
        f"ID этого чата: <code>{html.escape(str(chat_id))}</code>\n"
        f"Безлимит включен: <b>{status}</b>"
    )


def render_summary(session):
    analysis = session.get("analysis")
    if not analysis:
        return "Пока нет диагностики. Пришли резюме и вакансию через /start."

    answer_scores = session.get("answer_scores", [])
    answered_count = len(answer_scores)
    if not answered_count:
        return "Пока нет ответов для общей оценки. Напиши /mock и ответь хотя бы на один вопрос."

    total_questions = min(TRIAL_QUESTION_LIMIT, len(analysis.get("questions", [])))
    avg_answer_score = round(sum(answer_scores[-total_questions:]) / min(answered_count, total_questions))
    overall_score = combined_readiness_score(analysis, avg_answer_score)
    weak_spot = html.escape((analysis.get("gaps") or ["Добавить больше конкретики и метрик в ответы."])[0])
    focus = html.escape(str(analysis.get("focus", "структура ответа")))
    return (
        "<b>Общая оценка готовности</b>\n\n"
        f"Итог: <b>{overall_score}/100</b> - {html.escape(readiness_label(overall_score))}\n"
        f"Средняя оценка ответов: <b>{avg_answer_score}/100</b> "
        f"(пройдено {min(answered_count, total_questions)}/{total_questions})\n"
        f"Базовая оценка по резюме и вакансии: <b>{analysis.get('readiness', overall_score)}/100</b>\n\n"
        f"<b>Что прокачать перед интервью</b>\n"
        f"Главный фокус: <b>{focus}</b>\n"
        f"Первое слабое место: {weak_spot}\n\n"
        "Рекомендация: подготовь 2-3 истории по STAR, добавь измеримые результаты и потренируй короткие ответы на вопросы из текущего набора."
    )


def heuristic_score_answer(answer, analysis):
    words = len(tokenize(answer))
    answer_text = normalize(answer)
    has_story = bool(re.search(r"ситуац|задач|действ|результ|star|метрик|итог|impact|result", answer_text))
    has_numbers = bool(re.search(r"\d", answer))
    makes_false_claim = bool(re.search(r"придум|не было|соврать|fake|выдум", answer_text))
    score = 35
    if 55 <= words <= 170:
        score += 18
    if has_story:
        score += 18
    if has_numbers:
        score += 12
    if analysis:
        focus_words = [normalize(q["title"]).split()[0] for q in analysis.get("questions", [])[:4]]
        score += min(17, sum(1 for word in focus_words if word and word in answer_text) * 4)
    if makes_false_claim:
        score = min(score, 38)
    score = max(10, min(96, score))
    advice = []
    if words < 55:
        advice.append("Добавьте контекст и результат.")
    if words > 170:
        advice.append("Сократите ответ до 60-90 секунд.")
    if not has_story:
        advice.append("Соберите ответ по STAR.")
    if not has_numbers:
        advice.append("Добавьте метрику, срок или масштаб.")
    if makes_false_claim:
        advice.append("Не добавляйте опыт, которого не было.")
    verdict = "готовый каркас" if score >= 72 else "нужно усилить" if score >= 50 else "слабый ответ"
    return score, verdict, advice or ["Ответ достаточно конкретный. Следующий шаг - сделать его короче и естественнее."]


def llm_score_answer(answer, analysis, question, resume, job, baseline):
    developer_prompt = (
        "Ты строгий, но полезный AI interview coach. Оцени mock-ответ кандидата по вопросу. "
        "Не придумывай факты, которых нет в ответе или резюме. "
        "Если кандидат просит/пытается выдумать опыт, снизь оценку и предложи честную формулировку. "
        "Верни только валидный JSON без markdown."
    )
    user_prompt = (
        "Оцени ответ кандидата.\n\n"
        "Формат JSON:\n"
        "{\n"
        '  "score": 0-100,\n'
        '  "verdict": "короткий вердикт",\n'
        '  "advice": ["2-4 конкретных совета"]\n'
        "}\n\n"
        "Критерии: релевантность вопросу и вакансии, структура STAR, конкретика, метрики, честность, краткость.\n\n"
        f"Baseline heuristic: score={baseline[0]}, verdict={baseline[1]}, advice={baseline[2]}\n\n"
        f"Вопрос:\n{question or 'Не указан'}\n\n"
        f"Ответ кандидата:\n{answer[:5000]}\n\n"
        f"Резюме:\n{resume[:4000]}\n\n"
        f"Вакансия:\n{job[:4000]}"
    )
    result = openai_json(developer_prompt, user_prompt, max_output_tokens=900)
    if not result:
        return None
    score = clamp_int(result.get("score"), baseline[0])
    verdict = str(result.get("verdict", baseline[1])).strip()[:80] or baseline[1]
    advice = clean_list(result.get("advice"), 4, baseline[2])
    return score, verdict, advice


def score_answer(answer, analysis, question=None, resume="", job=""):
    baseline = heuristic_score_answer(answer, analysis)
    return llm_score_answer(answer, analysis, question, resume, job, baseline) or baseline


def api_call(method, params=None):
    data = urllib.parse.urlencode(params or {}).encode()
    with urllib.request.urlopen(f"{API_URL}/{method}", data=data, timeout=35) as response:
        return json.loads(response.read().decode())


def send_message(chat_id, text, keyboard=None):
    params = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if keyboard:
        params["reply_markup"] = json.dumps({"keyboard": keyboard, "resize_keyboard": True})
    api_call("sendMessage", params)


def fmt_list(items):
    return "\n".join(f"• {html.escape(item)}" for item in items)


def render_report(analysis):
    bank_count = len(analysis.get("bank_matches", []))
    return (
        f"<b>Диагностика готовности</b>\n\n"
        f"Readiness score: <b>{analysis['readiness']}/100</b>\n"
        f"Match: <b>{analysis['match']}%</b>\n"
        f"Риск: <b>{html.escape(analysis['risk'])}</b>\n"
        f"Фокус подготовки: <b>{html.escape(analysis['focus'])}</b>\n\n"
        f"<b>Слабые места</b>\n{fmt_list(analysis['gaps'])}\n\n"
        f"Банк вопросов: подобрано <b>{bank_count}</b> релевантных кейсов\n\n"
        f"Я подготовил <b>{TRIAL_QUESTION_LIMIT} примерных вопросов</b> по этой вакансии. "
        f"Напиши /questions, чтобы посмотреть список, или /mock, чтобы начать тренировку."
    )


def render_questions(analysis):
    lines = [f"<b>{TRIAL_QUESTION_LIMIT} примерных вопросов по вакансии</b>"]
    for index, question in enumerate(analysis["questions"][:TRIAL_QUESTION_LIMIT], 1):
        lines.append(
            f"\n<b>{index}. {html.escape(question['title'])}</b>\n"
            f"{html.escape(question['rationale'])}"
        )
    lines.append("\nНапиши /mock, чтобы ответить на первый вопрос.")
    return "\n".join(lines)


def render_help():
    return (
        "<b>ИИ-тренер интервью: команды</b>\n\n"
        "/start - начать со своего резюме и вакансии\n"
        "/questions - показать вероятные вопросы\n"
        "/mock - начать тренировочный вопрос\n"
        "/reset - начать заново"
    )


def render_gate3_instructions():
    mode = "OpenAI API" if OPENAI_API_KEY else "локальный fallback без внешних AI-вызовов"
    return (
        "<b>Инструкция для ДЗ 4 / Gate 3</b>\n\n"
        "Это рабочий Telegram-прототип Interview Coach AI. Он проходит ключевой сценарий:\n"
        "резюме + вакансия -> оценка готовности -> вероятные вопросы -> тренировочный ответ -> разбор ответа.\n\n"
        "<b>Как проверить за 3 минуты</b>\n"
        "1. Нажать /demo.\n"
        "2. Нажать /questions и посмотреть список вопросов.\n"
        "3. Нажать /mock и отправить ответ одним сообщением.\n"
        "4. Нажать /safety и /export.\n\n"
        "<b>Режим сейчас</b>\n"
        f"{html.escape(mode)}. Бот работает даже без OPENAI_API_KEY: тогда используется эвристика и локальный банк вопросов.\n\n"
        "<b>Что покрыто прототипом</b>\n"
        "• целевой сценарий подготовки;\n"
        "• граничный сценарий с коротким резюме;\n"
        "• негативный сценарий с просьбой выдумать опыт;\n"
        "• privacy/safety режим без отправки данных в OpenAI, если ключ не задан."
    )


def render_safety():
    return (
        "<b>Safety-проверки</b>\n"
        "• Не придумывать опыт, которого нет в резюме.\n"
        "• Не делать скрытый live-copilot во время реального интервью.\n"
        "• Не хранить PII без согласия пользователя.\n"
        "• Показывать неопределенность, если вопрос только вероятный.\n"
        "• Не обещать гарантированное трудоустройство."
    )


def render_tests():
    return (
        "<b>Проверенные сценарии для ДЗ 4</b>\n\n"
        "<b>1. Целевой</b>\n"
        "Команда /demo -> /questions -> /mock. Ожидается readiness report, вопросы из банка и оценка ответа.\n\n"
        "<b>2. Граничный</b>\n"
        "Очень короткое резюме + сложная вакансия. Ожидается более высокий риск и список слабых сигналов.\n\n"
        "<b>3. Негативный</b>\n"
        "Ответ с просьбой придумать несуществующий опыт. Ожидается снижение score и рекомендация не добавлять фейковый опыт.\n\n"
        "<b>4. Privacy/fallback</b>\n"
        "OPENAI_API_KEY не задан. Ожидается работа без внешних AI-вызовов через локальную эвристику и question_bank.json.\n\n"
        "Автоматическая офлайн-проверка: <code>python smoke_test.py</code>."
    )


def render_status(session):
    analysis = session.get("analysis")
    mode = "OpenAI API" if OPENAI_API_KEY else "локальный fallback"
    state = session.get("state", "idle")
    has_resume = "да" if session.get("resume") else "нет"
    has_job = "да" if session.get("job") else "нет"
    if analysis:
        summary = (
            f"readiness: <b>{analysis['readiness']}/100</b>, "
            f"risk: <b>{html.escape(analysis['risk'])}</b>, "
            f"questions: <b>{len(analysis.get('questions', []))}</b>"
        )
    else:
        summary = "анализ еще не собран"
    return (
        "<b>Статус прототипа</b>\n\n"
        f"Версия: <code>{BOT_VERSION}</code>\n"
        f"Режим AI-слоя: <b>{html.escape(mode)}</b>\n"
        f"Состояние диалога: <b>{html.escape(state)}</b>\n"
        f"Резюме получено: <b>{has_resume}</b>\n"
        f"Вакансия получена: <b>{has_job}</b>\n"
        f"Текущий результат: {summary}\n\n"
        "Это служебная команда для диагностики прототипа."
    )


def render_export(session):
    analysis = session.get("analysis")
    if not analysis:
        return "Пока нечего экспортировать. Пришли резюме и вакансию через /start."
    questions = analysis.get("questions", [])
    top_questions = "\n".join(
        f"{index}. {html.escape(question['title'])}"
        for index, question in enumerate(questions[:TRIAL_QUESTION_LIMIT], 1)
    )
    bank_matches = ", ".join(analysis.get("bank_matches", [])) or "нет"
    return (
        "<b>Краткий отчет для сдачи</b>\n\n"
        f"Readiness score: <b>{analysis['readiness']}/100</b>\n"
        f"Match: <b>{analysis['match']}%</b>\n"
        f"Риск: <b>{html.escape(analysis['risk'])}</b>\n"
        f"Фокус: <b>{html.escape(analysis['focus'])}</b>\n"
        f"Режим: <b>{'OpenAI API' if analysis.get('source') == 'openai' else 'локальная эвристика'}</b>\n"
        f"Подобранные кейсы банка: <code>{html.escape(bank_matches)}</code>\n\n"
        "<b>Слабые места</b>\n"
        f"{fmt_list(analysis['gaps'])}\n\n"
        "<b>Топ вопросов</b>\n"
        f"{top_questions}\n\n"
        "Проверочный путь: /demo -> /questions -> /mock -> ответ -> /safety -> /export."
    )


def handle_message(chat_id, text):
    session = sessions.setdefault(chat_id, {"state": "idle"})
    command = text.strip().lower()

    if command in {"/start", "старт"}:
        if has_used_trial(chat_id):
            send_message(chat_id, render_trial_locked(bool(session.get("analysis"))), keyboard=POST_TRIAL_KEYBOARD)
            return
        session.clear()
        session["state"] = "waiting_resume"
        send_message(
            chat_id,
            "Привет. Я ИИ-тренер интервью.\n\nПришли резюме текстом, а следующим сообщением - вакансию. "
            f"Я оценю готовность, найду слабые места и подберу {TRIAL_QUESTION_LIMIT} примерных вопросов, "
            "похожих на реальные задачи для этой роли.\n\nПосле тренировочного ответа дам общую оценку "
            "и направление, что прокачать перед интервью.",
            keyboard=MAIN_KEYBOARD,
        )
        return

    if command == "/whoami":
        send_message(chat_id, render_whoami(chat_id), keyboard=MAIN_KEYBOARD)
        return

    if command in {"/help", "help", "помощь"}:
        send_message(chat_id, render_help(), keyboard=MAIN_KEYBOARD)
        return

    if command == "/gate3":
        send_message(chat_id, render_gate3_instructions(), keyboard=MAIN_KEYBOARD)
        return

    if command == "/tests":
        send_message(chat_id, render_tests(), keyboard=MAIN_KEYBOARD)
        return

    if command == "/status":
        send_message(chat_id, render_status(session), keyboard=MAIN_KEYBOARD)
        return

    if command == "/export":
        send_message(chat_id, render_export(session), keyboard=MAIN_KEYBOARD)
        return

    if command == "/summary":
        send_message(chat_id, render_summary(session), keyboard=POST_TRIAL_KEYBOARD)
        return

    if command == "/reset":
        if has_used_trial(chat_id):
            send_message(chat_id, render_trial_locked(bool(session.get("analysis"))), keyboard=POST_TRIAL_KEYBOARD)
            return
        session.clear()
        session["state"] = "waiting_resume"
        send_message(chat_id, "Ок, начинаем заново. Пришли резюме текстом.", keyboard=MAIN_KEYBOARD)
        return

    if command == "/demo":
        if has_used_trial(chat_id):
            send_message(chat_id, render_trial_locked(bool(session.get("analysis"))), keyboard=POST_TRIAL_KEYBOARD)
            return
        analysis = analyze(SAMPLE_RESUME, SAMPLE_JOB)
        session.update(
            {
                "state": "idle",
                "resume": SAMPLE_RESUME,
                "job": SAMPLE_JOB,
                "analysis": analysis,
                "mock_index": 0,
            }
        )
        mark_trial_analysis_used(chat_id)
        send_message(chat_id, render_report(analysis), keyboard=MAIN_KEYBOARD)
        return

    if command == "/questions":
        analysis = session.get("analysis")
        if not analysis:
            if has_used_trial(chat_id):
                send_message(chat_id, render_trial_locked(False), keyboard=POST_TRIAL_KEYBOARD)
                return
            send_message(chat_id, "Сначала пришли резюме и вакансию через /start.", keyboard=MAIN_KEYBOARD)
            return
        send_message(chat_id, render_questions(analysis), keyboard=MAIN_KEYBOARD)
        return

    if command == "/mock":
        analysis = session.get("analysis")
        if not analysis:
            if has_used_trial(chat_id):
                send_message(chat_id, render_trial_locked(False), keyboard=POST_TRIAL_KEYBOARD)
                return
            send_message(chat_id, "Сначала пришли резюме и вакансию через /start.", keyboard=MAIN_KEYBOARD)
            return
        questions = analysis.get("questions", [])[:TRIAL_QUESTION_LIMIT]
        if not questions:
            send_message(chat_id, "Пока нет вопросов для тренировки. Пришли резюме и вакансию через /start.", keyboard=MAIN_KEYBOARD)
            return
        if session.get("mock_index", 0) >= len(questions):
            send_message(
                chat_id,
                f"Ты уже прошел все {TRIAL_QUESTION_LIMIT} пробных вопросов по этой вакансии.\n\n"
                + render_more_questions_cta()
                + "\n\nНапиши /summary, чтобы получить общую оценку готовности.",
                keyboard=POST_TRIAL_KEYBOARD,
            )
            return
        session["state"] = "waiting_answer"
        session["mock_index"] = session.get("mock_index", 0)
        question = questions[session["mock_index"]]["title"]
        send_message(
            chat_id,
            f"<b>Тренировочный вопрос {session['mock_index'] + 1}/{TRIAL_QUESTION_LIMIT}</b>\n"
            f"{html.escape(question)}\n\nНапиши ответ одним сообщением.",
        )
        return

    if command == "/safety":
        send_message(chat_id, render_safety(), keyboard=MAIN_KEYBOARD)
        return

    if session.get("state") == "waiting_resume":
        if has_used_trial(chat_id):
            session["state"] = "idle"
            send_message(chat_id, render_trial_locked(bool(session.get("analysis"))), keyboard=POST_TRIAL_KEYBOARD)
            return
        session["resume"] = text.strip()
        session["state"] = "waiting_job"
        send_message(chat_id, "Принял резюме. Теперь пришли описание вакансии.")
        return

    if session.get("state") == "waiting_job":
        if has_used_trial(chat_id):
            session["state"] = "idle"
            send_message(chat_id, render_trial_locked(bool(session.get("analysis"))), keyboard=POST_TRIAL_KEYBOARD)
            return
        session["job"] = text.strip()
        send_message(chat_id, "Собираю диагностику. Обычно это занимает несколько секунд.")
        analysis = analyze(session["resume"], session["job"])
        session["analysis"] = analysis
        session["mock_index"] = 0
        session["state"] = "idle"
        mark_trial_analysis_used(chat_id)
        send_message(chat_id, render_report(analysis), keyboard=MAIN_KEYBOARD)
        return

    if session.get("state") == "waiting_answer":
        analysis = session.get("analysis")
        questions = (analysis.get("questions") or [{}])[:TRIAL_QUESTION_LIMIT]
        mock_index = min(session.get("mock_index", 0), len(questions) - 1)
        question = questions[mock_index].get("title", "")
        send_message(chat_id, "Оцениваю ответ по рубрике.")
        score, verdict, advice = score_answer(
            text,
            analysis,
            question=question,
            resume=session.get("resume", ""),
            job=session.get("job", ""),
        )
        answered_count = session.get("mock_index", 0) + 1
        session["mock_index"] = answered_count
        session.setdefault("answer_scores", []).append(score)
        session["state"] = "idle"
        mark_trial_answered(chat_id, answered_count)
        if answered_count >= len(questions):
            next_step = (
                f"Ты прошел все {TRIAL_QUESTION_LIMIT} пробных вопросов по этой вакансии.\n\n"
                "Можешь получить общую оценку через /summary.\n\n"
                + render_more_questions_cta()
            )
        else:
            remaining = len(questions) - answered_count
            next_step = f"Осталось вопросов: {remaining}.\n\n{render_trial_choice()}"
        send_message(
            chat_id,
            f"<b>Оценка ответа на вопрос: {score}/100 - {html.escape(verdict)}</b>\n"
            f"{render_training_direction(analysis, advice)}\n\n"
            f"{next_step}",
            keyboard=POST_TRIAL_KEYBOARD,
        )
        return

    send_message(chat_id, "Напиши /start, чтобы начать, или /help, чтобы посмотреть команды.", keyboard=MAIN_KEYBOARD)


def poll():
    if not TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN before running: export TELEGRAM_BOT_TOKEN='123:abc'")
    offset = None
    print("Interview Coach AI Telegram bot is running. Press Ctrl+C to stop.")
    while True:
        try:
            params = {"timeout": 30}
            if offset:
                params["offset"] = offset
            result = api_call("getUpdates", params)
            for update in result.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or {}
                chat = message.get("chat") or {}
                text = message.get("text")
                if chat.get("id") and text:
                    handle_message(chat["id"], text)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as exc:
            print(f"Polling error: {exc}")
            time.sleep(3)


if __name__ == "__main__":
    poll()
