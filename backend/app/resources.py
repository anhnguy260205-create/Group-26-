"""Region-aware support resources — Singapore and Malaysia per the project spec.

Verified via web search (2026) against each organization's own site. Hotline numbers
change; re-verify before any real demo or deployment rather than trusting this list blindly.
"""

RESOURCES = [
    {
        "name": "Samaritans of Singapore (SOS)",
        "description": "24-hour confidential crisis support for anyone in emotional distress or having suicidal thoughts.",
        "contact": "Call 1-767 (24hr) or WhatsApp CareText at 9151 1767 (24hr)",
        "region": "Singapore",
        "category": "crisis",
    },
    {
        "name": "Caregivers Alliance Limited (CAL)",
        "description": "Support and training for caregivers of persons with mental health conditions or dementia.",
        "contact": "Dementia caregiver hotline: 6377 0700 · cal.org.sg",
        "region": "Singapore",
        "category": "caregiver_support",
    },
    {
        "name": "Agency for Integrated Care (AIC)",
        "description": "Government-linked one-stop resource for eldercare, caregiver support schemes, and care services navigation.",
        "contact": "aic.sg — see site for current Careline number",
        "region": "Singapore",
        "category": "caregiver_support",
    },
    {
        "name": "Befrienders Kuala Lumpur",
        "description": "24-hour free, confidential emotional support for anyone feeling distressed, depressed, or suicidal. Nationwide via 9 centres under the National Council of Befrienders Malaysia.",
        "contact": "Call 03-7627 2929 (24hr) · befrienders.org.my",
        "region": "Malaysia",
        "category": "crisis",
    },
    {
        "name": "Malaysian Mental Health Association (MMHA)",
        "description": "Mental health information, support, and referrals.",
        "contact": "+603-2780 6803 or +6017-613 3039 (Mon-Fri, 9am-5pm) · mmha.org.my",
        "region": "Malaysia",
        "category": "caregiver_support",
    },
]

# Deterministic crisis-line pointer used by the Companion's rule-based safety net —
# kept separate from the full RESOURCES list so it can't accidentally be filtered out.
CRISIS_LINES = {
    "Singapore": "Samaritans of Singapore (SOS): call 1-767 (24hr), or WhatsApp 9151 1767",
    "Malaysia": "Befrienders Kuala Lumpur: call 03-7627 2929 (24hr)",
}


def list_resources(region: str | None = None) -> list[dict]:
    if not region or region.lower() == "all":
        return RESOURCES
    return [r for r in RESOURCES if r["region"].lower() == region.lower()]
