from __future__ import annotations

import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


STOPWORDS = {
    "a",
    "an",
    "and",
    "after",
    "at",
    "by",
    "during",
    "effect",
    "effects",
    "for",
    "from",
    "in",
    "of",
    "on",
    "the",
    "to",
    "under",
    "with",
}

RESPONSES = ("rate", "growth", "reproduction", "survival", "mechanism")
HYPOTHESES = ("traits", "environment", "wound_type", "geometry", "integration")
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "data" / "screening"


def ascii_text(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def normalize_title(text: str) -> str:
    text = ascii_text(text or "")
    text = text.replace("_", " ")
    text = text.replace("&", " and ")
    text = text.replace("et al.", "et al")
    text = re.sub(r"\.pdf$", " ", text, flags=re.I)
    text = re.sub(r"doi[-: ]\S+", " ", text, flags=re.I)
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def split_author_year_title(text: str) -> tuple[str, str, str]:
    norm = normalize_title(text)
    match = re.search(r"^(.*?)\b((?:19|20)\d{2})\b(.*)$", norm)
    if not match:
        return "", "", norm
    left = match.group(1).strip()
    author = left.split()[0] if left else ""
    return author, match.group(2), match.group(3).strip()


def to_bool(value: str) -> bool:
    return str(value).strip() in {"1", "true", "True", "yes", "Y"}


def content_tokens(text: str, limit: int = 6) -> list[str]:
    out = []
    for tok in normalize_title(text).split():
        if tok in STOPWORDS:
            continue
        if tok.isdigit() and len(tok) == 4:
            continue
        out.append(tok)
        if len(out) >= limit:
            break
    return out


def work_key(row: dict[str, str]) -> str:
    title = row.get("local_filename") or row.get("source_title") or ""
    author, year, rest = split_author_year_title(title)
    parts = [author, year] + content_tokens(rest or title, limit=6)
    return "|".join(part for part in parts if part)


def pick_title(row: dict[str, str]) -> str:
    return row.get("local_filename") or row.get("source_title") or ""


def title_matches(row: dict[str, str], needle: str) -> bool:
    title = normalize_title(pick_title(row))
    rel = normalize_title(row.get("local_relpath", ""))
    source = normalize_title(row.get("source_title", ""))
    return needle in title or needle in rel or needle in source


def parse_candidate_bins(value: str) -> set[str]:
    bins = set()
    for part in (value or "").split("|"):
        part = part.strip().lower()
        if part in RESPONSES:
            bins.add(part)
    return bins


def split_response_and_hypothesis_tags(decision: dict[str, object]) -> tuple[set[str], set[str]]:
    raw_value = decision.get("responses", set())
    if isinstance(raw_value, str):
        raw_iterable = re.split(r"[,|;]\s*", raw_value)
    else:
        raw_iterable = raw_value
    raw_tags = {str(tag).lower() for tag in set(raw_iterable)}
    responses = {tag for tag in raw_tags if tag in RESPONSES}
    hypotheses = {tag for tag in raw_tags if tag in HYPOTHESES}
    return responses, hypotheses


def infer_responses(row: dict[str, str]) -> set[str]:
    bins = set(parse_candidate_bins(row.get("candidate_bins", "")))
    title = normalize_title(pick_title(row))
    notes = normalize_title(row.get("screening_notes", ""))
    text = f"{title} {notes}"

    if any(k in text for k in ("lesion", "wound", "regeneration", "healing", "repair", "tissue loss")):
        bins.add("rate")
    if any(k in text for k in ("growth", "calcification", "colony health", "biomass", "lipid")):
        bins.add("growth")
    if any(k in text for k in ("reproduction", "reproductive", "egg", "fecundity", "gamete", "spawning")):
        bins.add("reproduction")
    if any(k in text for k in ("mortality", "survival", "bleaching", "disease", "partial mortality")):
        bins.add("survival")
    if any(
        k in text
        for k in (
            "immune",
            "microbiome",
            "transcript",
            "histology",
            "ultrastructure",
            "fluorescent",
            "stem",
            "14c",
            "gene expression",
            "physiology",
        )
    ):
        bins.add("mechanism")
    return bins


def infer_hypotheses(row: dict[str, str], responses: set[str]) -> set[str]:
    title = normalize_title(pick_title(row))
    notes = normalize_title(row.get("screening_notes", ""))
    text = f"{title} {notes}"
    hyps = set()
    if any(
        k in text
        for k in (
            "morphology",
            "morphotype",
            "interspecific",
            "species",
            "massive",
            "branching",
            "colony size",
            "depth related variation",
            "trait",
            "polymorphic",
        )
    ):
        hyps.add("traits")
    if any(
        k in text
        for k in (
            "temperature",
            "thermal",
            "heat",
            "warming",
            "ph",
            "co2",
            "acidification",
            "nutrient",
            "sediment",
            "depth",
            "environmental",
            "irradiance",
            "hydrodynamics",
            "flow",
            "ocean warming",
        )
    ):
        hyps.add("environment")
    if any(
        k in text
        for k in (
            "predation",
            "corallivory",
            "fragmentation",
            "breakage",
            "scraping",
            "damage",
            "injury",
            "wound type",
            "grazing",
            "snail",
        )
    ):
        hyps.add("wound_type")
    if any(k in text for k in ("shape", "perimeter", "surface area", "size and shape", "lesion size")):
        hyps.add("geometry")
    if any(
        k in text
        for k in (
            "integration",
            "translocation",
            "resource allocation",
            "reproductive integration",
            "stem cell",
            "energy allocation",
        )
    ):
        hyps.add("integration")
    if "reproduction" in responses and ("integration" in text or "allocation" in text):
        hyps.add("integration")
    return hyps


def base_decision(row: dict[str, str]) -> dict[str, object]:
    bucket = row.get("screening_bucket", "")
    responses = infer_responses(row)

    if to_bool(row.get("conflicting_audits", "0")):
        return {
            "final_status": "review_needed",
            "extraction_readiness": "needs_adjudication",
            "responses": responses,
            "basis": "conflicted_prior_audit",
            "rationale": row.get("screening_notes", ""),
        }
    if bucket == "include_primary":
        return {
            "final_status": "include_primary",
            "extraction_readiness": "ready_extract",
            "responses": responses,
            "basis": "carry_forward_prior_audit",
            "rationale": row.get("screening_notes", ""),
        }
    if bucket == "include_primary_needs_fulltext":
        return {
            "final_status": "include_primary",
            "extraction_readiness": "needs_digitization",
            "responses": responses,
            "basis": "carry_forward_prior_audit",
            "rationale": row.get("screening_notes", ""),
        }
    if bucket == "include_primary_conflicted":
        return {
            "final_status": "review_needed",
            "extraction_readiness": "needs_adjudication",
            "responses": responses,
            "basis": "conflicted_prior_audit",
            "rationale": row.get("screening_notes", ""),
        }
    if bucket == "include_mechanism_only":
        responses.add("mechanism")
        return {
            "final_status": "include_mechanism_only",
            "extraction_readiness": "not_for_extraction",
            "responses": responses,
            "basis": "carry_forward_prior_audit",
            "rationale": row.get("screening_notes", ""),
        }
    if bucket == "exclude_scope":
        return {
            "final_status": "exclude_scope",
            "extraction_readiness": "not_for_extraction",
            "responses": responses,
            "basis": "carry_forward_prior_audit",
            "rationale": row.get("screening_notes", ""),
        }
    if bucket == "exclude_review":
        return {
            "final_status": "exclude_review",
            "extraction_readiness": "not_for_extraction",
            "responses": responses,
            "basis": "carry_forward_prior_audit",
            "rationale": row.get("screening_notes", ""),
        }
    return {
        "final_status": "review_needed",
        "extraction_readiness": "needs_adjudication",
        "responses": responses,
        "basis": "bucket_default",
        "rationale": row.get("screening_notes", ""),
    }


MANUAL_RULES: list[tuple[str, dict[str, object]]] = [
    # Explicit duplicates first.
    ("counsell et al 2019 colony size and depth affect wound repair in a bra", {
        "predicate": "only_truncated_counsell",
        "final_status": "duplicate_alias",
        "alias_of": "Counsell et al. - 2019 - Colony size and depth affect wound repair in a branching coral.pdf",
        "extraction_readiness": "not_for_extraction",
        "responses": {"rate", "survival"},
        "basis": "manual_override",
        "rationale": "Truncated local duplicate of the full Counsell et al. 2019 paper.",
    }),
    ("injury and regeneration of common reef crest corals", {
        "predicate": "duplicate_if_notebook_absent_and_not_hall_prefix",
        "final_status": "duplicate_alias",
        "alias_of": "Hall_Injury_and_regeneration_of_common_reef-crest_corals.pdf",
        "extraction_readiness": "not_for_extraction",
        "responses": {"rate", "growth", "reproduction"},
        "basis": "manual_override",
        "rationale": "Duplicate local copy of Hall's reef-crest coral injury thesis.",
    }),
    ("traylor knowles 2016 distinctive wound healing characteristics in the c", {
        "predicate": "only_truncated_traylor",
        "final_status": "duplicate_alias",
        "alias_of": "Traylor-Knowles - 2016 - Distinctive wound-healing characteristics in the corals Pocillopora damicornis and Acropora hyacinth.pdf",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Truncated duplicate of the full Traylor-Knowles wound-healing paper.",
    }),
    ("lock quantifying physiological responses to physical injury in porites lobata", {
        "final_status": "duplicate_alias",
        "alias_of": "Lock et al. - 2022 - Calcium homeostasis disruption initiates rapid growth after micro‐fragmentation in the scleractinian.pdf",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Project/proposal-style duplicate linked to the later published Lock et al. paper.",
    }),
    # Conflicted / unresolved includes.
    ("counsell et al 2019 colony size and depth affect wound repair in a branching coral", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "survival"},
        "basis": "manual_override",
        "rationale": "Primary field experiment on Pocillopora meandrina wound healing time and partial mortality; include for healing and survival even though extraction will rely on full-text values/time-to-heal endpoints.",
    }),
    ("fine et al 2002 bleaching effect on regeneration and resource translocation", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "survival", "mechanism"},
        "basis": "manual_override",
        "rationale": "Primary lesion-recovery experiment contrasting bleached and unbleached Oculina patagonica; also central for colony-integration mechanism.",
    }),
    ("hall 1997 interspecific differences in the regeneration of artificial injuries", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Core comparative regeneration dataset across multiple scleractinian morphologies and injury types.",
    }),
    ("hall et al 2015 lesion recovery of two scleractinian corals under low ph conditions", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "environment"},
        "basis": "manual_override",
        "rationale": "Primary lesion-recovery study under ocean acidification; include for the environmental-stress hypothesis.",
    }),
    ("meesters et al 1992 sedimentation and lesion position", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "environment"},
        "basis": "manual_override",
        "rationale": "Primary regeneration study testing sedimentation and lesion position effects on healing.",
    }),
    ("nagelkerken et al 1999 depth related variation in regeneration", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "environment", "traits"},
        "basis": "manual_override",
        "rationale": "Primary depth-gradient lesion-regeneration study in Porites astreoides and Stephanocoenia michelinii.",
    }),
    ("rice et al 2021 complex interactions with nutrients and sediment", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "survival"},
        "basis": "manual_override",
        "rationale": "Primary multi-stressor corallivory paper linking nutrients and sediment to tissue-loss and recovery outcomes.",
    }),
    ("soong and lang 1992 reproductive integration in reef corals", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"reproduction", "mechanism"},
        "basis": "manual_override",
        "rationale": "Primary reproductive-cost paper central to colony integration and trade-off hypotheses.",
    }),
    ("titlyanov and titlyanova 2009 the dynamics of the restoration of mechanical damage", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary regeneration study focused on Porites mechanical damage and restoration dynamics.",
    }),
    ("van woesik 1998 lesion healing on massive porites", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "geometry"},
        "basis": "manual_override",
        "rationale": "Classic Porites lesion-healing paper with exponential models and lesion-size dependence.",
    }),
    # Needs full text but clearly primary.
    ("bak 1983 neoplasia regeneration and growth in the reef building coral acropora palmata", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "growth"},
        "basis": "manual_override",
        "rationale": "Foundational Acropora palmata injury, regeneration, and growth study.",
    }),
    ("hall 2001 the response of acropora hyacinthus and montipora tuberculosa to three different types of colony damage", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary comparison of scraping, tissue damage, and branching loss across colony-damage types.",
    }),
    ("horwitz and fine 2014 high co2 detrimentally affects tissue regeneration", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary ocean-acidification paper on tissue regeneration under elevated CO2.",
    }),
    ("lenihan and edmunds 2010 response of pocillopora verrucosa to corallivory varies with environmental conditions", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "growth"},
        "basis": "manual_override",
        "rationale": "Primary corallivory-response paper combining wound outcomes with environmental context.",
    }),
    ("meesters et al 1994 damage and regeneration links to growth", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "growth"},
        "basis": "manual_override",
        "rationale": "Core trade-off paper linking lesion healing to colony growth in Montastrea annularis.",
    }),
    ("meesters et al 1996 partial mortality in three species of reef building corals", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"survival", "traits"},
        "basis": "manual_override",
        "rationale": "Primary partial-mortality paper relevant to the survival consequences of damage and morphology.",
    }),
    ("oren et al 2001 colony integration during regeneration in the stony coral favia favus", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "mechanism"},
        "basis": "manual_override",
        "rationale": "Primary regeneration and colony-integration experiment central to the translocation hypothesis.",
    }),
    ("rice et al 2019 different nitrogen sources speed recovery from corallivory", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "mechanism"},
        "basis": "manual_override",
        "rationale": "Primary corallivory-recovery paper with nutrient-source effects on wound outcomes and microbiome.",
    }),
    ("sabine et al 2015 environmental conditions influence tissue regeneration rates", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary tissue-regeneration study designed around environmental drivers of healing.",
    }),
    ("titlyanov et al 2005 regeneration of artificial injuries", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary artificial-injury regeneration dataset with coral-algal competition context.",
    }),
    ("titlyanov et al 2006 three stages of injuries regeneration", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "mechanism"},
        "basis": "manual_override",
        "rationale": "Primary staged-regeneration paper relevant to both wound dynamics and mechanism narrative.",
    }),
    ("townsend et al 2023 differing lesion recovery rates of two caribbean stony coral species", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary comparative lesion-recovery study across depth/habitat.",
    }),
    # Review_fulltext_needed decisions.
    ("brush 2024 ecology of fishes and invertebrates inhabiting", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Community-ecology dissertation on reef associates rather than coral wounding responses.",
    }),
    ("burmester et al 2018 the impact of autotrophic versus heterotrophic nutritional pathways", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "growth"},
        "basis": "manual_override",
        "rationale": "Primary wound-recovery and colony-health paper in Astrangia; retain even though many effect sizes will need extraction from figures.",
    }),
    ("chadwick and loya 1990 regeneration after experimental breakage", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "survival"},
        "basis": "manual_override",
        "rationale": "Primary breakage-regeneration experiment in Fungia granulosa.",
    }),
    ("cox 2014 corallivory the coral s point of view", {
        "final_status": "exclude_review",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Narrative review chapter on corallivory rather than a primary wound-response dataset.",
    }),
    ("defilippo et al 2016 patterns of surface lesion recovery", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary Astrangia lesion-recovery paper with direct wound-healing outcomes.",
    }),
    ("dias et al 2018 mortality growth and regeneration following fragmentation", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "growth", "survival"},
        "basis": "manual_override",
        "rationale": "Primary fragmentation paper covering mortality, growth, and regeneration under heat stress.",
    }),
    ("doo et al 2018 obligate ectosymbionts increase the physiological", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Physiology under ectosymbiont presence and stress, but not a wound-response paper.",
    }),
    ("edmunds and burgess 2017 colony size and turbulent flow speed modulate", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Performance paper without physical injury or regeneration outcomes.",
    }),
    ("edmunds et al 2025 a physiological crisis drives the coral recruitmen", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Recruitment/thermal-stress paper rather than post-injury healing or fitness costs of wounding.",
    }),
    ("enochs and glynn 2017 corallivory in the eastern pacific", {
        "final_status": "exclude_review",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Review chapter on eastern Pacific corallivory.",
    }),
    ("hamman 2019 spatial distribution of damage affects the healing growth and morphology", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "growth"},
        "basis": "manual_override",
        "rationale": "Primary experimental paper testing spatial distribution of damage on healing and growth.",
    }),
    ("honeycutt et al 2023 farmerfish gardens help buffer stony corals agains", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Heatwave-buffering ecology paper without direct wounding treatments or lesion outcomes.",
    }),
    ("jayewardene 2010 experimental determination of the cost of lesion healing", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"growth", "rate"},
        "basis": "manual_override",
        "rationale": "Primary experimental test of growth costs during lesion healing in Porites compressa.",
    }),
    ("jayewardene et al 2009 effects of frequent fish predation on corals in hawaii", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"growth", "survival"},
        "basis": "manual_override",
        "rationale": "Primary corallivory paper on repeated fish damage and colony consequences.",
    }),
    ("jones and barott 2025 evidence of rare occurrences of the phoenix effect", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Recovery-after-bleaching paper without a physical injury treatment.",
    }),
    ("kaufman et al 2021 thermal history influences lesion recovery", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary Acropora cervicornis lesion-recovery note under heat stress.",
    }),
    ("kersting and linares 2019 living evidence of a fossil survival strategy", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Climate-survival narrative centered on whole-colony persistence rather than lesion-response data.",
    }),
    ("kokita and nakazono 2001 rapid response of an obligately corallivorous filefish", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Predator-behavior paper without coral healing, growth, or survival outcomes.",
    }),
    ("kramarsky winter and loya 2000 tissue regeneration in the coral fungia granulosa", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary regeneration paper on extrinsic and intrinsic controls in Fungia granulosa.",
    }),
    ("lenihan et al 2015 hydrodynamics influence coral performance", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"growth", "survival"},
        "basis": "manual_override",
        "rationale": "Primary field assay showing indirect corallivory effects on coral growth under different flow regimes.",
    }),
    ("leuzinger et al 2012 energy allocation in a reef coral under varying resource availability", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Energy-allocation paper not tied to physical injury or lesion regeneration.",
    }),
    ("lirman et al 2010 propagation of the threatened staghorn coral acropora cervicornis", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"growth", "survival"},
        "basis": "manual_override",
        "rationale": "Primary propagation/fragmentation methods paper with direct growth and survivorship consequences of collection damage.",
    }),
    ("loya 1976 skeletal regeneration in a red sea scleractinian coral population", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Early primary regeneration study on skeletal/tissue repair in Red Sea scleractinians.",
    }),
    ("luz et al 2018 a polyp from nothing", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Extreme whole-polyp regeneration in sun corals is outside the lesion-healing comparability needed here.",
    }),
    ("luz et al 2021 high regenerative capacity is a general feature within colonial dendrophylliid corals", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Broad regenerative-capacity paper on dendrophylliids rather than lesion-healing outcomes in the focal wound framework.",
    }),
    ("nagelkerken and bak 1998 differential regeneration of artificial lesions", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "traits"},
        "basis": "manual_override",
        "rationale": "Primary lesion-regeneration comparison among sympatric Porites morphs.",
    }),
    ("nicolet et al 2018 predation scars may influence host susceptibility to pathogens", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"survival", "mechanism"},
        "basis": "manual_override",
        "rationale": "Primary test of whether corallivore scars alter pathogen susceptibility; relevant to wound consequences via disease risk.",
    }),
    ("okubo 2008 size independent investment allocation to regeneration and growth", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "growth"},
        "basis": "manual_override",
        "rationale": "Primary branching-coral experiment on regeneration versus growth allocation.",
    }),
    ("oren et al 1997 effect of lesion size and shape on regeneration", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "geometry"},
        "basis": "manual_override",
        "rationale": "Core lesion geometry paper for Favia favus.",
    }),
    ("oren et al 1998 prudent sessile feeding by the corallivore snail", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Predator-behavior/energy-sink paper useful for narrative context, but not an extractable wound-response dataset.",
    }),
    ("page and willis 2008 epidemiology of skeletal eroding band", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"survival", "mechanism"},
        "basis": "manual_override",
        "rationale": "Injury-initiation experiment relevant to disease-mediated consequences of damage, with lesion progression rates.",
    }),
    ("palacios et al 2014 fish corallivory on a pocilloporid reef", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"growth", "survival"},
        "basis": "manual_override",
        "rationale": "Primary corallivory-response paper linking predation to coral performance.",
    }),
    ("pavia jr and estacion 2019 survival and growth of isolated polyps", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Isolated-polyp culture paper outside the lesion-healing framework.",
    }),
    ("pisapia et al 2016 temporal consistency in background mortality", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Background mortality monitoring without an injury treatment or wound-response endpoint.",
    }),
    ("rapuano et al 2023 coming of age annual onset of coral reproduction", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Reproductive timing paper not tied to physical damage or regeneration.",
    }),
    ("raymundo et al 2016 effects of coralliophila violacea on tissue loss", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"survival", "growth"},
        "basis": "manual_override",
        "rationale": "Primary corallivore tissue-loss study relevant to wound consequences and colony performance.",
    }),
    ("sani et al 2024 ocean warming and acidification detrimentally affect coral tissue regeneration", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary Mediterranean regeneration experiment under warming and acidification.",
    }),
    ("titlyanov and titlyanova 2008 coral algal competition on damaged reefs", {
        "final_status": "exclude_review",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Review article on damaged reefs and coral-algal competition.",
    }),
    ("traylor knowles 2016 distinctive wound healing characteristics in the corals pocillopora damicornis", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Mechanistic wound-healing comparison emphasizing cellular and immune characteristics rather than extractable macro-rate data.",
    }),
    ("van veghel and bak 1994 reproductive characteristics of the polymorphic caribbean reef building coral montastrea annularis", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"reproduction"},
        "basis": "manual_override",
        "rationale": "Primary reproductive-cost paper used to quantify fecundity differences near lesions.",
    }),
    ("ward 1995 the effect of damage on the growth reproduction and storage of lipids", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"growth", "reproduction", "survival"},
        "basis": "manual_override",
        "rationale": "Primary damage-cost experiment covering growth, lipids, reproduction, and mortality.",
    }),
    ("welsh et al 2015 clustered parrotfish feeding scars trigger partial coral mortality", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"survival"},
        "basis": "manual_override",
        "rationale": "Primary field note on scar clustering and partial mortality in Porites.",
    }),
    ("wolf and nugues 2013 synergistic effects of algal overgrowth and corallivory", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"survival", "growth"},
        "basis": "manual_override",
        "rationale": "Primary multi-stressor paper on corallivory and algal overgrowth effects on reef-building corals.",
    }),
    # Review_needed decisions.
    ("bak and es regeneration of superficial damage in the scleractinian corals", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "survival"},
        "basis": "manual_override",
        "rationale": "Foundational early study on superficial-damage regeneration in Agaricia and Porites.",
    }),
    ("barrientos lujan et al 2019 ecological and functional diversity of gastropods", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Gastropod diversity paper, not a coral wound-response study.",
    }),
    ("biscere et al 2018 enhancement of coral calcification", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Calcification physiology without a wound or lesion treatment.",
    }),
    ("brown et al 2021 extended phenotypes on coral reefs cryptic phenotypes modulate coral vermetid interactions", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Interaction ecology paper without physical injury or regeneration endpoints.",
    }),
    ("bruckner et al 2000 parrotfish predation on live coral spot biting and focused biting", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Predation-description paper lacking coral healing or post-damage consequence measurements.",
    }),
    ("brush 2025 assemblage structure of fishes and invertebrates", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Community-structure study unrelated to coral wound responses.",
    }),
    ("buck wiese et al 2018 patterns in sexual reproduction", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Sexual-reproduction paper without a damage treatment.",
    }),
    ("coral damsel wounding manuscript", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "growth"},
        "basis": "manual_override",
        "rationale": "Unpublished/grey-literature manuscript with direct wound-healing and photosynthetic recovery outcomes in Pocillopora.",
    }),
    ("coral regeneration review annual review marine science", {
        "final_status": "exclude_review",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Annual Review manuscript; narrative synthesis rather than extractable primary data.",
    }),
    ("counsell 2018 assembly dynamics for a coral associated reef comm", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Community-assembly dissertation unrelated to wound responses.",
    }),
    ("croquer et al 2002 environmental factors affecting tissue regeneration", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary environmental-effects paper on tissue regeneration in Montastraea annularis.",
    }),
    ("cunning et al 2018 comparative analysis of the pocillopora damicornis genome", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Genome paper not tied to physical injury or regeneration measurements.",
    }),
    ("da silveira and van t hof 1977 regeneration in the gorgonian", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Octocoral/gorgonian study outside the scleractinian scope.",
    }),
    ("denis 2013 fast growth may impair regeneration capacity", {
        "final_status": "include_primary",
        "extraction_readiness": "ready_extract",
        "responses": {"rate", "growth"},
        "basis": "manual_override",
        "rationale": "Primary Porites lutea study directly linking growth to regeneration capacity.",
    }),
    ("e and y 1996 regeneration versus budding in fungiid corals", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "growth"},
        "basis": "manual_override",
        "rationale": "Primary fungiid paper on regeneration versus budding trade-offs following damage.",
    }),
    ("edmunds and burgess 2016 size dependent physiological responses", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Physiology paper without injury or lesion endpoints.",
    }),
    ("edmunds et al 2018 density dependence mediates coral assemblage struc", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Assemblage-structure paper unrelated to wound healing.",
    }),
    ("eh and rpm 1995 age related deterioration of a physiological function", {
        "final_status": "include_primary",
        "extraction_readiness": "ready_extract",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary Acropora palmata paper quantifying age-related regeneration decline.",
    }),
    ("eh et al 1997 predicting regeneration of physical damage", {
        "final_status": "include_primary",
        "extraction_readiness": "ready_extract",
        "responses": {"rate", "geometry"},
        "basis": "manual_override",
        "rationale": "Primary predictive regeneration paper using lesion shape and regeneration capacity.",
    }),
    ("fox et al 2019 trophic plasticity in a common reef building coral", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Trophic ecology paper without injury treatment.",
    }),
    ("furby et al 2014 incidence of lesions on fungiidae corals", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Lesion-incidence survey rather than a regeneration or consequence study.",
    }),
    ("gardner et al 2019 coral microbiome diversity reflects mass coral ble", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Bleaching susceptibility paper without wounding treatment.",
    }),
    ("glynn et al 2025 the role of holobiont composition and environmenta", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Thermotolerance/holobiont paper not centered on injury or repair.",
    }),
    ("guzman et al 1994 injury regeneration and growth of caribbean reef corals after a major oil spill", {
        "final_status": "include_primary",
        "extraction_readiness": "ready_extract",
        "responses": {"rate", "growth", "survival"},
        "basis": "manual_override",
        "rationale": "Primary post-disturbance injury, regeneration, and growth study in Caribbean corals.",
    }),
    ("hall injury and regeneration of common reef crest corals", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate", "growth", "reproduction"},
        "basis": "manual_override",
        "rationale": "Hall thesis with primary reef-crest coral damage, regeneration, and fecundity datasets that underpin several later papers.",
    }),
    ("han et al 2025 in depth single cell transcriptomic exploration of the regenerative dynamics", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Single-cell regenerative dynamics paper for mechanistic synthesis, not macro-response extraction.",
    }),
    ("jayewardene and birkeland 2006 fish predation on hawaiian corals", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Predation-description paper lacking direct coral healing or fitness outcome data.",
    }),
    ("kordas et al 2011 community ecology in a warming world", {
        "final_status": "exclude_review",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "General review on warming and species interactions.",
    }),
    ("levanoni 2021 coral tissue growth and regeneration conjoin the advent of adult stem cell like cells", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Stem-cell regeneration thesis relevant to mechanisms rather than pooled macro endpoints.",
    }),
    ("lock et al 2022 calcium homeostasis disruption initiates rapid growth", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Mechanistic micro-fragmentation paper emphasizing physiology and gene regulation.",
    }),
    ("mass et al 2016 temporal and spatial expression patterns of biomin", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Developmental biomineralization paper rather than post-injury repair.",
    }),
    ("miller and hay 1998 effects of fish predation and seaweed competition", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"growth", "survival"},
        "basis": "manual_override",
        "rationale": "Primary experiment on predation and seaweed competition affecting coral growth and survival.",
    }),
    ("palacio castro et al 2023 increased dominance of heat tolerant symbionts", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Symbiont/heat paper without injury treatment.",
    }),
    ("palmer et al 2011 corals use similar immune cells and wound healing processes", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Important mechanistic wound-healing paper with immune-cell focus.",
    }),
    ("paz garcia 2006 temporal variation in the regeneration rate of artificial lesions", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"rate"},
        "basis": "manual_override",
        "rationale": "Primary regeneration-rate paper in Porites panamensis morphotypes.",
    }),
    ("pogoreutz et al 2017 sugar enrichment provides evidence", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Nitrogen-fixation/sugar-enrichment physiology study without injury treatment.",
    }),
    ("putnam and gates 2015 preconditioning in the reef building coral", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Preconditioning/thermal-acclimation study not centered on wounding.",
    }),
    ("renegar 2015 histology and ultrastructure of montastraea cavernosa and porites astreoides during regeneration", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Dissertation focused on histology and ultrastructure during regeneration and recruitment.",
    }),
    ("renegar et al coral ultrastructural response to elevated pco2 and nutrients during tissue repair and regeneration", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Ultrastructural/tissue-repair paper better suited for mechanistic narrative than pooled macro endpoints.",
    }),
    ("rinkevich 1996 do reproduction and regeneration in damaged corals compete for energy allocation", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Conceptual note framing the regeneration-reproduction trade-off; useful for hypothesis context, not effect-size extraction.",
    }),
    ("rodriguez villalobos et al 2015 explained and unexplained tissue loss in corals", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Tissue-loss epidemiology paper rather than an experimental wound-response study.",
    }),
    ("rodriguez villalobos et al 2016 wound repair in pocillopora", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Wound-repair paper focused on mechanistic/histological characterization in Pocillopora.",
    }),
    ("roff et al 2014 porites and the phoenix effect", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Bleaching-recovery paper without a physical injury treatment.",
    }),
    ("samsuri et al 2018 the effectiveness of trapezia cymodoce", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Defensive-symbiont/predation ecology paper without direct healing measurements.",
    }),
    ("shantz et al 2023 positive interactions between corals and damselfis", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Damselfish interaction paper not centered on injury response.",
    }),
    ("sogin et al 2016 metabolomic signatures of increases in temperature", {
        "final_status": "exclude_scope",
        "extraction_readiness": "not_for_extraction",
        "responses": set(),
        "basis": "manual_override",
        "rationale": "Metabolomic temperature study without physical damage.",
    }),
    ("van de water et al 2015 elevated seawater temperatures have a limited impact on the coral immune response following physical", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Mechanistic immune-response study following physical damage under elevated temperature.",
    }),
    ("van de water et al 2015 the coral immune response facilitates protection against microbes during tissue regeneration", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Mechanistic immune/microbe paper documenting rapid tissue regeneration without pooled macro effect sizes.",
    }),
    ("xu et al 2023 wound healing and regeneration in the reef building coral acropora millepora", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Recent regeneration paper better positioned as mechanism synthesis unless full macro effect sizes are recovered later.",
    }),
    ("yap and gomez 1984 growth of acropora pulchra ii responses of natural and transplanted colonies to temperature and da", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"growth", "survival"},
        "basis": "manual_override",
        "rationale": "Primary damage/transplant study with growth responses under temperature and disturbance.",
    }),
    # Corrections to previously resolved buckets.
    ("shaver et al 2017 effects of predation and nutrient enrichment on the success and microbiome", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"growth", "survival", "mechanism"},
        "basis": "manual_override",
        "rationale": "Primary field experiment showing predation effects on growth, mortality, tissue loss, and microbiome in Acropora cervicornis.",
    }),
    ("rotjan et al 2006 chronic parrotfish grazing impedes coral recovery after bleaching", {
        "final_status": "include_primary",
        "extraction_readiness": "needs_digitization",
        "responses": {"survival", "mechanism"},
        "basis": "manual_override",
        "rationale": "Primary coral-bleaching recovery study where chronic predation worsened post-bleaching performance.",
    }),
    ("maher et al 2019 multiple stressors interact primarily through antagonism to drive changes in the coral microbiome", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Microbiome experiment with simulated predation and heat stress; useful mechanistically but not a core macro-endpoint dataset.",
    }),
    ("madeira et al 2022 does predation exacerbate the risk of endosymbiont loss", {
        "final_status": "include_mechanism_only",
        "extraction_readiness": "not_for_extraction",
        "responses": {"mechanism"},
        "basis": "manual_override",
        "rationale": "Predation-plus-heat physiology paper focused on endosymbiont loss rather than pooled healing/growth endpoints.",
    }),
]


