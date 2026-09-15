"""
Keyword-based sales-intent detection — not ML, not meant to be precise.
Good enough to decide "should we offer the contact form here?" without
pestering a visitor who's just asking general questions.
"""

SALES_INTENT_KEYWORDS = {
    "de": [
        "preis", "preise", "kosten", "kostet", "wie viel", "wieviel",
        "angebot", "beratung", "anfrage", "budget", "termin", "buchen",
        "zusammenarbeit", "beauftragen",
    ],
    "en": [
        "price", "pricing", "cost", "costs", "how much", "quote", "offer",
        "consultation", "budget", "book a call", "get started", "hire",
        "work with you", "proposal",
    ],
}

SERVICE_KEYWORDS = {
    "de": [
        ("SEO", ["seo", "suchmaschinenoptimierung"]),
        ("SEA", ["sea", "google ads", "anzeigen", "werbung"]),
        ("Webdesign", ["webdesign", "website", "webseite"]),
        ("App-Entwicklung", ["app", "anwendung"]),
    ],
    "en": [
        ("SEO", ["seo", "search engine optimization"]),
        ("SEA", ["sea", "google ads", "ppc"]),
        ("Web design", ["web design", "website"]),
        ("App development", ["app", "application", "mobile app"]),
    ],
}

DEFAULT_SERVICE_INTEREST = {
    "de": "Allgemeine Anfrage",
    "en": "General inquiry",
}


def detect_sales_intent(message: str, language: str) -> str | None:
    """Returns a guessed service_interest label if the message shows sales
    intent, else None."""
    text = message.lower()
    keywords = SALES_INTENT_KEYWORDS.get(language, SALES_INTENT_KEYWORDS["de"])

    if not any(keyword in text for keyword in keywords):
        return None

    for label, service_keywords in SERVICE_KEYWORDS.get(language, []):
        if any(keyword in text for keyword in service_keywords):
            return label

    return DEFAULT_SERVICE_INTEREST.get(language, DEFAULT_SERVICE_INTEREST["de"])
