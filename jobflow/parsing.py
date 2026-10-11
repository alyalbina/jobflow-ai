"""Conservative bilingual extraction; absent information stays null."""

import hashlib
import re

SKILLS = {
    "SQL": ["sql"],
    "Python": ["python", "питон"],
    "Product Management": ["product management", "управление продукт"],
    "Business Analysis": ["business analysis", "бизнес-анализ", "бизнес анализ"],
    "Product Analytics": ["product analytics", "продуктов.*аналит"],
    "UX Research": ["ux research", "ux-исслед"],
    "A/B Testing": ["a/b", "ab testing", "a/b-тест"],
    "API": ["api", "rest"],
    "Figma": ["figma"],
    "Tableau": ["tableau"],
    "Power BI": ["power bi"],
    "Excel": ["excel"],
    "Jira": ["jira"],
    "Agile": ["agile", "scrum"],
    "Web3": ["web3", "blockchain", "блокчейн"],
    "FinTech": ["fintech", "финтех"],
    "Discovery": ["discovery", "дискавери"],
    "Statistics": ["statistics", "статистик"],
    "Machine Learning": ["machine learning", "машинн.*обуч"],
    "German": ["german", "немецк"],
    "English": ["english", "английск"],
}
ROLES = {
    "AI Business Analyst": r"ai business analyst",
    "AI Product Manager": r"ai product manager|ai[- ]продукт",
    "Growth Product Manager": r"growth product manager|growth manager",
    "Product Analyst": r"product analyst|продуктов\w* аналитик",
    "Business Analyst": r"business analyst|бизнес[- ]аналитик",
    "System Analyst": r"system analyst|системн\w* аналитик",
    "UX Researcher": r"ux researcher|ux research|ux[- ]исследователь",
    "Associate Product Manager": r"associate product manager|junior product manager",
    "Product Owner": r"product owner|владелец продукта",
    "Product Operations": r"product operations|product ops",
    "Product Manager": r"product manager|продакт[- ]менеджер|менеджер продукта",
    "Software Engineer": r"software engineer|разработчик",
    "Data Engineer": r"data engineer|дата инженер",
}


def skills_in(text):
    return [
        skill
        for skill, aliases in SKILLS.items()
        if any(re.search(r"(?<!\w)(?:" + a + r")(?!\w)", text, re.IGNORECASE) for a in aliases)
    ]


def canonical_hash(text):
    value = re.sub(r"https?://\S+|@[\w]+", "", text.lower())
    return hashlib.sha256(re.sub(r"\s+", " ", value).strip().encode()).hexdigest()