def apply_manual_rule(row: dict[str, str], decision: dict[str, object]) -> dict[str, object]:
    title = normalize_title(pick_title(row))
    for needle, override in MANUAL_RULES:
        needle_norm = normalize_title(needle)
        if needle_norm not in title and needle_norm.replace(" ", "") not in title.replace(" ", ""):
            continue
        predicate = override.get("predicate")
        if predicate == "duplicate_if_notebook_absent_and_not_hall_prefix":
            if to_bool(row.get("notebook_present", "0")):
                continue
            if title.startswith("hall "):
                continue
        if predicate == "only_truncated_counsell":
            if "branching coral" in title:
                continue
        if predicate == "only_truncated_traylor":
            if "pocillopora damicornis and acropora hyacinth" in title:
                continue
        merged = dict(decision)
        merged.update({k: v for k, v in override.items() if k != "predicate"})
        return merged
    return decision


def choose_canonical(indices: list[int], rows: list[dict[str, object]]) -> int:
    def score(i: int) -> tuple[int, int, int, int, int]:
        row = rows[i]
        return (
            1 if row["final_status"] == "include_primary" else 0,
            1 if row.get("source_id") else 0,
            1 if to_bool(str(row.get("notebook_present", "0"))) else 0,
            1 if to_bool(str(row.get("local_present", "0"))) else 0,
            len(str(row.get("paper_title", ""))),
        )

    return sorted(indices, key=score, reverse=True)[0]


