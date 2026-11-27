"""The game-concept → real-data mapping, defined once and exported to the browser (nation.json `yields`).

All job-based yields count employed persons by place of WORK (November / 4th quarter 2024) in the harmonised
industry groups of admin.GROUPS. Gold is regional GDP apportioned to municipalities by their share of the region's
jobs, so it is an estimate below the county level and is always shown with '≈'.
"""
from __future__ import annotations

YIELDS = [
    {"key": "food", "icon": "y-food", "emoji": "🌾", "label": "Food", "color": "#7fbf3f", "unit": "jobs",
     "groups": ["A"],
     "description": "Jobs in agriculture, forestry and fishing (NACE A), counted at the place of work, November/Q4 2024."},
    {"key": "production", "icon": "y-production", "emoji": "⚙️", "label": "Production", "color": "#d98b3a", "unit": "jobs",
     "groups": ["BC", "F"],
     "description": "Jobs in mining and quarrying (incl. oil and gas extraction), manufacturing and construction "
                    "(NACE B, C, F), at the place of work, 2024."},
    {"key": "gold", "icon": "y-gold", "emoji": "🪙", "label": "Gold", "color": "#e6c14a", "unit": "eur",
     "groups": [],
     "description": "Gross domestic product, current prices 2023, in euro (Eurostat average exchange rates). Published "
                    "for counties/län/landsdele (Norway: gross value added at basic prices; Norway's continental shelf "
                    "is outside every county). For a municipality it is an estimate: the region's GDP times the "
                    "municipality's share of the region's jobs."},
    {"key": "science", "icon": "y-science", "emoji": "🔬", "label": "Science", "color": "#5aa8e6", "unit": "jobs",
     "groups": ["J", "LMN"],
     "description": "Jobs in information and communication (J) and in real estate, professional, scientific, technical "
                    "and business services (L–N), at the place of work, 2024. L–N is one group because that is the "
                    "finest level all three agencies publish."},
    {"key": "culture", "icon": "y-culture", "emoji": "🎭", "label": "Culture", "color": "#b07ad9", "unit": "jobs",
     "groups": ["RS"],
     "description": "Jobs in arts, entertainment, recreation and other services (NACE R–U), at the place of work, 2024."},
    {"key": "welfare", "icon": "i-health", "emoji": "🏥", "label": "Welfare", "color": "#e5707a", "unit": "jobs",
     "groups": ["P", "Q"],
     "description": "Jobs in education and in health and social work (NACE P, Q) — the welfare state's workforce, "
                    "public and private — at the place of work, 2024."},
]

# Specialisation: location quotient against the three countries combined.
LQ_MIN = 1.5
LQ_MIN_JOBS = 250
CITY_TYPES = {
    "A": ("Farming & fishing", "#7fbf3f"), "BC": ("Industrial", "#d9822b"), "DE": ("Energy & utilities", "#f2d230"),
    "F": ("Construction", "#9c6b3e"), "G": ("Trade", "#e08fb0"), "H": ("Logistics", "#3f6fbf"),
    "I": ("Tourism", "#2fb3a0"), "J": ("Tech", "#66d0f5"), "K": ("Finance", "#b8860b"),
    "LMN": ("Business services", "#8aa0c8"), "O": ("Government", "#8a5cc2"), "P": ("Education", "#e6e6a0"),
    "Q": ("Health & care", "#e5505a"), "RS": ("Culture & leisure", "#d070e0"),
}
