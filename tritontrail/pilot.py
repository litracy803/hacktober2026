"""Curated pilot cohort for repeatable end-to-end testing."""

PILOT_CLUBS = {
    "Data Science Student Society": ["data science student society"],
    "Association for Computing Machinery (ACM)": ["association for computing machinery", "acm"],
    "Chinese American Student Association (CASA)": ["chinese american student association", "casa"],
    "Social Club": ["social club"],
    "Aequora Ballet Company": ["aequora ballet"],
    "Engineers Without Borders": ["engineers without borders"],
    "Indian Student Association": ["indian student association"],
    "Pre-Medical APAMSA": ["pre-medical apamsa", "apamsa"],
    "Climbing Club": ["climbing club"],
    "Product Management Club": ["product management club"],
}


def matches_pilot(name: str) -> bool:
    normalized = " ".join(name.lower().replace("@", " ").replace("(", " ").replace(")", " ").split())
    return any(alias in normalized for aliases in PILOT_CLUBS.values() for alias in aliases)