def merge_delimited(existing: object, incoming: object, separator: str) -> str:
    seen: set[str] = set()
    merged: list[str] = []
    for value in [str(existing or ""), str(incoming or "")]:
        for part in value.split(separator):
            part = part.strip()
            if not part or part in seen:
                continue
            seen.add(part)
            merged.append(part)
    return separator.join(merged)


def merge_duplicate_evidence(canonical: dict[str, object], duplicate: dict[str, object]) -> None:
    canonical["_responses"] = set(canonical.get("_responses", set())) | set(duplicate.get("_responses", set()))
    canonical["_hypotheses"] = set(canonical.get("_hypotheses", set())) | set(duplicate.get("_hypotheses", set()))
    for field, separator in [
        ("audit_titles", " || "),
        ("audit_verdicts", " || "),
        ("screening_notes", " || "),
        ("final_rationale", " || "),
        ("candidate_bins", "|"),
    ]:
        canonical[field] = merge_delimited(canonical.get(field, ""), duplicate.get(field, ""), separator)
    if to_bool(str(duplicate.get("conflicting_audits", "0"))):
        canonical["conflicting_audits"] = "1"
    try:
        canonical["audit_count"] = str(
            int(str(canonical.get("audit_count", "0") or "0")) + int(str(duplicate.get("audit_count", "0") or "0"))
        )
    except ValueError:
        canonical["audit_count"] = str(canonical.get("audit_count", ""))