def parse(text):
    lines = [x.strip(" #*•-\t") for x in text.splitlines() if x.strip()]
    low = text.lower()
    role = next((name for name, pattern in ROLES.items() if re.search(pattern, low)), None)
    vacancy_signal = re.search(
        r"vacancy|hiring|apply|requirements|responsibil|ваканси|ищем|требован|обязанност|отклик", low
    )
    posted_title = re.search(
        r"(?:vacancy|position|вакансия|должность)\s*[:—-]\s*([^\n]{2,120})", text, re.IGNORECASE
    )
    classification = "vacancy" if (role or posted_title) and vacancy_signal else "non_vacancy"
    if re.search(r"webinar|course|вебинар|курс|обучение", low) and not re.search(
        r"we are hiring|ищем.*в команд|вакансия:", low
    ):
        classification = "advertisement"
    if re.search(r"digest|подборка|дайджест", low) and len(re.findall(r"https?://", low)) > 1:
        classification = "roundup"
    if re.search(r"news|новост", low) and not vacancy_signal:
        classification = "news"
    title = (
        posted_title[1].strip()
        if posted_title
        else next(
            (line[:180] for line in lines[:6] if role and re.search(ROLES[role], line, re.IGNORECASE)), None
        )
    )
    company = re.search(r"(?:company|компания|работодатель)\s*[:—-]\s*([^\n]{2,100})", text, re.IGNORECASE)
    seniority = next(
        (
            level
            for level, pattern in [
                ("Head", r"\bhead\b|руководител"),
                ("Lead", r"\blead\b|\bлид\b"),
                ("Senior", r"\bsenior\b|\bсеньор"),
                ("Junior", r"\bjunior\b|\bджуниор"),
                ("Associate", r"\bassociate\b"),
                ("Middle", r"\bmiddle\b|\bmid[- ]level\b|\bмидл"),
            ]
            if re.search(pattern, title or "", re.IGNORECASE)
        ),
        None,
    )
    countries = [
        ("UAE", r"dubai|abu dhabi|\buae\b|дубай|дубаи|оаэ"),
        ("Russia", r"russia|moscow|росси|москв"),
        ("Germany", r"germany|berlin|германи|берлин"),
        ("USA", r"\busa\b|united states|\bus[- ]only\b|сша"),
        ("Montenegro", r"montenegro|черногори"),
    ]
    country = next((name for name, pattern in countries if re.search(pattern, low)), None)
    remote = bool(re.search(r"remote|удал[её]н", low))
    onsite = bool(re.search(r"on[- ]site|офис|office[- ]based", low))
    work_format = (
        "hybrid"
        if re.search(r"hybrid|гибрид", low)
        else "remote"
        if remote
        else "on-site"
        if onsite
        else None
    )
    relocation = (
        False
        if re.search(r"no relocation|no visa|без релокаци|не.*визов", low)
        else True
        if re.search(r"relocation|visa sponsor|релокаци|визов.*поддерж", low)
        else None
    )
    restricted = bool(
        re.search(
            r"(?:must|only|обязательно|только).{0,50}(?:resident|based|граждан|прожива)|us[- ]only", low
        )
    )
    if re.search(
        r"(?:remote|location|удал[её]н|локация)[^\n]{0,50}(?:only|только)|(?:only|только)\s+(?:in\s+)?(?:UAE|USA|Russia|Germany|EU|US|РФ|России|ОАЭ)\b",
        text,
        re.IGNORECASE,
    ):
        restricted = True
    years = re.search(r"(\d{1,2})\s*\+?\s*(?:years?\b|лет\b|года?\b)", low)
    salary = re.search(
        r"(?:salary|зарплата|compensation)\s*[:—-]?\s*(?:([$€])\s*)?(\d[\d ,.]*)\s*(?:[-–—]\s*(\d[\d ,.]*)\s*)?(USD|AED|EUR|RUB|руб|₽|\$|€)?",
        text,
        re.IGNORECASE,
    )

    def amount(value):
        if not value:
            return None
        clean = re.sub(r"[^\d.]", "", value)
        try:
            return float(clean)
        except ValueError:
            return None

    currency = None
    if salary:
        currency = {"$": "USD", "€": "EUR", "руб": "RUB", "₽": "RUB"}.get(
            (salary[4] or salary[1] or "").lower(), (salary[4] or "").upper() or None
        )
    period = (
        "year"
        if re.search(r"/year|per year|annual|в год", low)
        else "month"
        if re.search(r"/month|per month|месяц", low)
        else None
    )
    required, nice = [], []
    nice_section = False
    for line in lines:
        if re.search(r"nice.to.have|preferred|будет плюсом|желательно", line, re.IGNORECASE):
            nice_section = True
        elif re.search(
            r"requirements|must.have|требования|обязанности|responsibilities|we offer|предлагаем",
            line,
            re.IGNORECASE,
        ):
            nice_section = False
        target = nice if nice_section else required
        target.extend(skills_in(line))
    urls = re.findall(r"https?://[^\s<>]+", text)
    urls = [u.rstrip(".,);") for u in urls]
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", text)
    contact = emails[0] if emails else next(iter(re.findall(r"@[A-Za-z][\w]{3,}", text)), None)
    english = re.search(r"(?:english|английский)[^\n]{0,50}(?:[ABC][12]|fluent|свободн)", text, re.IGNORECASE)
    return dict(
        classification=classification,
        title=title,
        role=role,
        company=company[1].strip() if company else None,
        seniority=seniority,
        location=country,
        country=country,
        employment_type="full-time" if re.search(r"full.time|полная занятость", low) else None,
        work_format=work_format,
        salary_min=amount(salary[2]) if salary else None,
        salary_max=amount(salary[3]) if salary else None,
        currency=currency,
        salary_period=period,
        required_skills=sorted(set(required) - {"English", "German"}),
        nice_skills=sorted(set(nice) - set(required) - {"English", "German"}),
        years_experience=int(years[1]) if years else None,
        english_requirement=english[0] if english else None,
        german_required=bool(
            re.search(
                r"(?:german|немецк)[^\n]{0,50}(?:fluent|required|C[12]|обязател|свободн)", text, re.IGNORECASE
            )
        ),
        relocation=relocation,
        country_restricted=restricted,
        application_url=next((u for u in urls if not u.startswith("https://t.me/")), None),
        recruiter_contact=contact,
        repost=bool(re.search(r"forwarded|репост", low)),
        extraction_method="rules-v1",
        industry_requirement=next(
            (
                name
                for name, pattern in [
                    ("FinTech", r"fintech|финтех"),
                    ("Web3", r"web3|crypto|blockchain|крипто|блокчейн"),
                ]
                if re.search(r"(?:experience|опыт)[^\n]{0,60}(?:" + pattern + r")", text, re.IGNORECASE)
            ),
            None,
        ),
    )
