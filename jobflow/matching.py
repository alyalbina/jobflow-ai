"""Preference score, not hiring probability. Unknowns never become fabricated evidence."""

DEFAULT_WEIGHTS = {"role": 25, "skills": 25, "experience": 20, "location": 15, "seniority": 10, "other": 5}
DEFAULT_ROLES = [
    "Product Analyst",
    "Business Analyst",
    "Associate Product Manager",
    "Product Manager",
    "AI Product Manager",
    "AI Business Analyst",
    "UX Researcher",
    "Growth Product Manager",
    "Product Owner",
    "System Analyst",
    "Product Operations",
]


def default_profile():
    return {
        "name": "",
        "roles": DEFAULT_ROLES,
        "countries": ["UAE", "Russia"],
        "formats": ["remote", "hybrid", "on-site"],
        "years_experience": None,
        "authorized_countries": None,
        "languages": {},
        "salary_min": None,
        "salary_currency": None,
        "salary_period": None,
        "relocation_required": False,
        "excluded_companies": [],
        "excluded_industries": [],
        "facts": [],
        "weights": DEFAULT_WEIGHTS,
    }


def match(job, profile):
    why, gaps, unknowns, hard = [], [], [], []
    facts = [
        f
        for f in profile.get("facts", [])
        if f.get("status") in ("verified", "self_reported") and f.get("approved")
    ]
    supported = {s for f in facts for s in f.get("skills", [])}
    inferred = {
        s for f in profile.get("facts", []) if f.get("status") == "inferred" for s in f.get("skills", [])
    }
    required = job.get("required_skills", [])
    matched = sorted(set(required) & supported)
    missing = sorted(set(required) - supported)
    why += [f"Supported skill: {s}" for s in matched]
    gaps += [f"Not confirmed in profile: {s}" for s in missing]
    domain = job.get("industry_requirement")
    if domain and domain not in supported:
        gaps.append(f"Industry experience is not confirmed: {domain}")
    elif domain:
        why.append(f"Approved industry evidence: {domain}")
    unknowns += [
        f"Inferred only; verify before claiming: {s}" for s in sorted((set(required) & inferred) - supported)
    ]
    role_fit = job.get("role") in profile.get("roles", [])
    if job.get("role") and not role_fit:
        hard.append("Role is outside selected directions")
    elif role_fit:
        why.append("Role is in your selected directions")
    else:
        unknowns.append("Role was not extracted; review the original text")
    years, need = profile.get("years_experience"), job.get("years_experience")
    if years is None or need is None:
        experience = 0.5
        unknowns.append("Years of relevant experience cannot be fully compared")
    else:
        experience = min(1, years / max(need, 1))
        if years < need:
            gaps.append(f"{need} years requested; {years} stated in profile")
            if need >= 8:
                hard.append("Confirmed experience requirement exceeds profile")
        else:
            why.append("Stated experience meets the extracted minimum")
    senior = job.get("seniority")
    senior_ok = senior in ("Junior", "Associate", "Middle")
    unconfirmed_senior = senior in ("Senior", "Lead", "Head") and (years is None or years < 6)
    if unconfirmed_senior:
        gaps.append("Senior/leadership fit is not verified; not recommended by default")
    if senior is None:
        unknowns.append("Seniority is unspecified")
    country, authorization = job.get("country"), profile.get("authorized_countries")
    international_remote = job.get("work_format") == "remote" and not job.get("country_restricted")
    location = (
        1
        if country in profile.get("countries", []) or international_remote
        else 0.5
        if country is None
        else 0.2
    )
    if job.get("country_restricted"):
        if not country:
            unknowns.append("Restricted location: country was not extracted")
        if authorization is None:
            unknowns.append("Restricted location: work authorization is unknown")
        elif country and country not in authorization:
            hard.append("Explicit country restriction conflicts with confirmed work authorization")
    if profile.get("relocation_required") and job.get("relocation") is False:
        hard.append("Relocation is required by profile but explicitly unavailable")
    elif profile.get("relocation_required") and job.get("relocation") is None:
        unknowns.append("Required relocation support is unknown")
    if job.get("work_format") and job["work_format"] not in profile.get("formats", []):
        hard.append("Published work format is outside your selected formats")
    if job.get("relocation") is None:
        unknowns.append("Visa sponsorship / relocation is unspecified")
    if job.get("german_required"):
        german = profile.get("languages", {}).get("German")
        if german is None:
            unknowns.append("Required German proficiency is unknown")
        elif german not in ("C1", "C2", "native", "fluent"):
            hard.append("Required fluent German conflicts with stated language level")
    if job.get("english_requirement"):
        import re

        stated = profile.get("languages", {}).get("English")
        required_level = re.search(r"\b([ABC][12])\b", job["english_requirement"], re.IGNORECASE)
        levels = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6, "native": 7, "fluent": 6}
        if stated is None:
            unknowns.append("English proficiency is unknown")
        elif required_level and levels.get(stated, 0) < levels[required_level[1].upper()]:
            gaps.append("Stated English level is below the published requirement")
        elif required_level:
            why.append("Stated English level meets the extracted requirement")
        else:
            unknowns.append("Confirm English level against the original requirement")
    if job.get("company") in profile.get("excluded_companies", []):
        hard.append("Company is excluded in preferences")
    industry = next(
        (
            x
            for x in profile.get("excluded_industries", [])
            if x.lower() in job.get("original_text", "").lower()
        ),
        None,
    )
    if industry:
        hard.append("Text mentions an excluded industry; review classification")
    salary_known = all(
        [
            profile.get("salary_min"),
            job.get("salary_max") or job.get("salary_min"),
            profile.get("salary_currency") == job.get("currency"),
            profile.get("salary_period") and profile.get("salary_period") == job.get("salary_period"),
        ]
    )
    if salary_known and (job.get("salary_max") or job["salary_min"]) < profile["salary_min"]:
        gaps.append("Published salary ceiling is below your stated minimum")
    elif not salary_known:
        unknowns.append("Salary cannot be compared without matching currency and period")
    for key in ("company", "employment_type"):
        if not job.get(key):
            unknowns.append(f"{key.replace('_', ' ').capitalize()} is unspecified")
    components = {
        "role": 1 if role_fit else 0,
        "skills": len(matched) / len(required) if required else 0.5,
        "experience": experience,
        "location": location,
        "seniority": 1 if senior_ok else 0.1 if unconfirmed_senior else 0.5,
        "other": 0.5 if unknowns else 1,
    }
    weights = profile.get("weights") or DEFAULT_WEIGHTS
    total = sum(max(0, float(weights.get(k, 0))) for k in components)
    score = (
        round(100 * sum(components[k] * max(0, float(weights.get(k, 0))) for k in components) / total, 1)
        if total
        else 0
    )
    action = (
        "Skip"
        if hard or unconfirmed_senior
        else "Apply"
        if score >= 75
        and not gaps
        and location == 1
        and not any(
            any(
                flag in x
                for flag in (
                    "Restricted location",
                    "Required German",
                    "English proficiency",
                    "Required relocation",
                )
            )
            for x in unknowns
        )
        and not (need is not None and years is None)
        else "Review"
        if score >= 45
        else "Save"
    )
    return {
        "score": score,
        "action": action,
        "why": why,
        "gaps": gaps,
        "unknowns": unknowns,
        "hard_filters": hard,
        "components": components,
        "weights": weights,
        "evidence_ids": [f["id"] for f in facts if set(f.get("skills", [])) & set(matched)],
        "meaning": "Preference score; not probability of hiring",
        "method": "explainable-rules-v1",
    }