def build_outputs(input_csv: Path, output_dir: Path) -> None:
    with input_csv.open(newline="") as f:
        rows = list(csv.DictReader(f))

    adjudicated: list[dict[str, object]] = []
    for row in rows:
        decision = base_decision(row)
        decision = apply_manual_rule(row, decision)
        responses, manual_hypotheses = split_response_and_hypothesis_tags(decision)
        hypotheses = infer_hypotheses(row, responses) | manual_hypotheses

        title = pick_title(row)
        title_norm = normalize_title(title)

        # If a paper is still unresolved here, make a conservative title-based fallback.
        if decision["final_status"] == "review_needed":
            if any(k in title_norm for k in ("review", "annual review", "book chapter")):
                decision["final_status"] = "exclude_review"
                decision["extraction_readiness"] = "not_for_extraction"
                decision["basis"] = "title_keyword_fallback"
                decision["rationale"] = "Title indicates review/synthesis rather than a primary data paper."
                responses = set()
                hypotheses = set()
            elif any(k in title_norm for k in ("gorgonian", "demospong", "gastropod", "genome", "transcriptomic", "assemblage", "microbiome diversity reflects")):
                decision["final_status"] = "exclude_scope"
                decision["extraction_readiness"] = "not_for_extraction"
                decision["basis"] = "title_keyword_fallback"
                decision["rationale"] = "Title indicates taxonomic or topical mismatch with the wound-response data pool."
                responses = set()
                hypotheses = set()
            elif any(k in title_norm for k in ("lesion", "regeneration", "wound", "injury", "healing", "corallivory", "fragmentation", "predation", "repair")):
                decision["final_status"] = "review_needed"
                decision["extraction_readiness"] = "needs_adjudication"
                decision["basis"] = "title_keyword_fallback"
                decision["rationale"] = "Title suggests possible wound-response relevance; full-text adjudication is required before inclusion."

        item = dict(row)
        item["paper_title"] = title
        item["title_normalized"] = title_norm
        item["final_status"] = decision["final_status"]
        item["extraction_readiness"] = decision["extraction_readiness"]
        item["adjudication_basis"] = decision["basis"]
        item["final_rationale"] = str(decision["rationale"]).strip()
        item["alias_of"] = str(decision.get("alias_of", "")).strip()
        item["_responses"] = responses
        item["_hypotheses"] = hypotheses
        adjudicated.append(item)

    # Collapse obvious duplicates after initial decisions.
    groups: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(adjudicated):
        if row["final_status"] in {"exclude_scope", "exclude_review", "duplicate_alias"}:
            continue
        groups[work_key(row)].append(i)

    for _, indices in groups.items():
        if len(indices) < 2:
            continue
        canonical = choose_canonical(indices, adjudicated)
        canonical_title = str(adjudicated[canonical]["paper_title"])
        for i in indices:
            if i == canonical:
                continue
            # Preserve genuinely distinct entries when the titles are not actually near-identical.
            can_norm = str(adjudicated[canonical]["title_normalized"])
            row_norm = str(adjudicated[i]["title_normalized"])
            overlap = len(set(can_norm.split()) & set(row_norm.split()))
            if can_norm != row_norm and overlap < 6:
                continue
            merge_duplicate_evidence(adjudicated[canonical], adjudicated[i])
            adjudicated[i]["final_status"] = "duplicate_alias"
            adjudicated[i]["extraction_readiness"] = "not_for_extraction"
            adjudicated[i]["alias_of"] = canonical_title
            adjudicated[i]["adjudication_basis"] = "duplicate_collapse"
            adjudicated[i]["final_rationale"] = f"Duplicate or alternate copy of {canonical_title}."

    # Build derived columns.
    for row in adjudicated:
        responses = set(row.pop("_responses"))
        hypotheses = set(row.pop("_hypotheses"))
        if row["final_status"] not in {"include_primary", "include_mechanism_only"}:
            responses = set()
            hypotheses = set()
        elif row["final_status"] != "include_primary":
            responses.discard("rate")
            responses.discard("growth")
            responses.discard("reproduction")
            responses.discard("survival")
        if row["final_status"] == "duplicate_alias":
            responses = set()
            hypotheses = set()
        for resp in RESPONSES:
            row[f"response_{resp}"] = 1 if resp in responses else 0
        for hyp in HYPOTHESES:
            row[f"hypothesis_{hyp}"] = 1 if hyp in hypotheses else 0
        title = row["title_normalized"]
        row["moderator_environment"] = 1 if any(
            k in title for k in ("temperature", "thermal", "warming", "ph", "co2", "nutrient", "sediment", "depth", "flow", "irradiance")
        ) else 0
        row["moderator_traits"] = 1 if any(
            k in title for k in ("morphology", "morphotype", "species", "branching", "massive", "colony size", "depth related", "interspecific")
        ) else 0

    output_dir.mkdir(parents=True, exist_ok=True)

    final_csv = output_dir / "SCREENING_LOG_FINAL.csv"
    matrix_csv = output_dir / "HYPOTHESIS_X_RESPONSE_MATRIX.csv"
    rationale_md = output_dir / "INCLUSION_EXCLUSION_RATIONALE.md"

    fieldnames = [
        "paper_title",
        "source_id",
        "notebook_present",
        "local_present",
        "local_relpath",
        "local_filename",
        "current_folder",
        "final_status",
        "extraction_readiness",
        "alias_of",
        "response_rate",
        "response_growth",
        "response_reproduction",
        "response_survival",
        "response_mechanism",
        "moderator_environment",
        "moderator_traits",
        "hypothesis_traits",
        "hypothesis_environment",
        "hypothesis_wound_type",
        "hypothesis_geometry",
        "hypothesis_integration",
        "adjudication_basis",
        "final_rationale",
        "audit_count",
        "audit_titles",
        "audit_verdicts",
        "conflicting_audits",
        "screening_bucket",
        "candidate_bins",
        "screening_notes",
    ]
    with final_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in adjudicated:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    matrix_fields = [
        "paper_title",
        "final_status",
        "extraction_readiness",
        "response_rate",
        "response_growth",
        "response_reproduction",
        "response_survival",
        "response_mechanism",
        "hypothesis_traits",
        "hypothesis_environment",
        "hypothesis_wound_type",
        "hypothesis_geometry",
        "hypothesis_integration",
    ]
    with matrix_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=matrix_fields, lineterminator="\n")
        writer.writeheader()
        for row in adjudicated:
            writer.writerow({k: row.get(k, "") for k in matrix_fields})

    status_counts = Counter(row["final_status"] for row in adjudicated)
    readiness_counts = Counter(row["extraction_readiness"] for row in adjudicated)
    response_counts = Counter()
    for row in adjudicated:
        for resp in RESPONSES:
            if int(row[f"response_{resp}"]) == 1:
                response_counts[resp] += 1

    included_titles = [
        row["paper_title"]
        for row in adjudicated
        if row["final_status"] == "include_primary"
    ]
    mechanism_titles = [
        row["paper_title"]
        for row in adjudicated
        if row["final_status"] == "include_mechanism_only"
    ]

    lines = [
        "# Inclusion / Exclusion Rationale",
        "",
        "## Status Counts",
        "",
    ]
    for key, value in sorted(status_counts.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Extraction Readiness", ""])
    for key, value in sorted(readiness_counts.items()):
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Response Coverage", ""])
    for key in RESPONSES:
        lines.append(f"- `{key}`: {response_counts[key]}")
    lines.extend(
        [
            "",
            "## Adjudication Rules",
            "",
            "- `include_primary`: direct wound-response or damage-consequence paper contributing extractable rate, growth, reproduction, or survival outcomes.",
            "- `include_mechanism_only`: relevant to mechanism, physiology, microbiology, or immune response during regeneration, but not treated as a pooled effect-size source for the core outcome families.",
            "- `exclude_scope`: outside the topical or taxonomic scope of the wound-response pool.",
            "- `exclude_review`: review, synthesis, assay protocol, or commentary without primary extractable outcomes.",
            "- `duplicate_alias`: alternate copy, truncated export, or proposal/thesis duplicate of another retained work.",
            "",
            "## Included Primary Papers",
            "",
        ]
    )
    for title in included_titles:
        lines.append(f"- {title}")
    lines.extend(["", "## Mechanism-Only Papers", ""])
    for title in mechanism_titles:
        lines.append(f"- {title}")
    rationale_md.write_text("\n".join(lines) + "\n")


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print(
            "usage: python3 tools/finalize_adjudication.py "
            "<screening_log_v2.csv> [output_dir]"
        )
        print("default output_dir: data/screening")
        return 1
    input_csv = Path(sys.argv[1]).expanduser().resolve()
    output_dir = Path(sys.argv[2]).expanduser().resolve() if len(sys.argv) == 3 else DEFAULT_OUTPUT_DIR
    build_outputs(input_csv, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
