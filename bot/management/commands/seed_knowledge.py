from django.core.management.base import BaseCommand

from bot.models import KnowledgeEntry

# Persona + grounding rules now live in views.BASE_INSTRUCTIONS (always-on,
# not retrieval-dependent). These seed entries are just the retrievable
# factual content — company info and service summaries.
SEED_ENTRIES = [
    {
        "language": "de",
        "title": "Unternehmensinformationen",
        "order": 0,
        "retrievable": True,
        "content": """## Unternehmensinformationen
- Name: ONMA scout
- Leistungen: Suchmaschinenoptimierung (SEO), Suchmaschinenwerbung (SEA/Google Ads),
  Webdesign & Webentwicklung, App-Entwicklung
- Kontakt: [Telefonnummer einsetzen], [E-Mail-Adresse einsetzen]
- Adresse: [Firmenadresse einsetzen]
- Öffnungszeiten: Mo–Fr, [Uhrzeiten einsetzen]""",
    },
    {
        "language": "de",
        "title": "Leistungsübersicht",
        "order": 1,
        "retrievable": True,
        "content": """## Leistungsübersicht

### SEO
ONMA scout optimiert Websites für bessere Sichtbarkeit in Suchmaschinen durch
technische Optimierung, Content-Strategie und Backlink-Aufbau.

### SEA
Erstellung und Betreuung von Google-Ads-Kampagnen zur Neukundengewinnung,
inklusive Keyword-Recherche, Anzeigentexten und laufender Optimierung.

### Webdesign
Konzeption und Umsetzung moderner, responsiver Websites, optimiert für
Nutzererfahrung und Conversion.

### App-Entwicklung
Entwicklung individueller mobiler Anwendungen für iOS und Android.""",
    },
    {
        "language": "en",
        "title": "Company information",
        "order": 0,
        "retrievable": True,
        "content": """## Company information
- Name: ONMA scout
- Services: search engine optimization (SEO), search engine advertising
  (SEA/Google Ads), web design & web development, app development
- Contact: [insert phone number], [insert email address]
- Address: [insert company address]
- Hours: Mon–Fri, [insert hours]""",
    },
    {
        "language": "en",
        "title": "Service overview",
        "order": 1,
        "retrievable": True,
        "content": """## Service overview

### SEO
ONMA scout improves a website's visibility in search engines through
technical optimization, content strategy and backlink building.

### SEA
Setup and management of Google Ads campaigns to win new customers,
including keyword research, ad copywriting and ongoing optimization.

### Web design
Design and implementation of modern, responsive websites, optimized for
user experience and conversion.

### App development
Development of custom mobile applications for iOS and Android.""",
    },
]


class Command(BaseCommand):
    help = "Seed the initial DE/EN retrievable knowledge entries (company info + services)."

    def handle(self, *args, **options):
        created = 0
        for entry in SEED_ENTRIES:
            _, was_created = KnowledgeEntry.objects.get_or_create(
                language=entry["language"],
                title=entry["title"],
                defaults={
                    "content": entry["content"],
                    "order": entry["order"],
                    "retrievable": entry["retrievable"],
                },
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Seeded {created} knowledge entries (skipped existing)."))
