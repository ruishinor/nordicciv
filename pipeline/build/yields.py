"""The game-concept → real-data mapping, defined once and exported to the browser (nation.json `yields`).

All job-based yields count employed persons by place of WORK (November / 4th quarter 2024) in the harmonised
industry groups of admin.GROUPS: they measure where people work in those industries, not what those industries produce
(agricultural jobs are not food output, knowledge-sector jobs are not research output, welfare jobs are not welfare
quality). Gold is regional economic output; below the region it is an estimate, always shown with '≈'.
`measure` is the short real-world label shown next to every value (NC-T09/§10).
"""
from __future__ import annotations

YIELDS = [
    {"key": "food", "measure": "agriculture, forestry & fishing jobs", "icon": "y-food", "emoji": "🌾", "label": "Food", "color": "#7fbf3f", "unit": "jobs",
     "groups": ["A"],
     "description": "Jobs in agriculture, forestry and fishing (NACE A), counted at the place of work, November/Q4 2024."},
    {"key": "production", "measure": "mining, manufacturing & construction jobs", "icon": "y-production", "emoji": "⚙️", "label": "Production", "color": "#d98b3a", "unit": "jobs",
     "groups": ["BC", "F"],
     "description": "Jobs in mining and quarrying (incl. oil and gas extraction), manufacturing and construction "
                    "(NACE B, C, F), at the place of work, 2024."},
    {"key": "gold", "measure": "economic output, € (est. below region)", "icon": "y-gold", "emoji": "🪙", "label": "Gold", "color": "#e6c14a", "unit": "eur",
     "groups": [],
     "description": "Regional economic output, current prices 2023, in euro (Eurostat average exchange rates), as each "
                    "agency publishes it: Norway gross value added at basic prices by county (the continental shelf "
                    "is outside every county), Sweden regional GDP at market prices by län, Denmark regional GDP by "
                    "landsdel — related but not identical concepts. For a municipality it is an estimate: the "
                    "region's published total shared by industry value added and the municipality's jobs in each "
                    "industry (real estate by residents)."},
    {"key": "science", "measure": "ICT, professional & business-service jobs", "icon": "y-science", "emoji": "🔬", "label": "Science", "color": "#5aa8e6", "unit": "jobs",
     "groups": ["J", "LMN"],
     "description": "Jobs in information and communication (J) and in real estate, professional, scientific, technical "
                    "and business services (L–N), at the place of work, 2024. L–N is one group because that is the "
                    "finest level all three agencies publish."},
    {"key": "culture", "measure": "culture, recreation & other-service jobs", "icon": "y-culture", "emoji": "🎭", "label": "Culture", "color": "#b07ad9", "unit": "jobs",
     "groups": ["RS"],
     "description": "Jobs in arts, entertainment, recreation and other services (NACE R–U), at the place of work, 2024."},
    {"key": "welfare", "measure": "education, health & social-work jobs", "icon": "i-health", "emoji": "🏥", "label": "Welfare", "color": "#e5707a", "unit": "jobs",
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
