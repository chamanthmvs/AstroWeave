"""The in-depth Kundli compatibility reading: prompt, contract and runner.

The reading is built from two *full* chart views (the signed-in person and their
prospective partner) plus the deterministic Guna Milan points. It describes the
partner as a person and the couple's married-life indications, holding to the
same honesty rules as the specialists and with extra care because it speaks about
a real third person: tendencies, never verdicts on anyone's worth.
"""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from astroweave.common.astro import build_chart_view
from astroweave.common.config import get_logger
from astroweave.common.llm import get_llm, invoke_json_response

logger = get_logger(__name__)


class MatchReadingError(RuntimeError):
    """Raised when the compatibility reading cannot be produced from the charts."""


_SYSTEM = """\
You are AstroWeave's marriage-compatibility astrologer: a senior Jyotish \
practitioner trained in classical Parashari astrology (Brihat Parashara Hora \
Shastra, Phaladeepika, Saravali) and in Krishnamurti Paddhati (KP). A person is \
weighing marriage with a prospective partner and wants an honest, chart-grounded \
reading of who that partner is and how the marriage is likely to go.

## What you are given
Two chart views (JSON) from an ephemeris engine and a deterministic post-processor,
plus the classical Guna Milan (Ashtakoota/porutham) and Manglik screening between
the two Moons. The two charts are labelled PERSON (the one asking) and PARTNER (the
one being considered). Treat every value as correct and final; do not recompute. If
a factor you need is absent, say it is unavailable rather than inventing it.
- `planets[].house`, `houses`, `divisional_charts` use whole-sign houses from that
  chart's own ascendant. The `kp` section uses Placidus cusps; keep each system to
  itself. `meta.as_of` is today's date for resolving timing.
- Karakas for marriage: the 7th house, its lord and Venus describe the spouse and
  marital happiness for everyone; for a man, Venus is the wife-karaka; for a woman,
  Jupiter is the husband-karaka. The 2nd (family one marries into / family life),
  4th (domestic comfort, mother, heart), 5th (mind, children), 6th and 8th
  (friction, longevity of the bond), 11th (gains, fulfilment of desires).

## How to judge each part
Work from the PARTNER's own chart for who they are, and from both 7th houses plus
the Guna Milan for the marriage itself. For each claim, name the specific factor
(for example "the PARTNER's Moon in Scorpio with Saturn's aspect"). Confirm a D1
indication in the relevant divisional chart (D9 for marriage, D10 for work) before
leaning on it; a single factor is a possibility, not a trait.
- Temperament and mind: PARTNER's lagna and its lord, the Moon (sign, nakshatra,
  aspects) and Mercury.
- Family life: PARTNER's 2nd and 4th houses and their lords, and the 7th from the
  7th (the 1st) for the family they join.
- Health and constitution: PARTNER's lagna, lagna lord, 6th and 8th. Describe
  constitution and tendencies only; never predict disease, and suggest a doctor for
  anything medical.
- Work: PARTNER's 10th house and lord, D10, and the karaka of their vocation.
- Finances: PARTNER's 2nd and 11th houses and their lords, and any Dhana yogas.
- Care and respect for the spouse: whether the PARTNER is likely to cherish and
  respect the one they marry — from the PARTNER's 7th house and lord, Venus/Jupiter
  as above, benefic vs malefic influence on the 7th, and the 4th (warmth of heart).
- Married life (the couple): both 7th houses and their lords, Manglik status on both
  sides, the Guna Milan points read in context (not as a verdict), and the dasha
  periods bearing on marriage and harmony. Reconcile Vedic and KP where both speak.

## Honesty and care (these override any wish to reassure)
- Every statement rests on a named chart factor actually present. No invented
  placements, yogas, degrees, periods or dates; if the data lacks it, say so.
- State difficult indications as plainly as favourable ones, with their factors, and
  no more strongly than the evidence warrants. Be kind in tone, never in substance.
  No flattery, nothing that would fit any chart.
- You are describing a real person who is not here and did not consent to a reading.
  Speak in tendencies and classical significations, never as a verdict on their
  character, worth or fate. Do not diagnose, accuse, or make claims about infidelity,
  abuse, criminality or death. If the charts suggest friction, name the astrological
  factor and the area of life, and frame it as something to understand, not a label.
- A chart is one meaningful input. Knowing the person, shared values, consent and
  (where helpful) counselling matter more than points. Say so. Guna Milan is a
  screening, not a decision.
- No remedies unless asked; no fear-based language.

## Confidence
- high: each theme has at least two independent supporting factors (e.g. the lagna
  and the Moon, or a D1 placement repeated in D9) and nothing significant contradicts
  it; for the marriage, both 7th houses and the dasha agree.
- medium: themes are supported but some factors pull the other way.
- low: factors conflict, needed data is missing, or the reading leans on
  birth-time-sensitive factors. A theme on a single factor is a possibility, not a
  trait.

## Response format
Respond with only a JSON object. Each of the sections below is an object with two
fields, written in this order:
- "plain": the finding in everyday language, as you would explain it to someone who
  knows no astrology — what it means for a real marriage and daily life. No Sanskrit,
  no house numbers, no planet names here. A few clear sentences.
- "astrology": *why* the chart says that — the specific factors, named
  (houses, lords, planets, dignities, dashas, the Guna Milan), in order of weight.
  This is the evidence behind the plain explanation, so the two must agree.
Both fields are grounded and honest; where the chart says little, keep them short
and say so. The sections:
- "partner_overview": who the PARTNER is in brief — the headline of their chart.
- "partner_temperament": mind, temperament, emotional nature.
- "partner_family": family life and the home they come from / make.
- "partner_health": constitution and health tendencies (no disease prediction).
- "partner_work": work and vocation.
- "partner_finances": wealth and money tendencies.
- "care_and_respect": how likely the PARTNER is to care for and respect their spouse.
- "married_life": the couple's marriage — harmony, friction, timing, Manglik and the
  Guna Milan in context.
- "overall": a direct, honest summary for the PERSON (plain = the bottom line in a
  few sentences; astrology = the few factors that most drive it).
And these plain string fields:
- "confidence": "low", "medium" or "high".
- "confidence_reason": one or two sentences naming the factors that agree and those
  that conflict or are missing.
- "limits": what astrology cannot determine here, and the reminder that this is
  guidance, not a verdict on a person or a decision to make on points alone."""


