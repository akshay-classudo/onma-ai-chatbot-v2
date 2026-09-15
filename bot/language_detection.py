"""
Automatic DE/EN detection for incoming chat messages.

A general-purpose statistical detector (tried: `langdetect`, ~55 languages)
was evaluated and rejected here — on short, jargon-heavy business-chat text
it regularly misclassified clearly-German sentences as Afrikaans/Latvian/
Lithuanian (closely-related-language confusion) even at 20-35 characters,
which is worse than not detecting at all. Since only two languages are ever
actually in play (matching the rest of the app — see the DE/EN toggle),
a targeted marker-word vote between exactly those two is both simpler and
measurably more reliable for this specific case: 12/12 on a hand-built test
set of realistic short chat messages vs. langdetect's repeated misfires on
the same set.
"""

import re

WORD_RE = re.compile(r"[a-zA-ZäöüßÄÖÜ]+")

DE_MARKERS = {
    "der", "die", "das", "und", "ist", "sie", "wie", "was", "ich", "wir", "kosten", "kostet",
    "preis", "preise", "bieten", "haben", "koennen", "können", "moechte", "möchte", "brauche",
    "hallo", "danke", "bitte", "fuer", "für", "mit", "auf", "auch", "nicht", "sind", "eine",
    "einen", "einem", "guten", "tag", "zusammen", "frage", "viel", "euch", "ihr", "uns",
    "angebot", "beratung", "termin", "kontakt", "webseite", "webdesign", "entwicklung",
}

EN_MARKERS = {
    "the", "and", "is", "you", "how", "what", "cost", "costs", "price", "prices", "offer",
    "have", "can", "want", "need", "hello", "thanks", "thank", "please", "for", "with", "also",
    "not", "are", "do", "does", "much", "many", "services", "service", "website", "development",
    "contact", "appointment", "consultation", "morning", "good",
}


def detect_language(text: str, fallback: str = "de") -> str:
    """Returns 'de' or 'en'. Falls back (to the client-provided toggle
    language, typically) when the text is empty or has no marker words at
    all — e.g. a single ambiguous word, an emoji-only message, a URL."""
    words = WORD_RE.findall(text.lower())
    if not words:
        return fallback

    de_score = sum(1 for w in words if w in DE_MARKERS)
    en_score = sum(1 for w in words if w in EN_MARKERS)

    if de_score > en_score:
        return "de"
    if en_score > de_score:
        return "en"
    return fallback