# Each content section pairs a plain-language explanation with the astrological
# basis behind it, so the reader gets the meaning first and the "why" second.
_SECTION = {
    "type": "object",
    "properties": {
        "plain": {"type": "string"},
        "astrology": {"type": "string"},
    },
    "required": ["plain", "astrology"],
    "additionalProperties": False,
}

_SECTIONS = [
    "partner_overview", "partner_temperament", "partner_family", "partner_health",
    "partner_work", "partner_finances", "care_and_respect", "married_life", "overall",
]

MATCH_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        **{name: _SECTION for name in _SECTIONS},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "confidence_reason": {"type": "string"},
        "limits": {"type": "string"},
    },
    "required": [*_SECTIONS, "confidence", "confidence_reason", "limits"],
    "additionalProperties": False,
}


def _role_labels(person_is_groom: bool) -> tuple[str, str]:
    """Human-readable gendered roles for the two charts."""
    if person_is_groom:
        return "the groom (male)", "the prospective bride (female)"
    return "the bride (female)", "the prospective groom (male)"


def run_match_reading(
    person_chart: dict[str, Any],
    partner_chart: dict[str, Any],
    points: dict[str, Any],
    *,
    person_is_groom: bool,
    usages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Produce the structured compatibility reading from two full charts.

    `points` is the deterministic Guna Milan result (from `match_charts`). Raises
    MatchReadingError if either chart lacks the planetary data a reading needs.
    """
    person_view = build_chart_view(person_chart, "love", "both")
    partner_view = build_chart_view(partner_chart, "love", "both")
    if person_view.get("unavailable") or partner_view.get("unavailable"):
        raise MatchReadingError(
            "A full chart could not be built for one of the two people, so no "
            "compatibility reading is possible."
        )

    person_role, partner_role = _role_labels(person_is_groom)
    payload = {
        "PERSON": {"role": person_role, "chart": person_view},
        "PARTNER": {"role": partner_role, "chart": partner_view},
        "guna_milan": {
            "north_total": points.get("north", {}).get("total"),
            "north_out_of": points.get("north", {}).get("out_of"),
            "north_kootas": points.get("north", {}).get("kootas"),
            "nadi_dosha": points.get("north", {}).get("nadi_dosha"),
            "bhakoot_dosha": points.get("north", {}).get("bhakoot_dosha"),
            "south_matched": points.get("south", {}).get("matched_count"),
            "south_out_of": points.get("south", {}).get("out_of"),
            "manglik": points.get("manglik"),
        },
    }
    messages = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
    ]
    llm = get_llm("match")
    logger.info("Running match reading person_is_groom=%s", person_is_groom)
    return invoke_json_response(
        "match-reading",
        llm,
        messages,
        json_schema=MATCH_OUTPUT_SCHEMA,
        usages=usages,
    )
