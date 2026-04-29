import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

batches = [['Barbara - Host and Symbiont Physiology During Wound Regeneration in Acropora pulchra Under', 'Brush - 2024 - Ecology of Fishes and Invertebrates Inhabiting the', 'Chadwick and Loya - 1990 - Regeneration after experimental breakage in the solitary reef coral Fungia granulosa Klunzing', 'Chong-Seng et al. - 2011 - Selective feeding by coral reef fishes on coral lesions associated with brown band and black band di', 'Comeau et al. - 2014 - Effects of irradiance on the response of the coral Acropora pulchra and the calcifying alga Hydrolit'], ['Counsell et al. - 2019 - Colony size and depth affect wound repair in a bra', 'Counsell et al. - 2019 - Colony size and depth affect wound repair in a branching coral', 'Cox - 2014 - Corallivory The Coral’s Point of View', 'D’Angelo et al. - 2012 - Locally accelerated growth is part of the innate immune response and repair mechanisms in reef-build', 'Denis et al. - 2011 - Lesion regeneration capacities in populations of the massive coral Porites lutea at Réunion Island'], ['Doo et al. - 2018 - Obligate ectosymbionts increase the physiological ', 'E and Y - 1996 - Regeneration versus budding in fungiid corals a trade-off', 'Edmunds and Burgess - 2017 - Colony size and turbulent flow speed modulate the ', 'Edmunds and Lenihan - 2010 - Effect of sub-lethal damage to juvenile colonies of massive Porites spp. under contrasting regimes o', 'Edmunds and Yarid - 2017 - The effects of ocean acidification on wound repair in the coral Porites spp.'], ['Edmunds et al. - 2025 - A physiological crisis drives the coral recruitmen', 'Enochs and Glynn - 2017 - Corallivory in the Eastern Pacific', 'Fine et al. - 2002 - Bleaching effect on regeneration and resource translocation in the coral Oculina patagonica', 'Fisher et al. - 2007 - Lesion regeneration rates in reef-building corals Montastraea spp. as indicators of colony condition', 'Fong and Lirman - 1995 - Hurricanes Cause Population Expansion of the Branching Coral Acropora palmata (Scleractinia)'], ['Furby et al. - 2014 - Incidence of lesions on Fungiidae corals in the eastern Red Sea is related to water temperature and', 'Hall - 1997 - Interspecific differences in the regeneration of artificial injuries on scleractinian corals', 'Hall - 2001 - The response of Acropora hyacinthus and Montipora tuberculosa to three different types of colony dam', 'Hall et al. - 2015 - Lesion recovery of two scleractinian corals under low pH conditions Implications for restoration ef', 'Henry and Hart - 2005 - Regeneration from Injury and Resource Allocation in Sponges and Corals - a Review'], ['Honeycutt et al. - 2023 - Farmerfish gardens help buffer stony corals agains', 'Horricks et al. - 2019 - Differential protein abundance during the first month of regeneration of the Caribbean star coral Mo', 'Horwitz and Fine - 2014 - High CO2 detrimentally affects tissue regeneration of Red Sea corals', 'Jayewardene - 2010 - Experimental determination of the cost of lesion healing on Porites compressa growth', 'Jayewardene et al. - 2009 - Effects of frequent fish predation on corals in Hawaii'], ['Jones and Barott - 2025 - Evidence of rare occurrences of the Phoenix effect in the Hawaiian corals Porites compressa a', 'Kaufman et al. - 2021 - Thermal history influences lesion recovery of the threatened Caribbean staghorn coral Acropora cervi', 'Kersting and Linares - 2019 - Living evidence of a fossil survival strategy raises hope for warming-affected corals', 'Kokita and Nakazono - 2001 - Rapid response of an obligately corallivorous filefish Oxymonacanthus longirostris (Monacanthidae) t', 'Kramarsky-Winter and Loya - 2000 - Tissue regeneration in the coral Fungia granulosa  the effect of extrinsic and intrinsic factors'], ['Lenihan and Edmunds - 2010 - Response of Pocillopora verrucosa to corallivory varies with environmental conditions', 'Lenihan et al. - 2015 - Hydrodynamics influence coral performance through simultaneous direct and indirect effects', 'Leuzinger et al. - 2012 - Energy allocation in a reef coral under varying resource availability', 'Levanoni - 2021 - Coral Tissue Growth and Regeneration Conjoin the Advent of Adult Stem Cell-Like Cells', 'Levanoni et al. - 2024 - Coral Tissue Regeneration and Growth Is Associated with the Presence of Stem-like Cells'], ['Lirman et al. - 2010 - Propagation of the threatened staghorn coral Acropora cervicornis methods to minimize the impacts o', 'Lock et al. - 2022 - Calcium homeostasis disruption initiates rapid growth after micro-fragmentation in the scleractinian', 'Lock et al. - 2022 - Calcium homeostasis disruption initiates rapid growth after micro‐fragmentation in the scleractinian', 'Loya - 1976 - Skeletal regeneration in a Red Sea scleractinian coral population', 'Luz et al. - 2018 - A polyp from nothing The extreme regeneration capacity of the Atlantic invasive sun corals Tubastra'], ['Madeira et al. - 2022 - Does Predation Exacerbate the Risk of Endosymbiont Loss in Heat Stressed Hermatypic Corals Molecula', 'Maher et al. - 2019 - Multiple stressors interact primarily through antagonism to drive changes in the coral microbiome', 'Meesters et al 1992 sedimentation and lesion position', 'Meesters et al. - 1994 - Damage and regeneration links to growth in the reef-building coral Montastrea annularis', 'Meesters et al. - 1996 - Partial Mortality in Three Species of Reef-Building Corals and the Relation with Colony Morphology'], ['Moses and Hallock - 2015 - Coral Regeneration Assay', 'Nagelkerken et al. - 1999 - Depth-related variation in regeneration of artificial lesions in the Caribbean corals Porites ast', 'Nicolet et al. - 2018 - Predation scars may influence host susceptibility to pathogens evaluating the role of corallivores', 'Okubo - 2008 - Size-independent investment allocation to regeneration and growth of the branching coral Acropora mu', 'Oren et al. - 1997 - Effect of lesion size and shape on regeneration of the Red Sea coral Favia favus'], ['Oren et al. - 1997 - Oriented intra-colonial transport of 14C labeled materials during coral regeneration', 'Oren et al. - 2001 - Colony Integration during Regeneration in the Stony Coral Favia favus', 'Page and Willis - 2008 - Epidemiology of skeletal eroding band on the Great Barrier Reef and the role of injury in the initia', 'Palacios et al. - 2014 - Fish corallivory on a pocilloporid reef and experimental coral responses to predation', 'Paradis et al. - 2019 - Compound effects of thermal stress and tissue abrasion on photosynthesis and respiration in the reef'], ['Pavia Jr and Estacion - 2019 - Survival and Growth of Isolated Polyps of Galaxea fascicularis (Linnaeus 1767) on Six Kinds of Cultu', 'Pisapia et al. - 2016 - Temporal consistency in background mortality of four dominant coral taxa along Australia’s Great Bar', 'Rapuano et al. - 2023 - Coming of age Annual onset of coral reproduction is determined by age rather than size', 'Raymundo et al. - 2016 - Effects of Coralliophila violacea on tissue loss in the scleractinian corals Porites spp. depend on', 'Renegar - 2015 - Histology and ultrastructure of Montastraea cavernosa  and Porites astreoides during regeneration an'], ['Rice et al. - 2019 - Different nitrogen sources speed recovery from corallivory and uniquely alter the microbiome of a re', 'Rice et al. - 2021 - Complex interactions with nutrients and sediment a', 'Rinkevich - 1996 - Do reproduction and regeneration in damaged corals compete for energy allocation', 'Roff et al. - 2014 - Porites and the Phoenix effect unprecedented recovery after a mass coral bleaching event at Rangiro', 'Rotjan and Lewis - 2009 - Predators selectively graze reproductive structures in a clonal marine organism'], ['Rotjan et al. - 2006 - Chronic parrotfish grazing impedes coral recovery after bleaching', 'Sabine et al. - 2015 - Environmental conditions influence tissue regeneration rates in scleractinian corals', 'Sani et al. - 2024 - Ocean warming and acidification detrimentally affect coral tissue regeneration at a Mediterranean CO', 'Shaver et al. - 2017 - Effects of predation and nutrient enrichment on the success and microbiome of a foundational coral', 'Shirur et al. - 2016 - Lesion recovery and the bacterial microbiome in two Caribbean gorgonian corals'], ['Soong and Lang - 1992 - Reproductive Integration in Reef Corals', 'Titlyanov and Titlyanova - 2008 - Coral-algal competition on damaged reefs', 'Titlyanov and Titlyanova - 2009 - The dynamics of the restoration of mechanical damage to colonies of the scleractinian coral Porites', 'Titlyanov et al. - 2005 - Regeneration of artificial injuries on scleractinian corals and coralalgal competition for newly fo', 'Titlyanov et al. - 2006 - Three stages of injuries regeneration on scleractinian corals'], ['Townsend et al. - 2023 - Differing lesion recovery rates of two Caribbean stony coral species across a shallow water to mesop', 'Traylor-Knowles - 2016 - Distinctive wound-healing characteristics in the c', 'Traylor-Knowles - 2016 - Distinctive wound-healing characteristics in the corals Pocillopora damicornis and Acropora hyacinth', 'Van De Water et al. - 2015 - Elevated seawater temperatures have a limited impact on the coral immune response following physical', 'Van De Water et al. - 2015 - The coral immune response facilitates protection against microbes during tissue regeneration'], ['Van Woesik - 1998 - Lesion healing on massive Porites spp. corals', 'Wahle - 1983 - Regeneration of injuries among jamaican gorgonians the roles of colony physiology and environment', 'Welsh et al. - 2015 - Clustered parrotfish feeding scars trigger partial coral mortality of massive Porites colonies on th', 'Wesseling et al. - 2001 - Partial Mortality in Porites Corals Variation among Philippine Reefs', 'Wolf and Nugues - 2013 - Synergistic effects of algal overgrowth and corallivory on Caribbean reef‐building corals'], ['Work and Aeby - 2010 - Wound repair in Montipora capitata']]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "audit" / "FULL_LIBRARY_AUDIT.md"
DEFAULT_NLM = Path.home() / ".local" / "bin" / "nlm"


def build_prompt(batch: list[str]) -> str:
    return (
        "Act as a technical data auditor for a PRISMA-standard meta-analysis. Evaluate the following sources "
        "for inclusion in the Scleractinian Regeneration Data Pool:\n"
        + ", ".join(batch)
        + "\n\nAudit the text and tables for the following with surgical precision:\n"
        "1. Primary Response Variables: Does the paper provide raw quantitative data for Healing Rate, Growth Cost, Reproductive Cost, or Survival?\n"
        "2. Threshold of Evidence: Extract the Mean, Variance (SD/SE/CI), and Sample Size (n). Flag as Deficient if missing.\n"
        "3. Taxonomic & Methodological Check: Confirm Scleractinia and describe experimental vs natural wounding.\n"
        "4. Exclusion Red-Flags: Review, Book Chapter, Genomics without macroscopic outcomes.\n"
        "5. Final Verdict: Recommend: [Include in Bins X, Y], [Narrative/Mechanism Only], or [Exclude]."
    )


def write_error(f, batch_num: int, exc: Exception) -> None:
    f.write(f"\n\n### Pool Audit Batch {batch_num} Error\n\n")
    if isinstance(exc, subprocess.CalledProcessError):
        f.write(f"returncode={exc.returncode}\n")
        if exc.stdout:
            f.write("\nstdout:\n" + exc.stdout)
        if exc.stderr:
            f.write("\nstderr:\n" + exc.stderr)
    else:
        f.write(f"{type(exc).__name__}: {exc}\n")
    f.flush()


def validate_nlm_bin(nlm_bin: Path) -> bool:
    return nlm_bin.is_file() and os.access(nlm_bin, os.X_OK)


def run_batches(
    output: Path,
    nlm_bin: Path,
    notebook: str,
    append: bool,
    sleep_seconds: float,
    timeout_seconds: float,
) -> int:
    if not validate_nlm_bin(nlm_bin):
        print(f"nlm binary is not executable: {nlm_bin}", file=sys.stderr)
        return 2
    failures = 0
    mode = "a" if append else "w"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open(mode) as f:
        for idx, batch in enumerate(batches, start=1):
            print(f"Auditing Batch {idx}/{len(batches)}...")
            try:
                result = subprocess.run(
                    [str(nlm_bin), "query", "notebook", notebook, build_prompt(batch)],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=timeout_seconds,
                )
                f.write(f"\n\n### Pool Audit Batch {idx}\n\n" + result.stdout + "\n")
                f.flush()
            except Exception as exc:
                failures += 1
                print(f"Error in batch {idx}: {exc}")
                write_error(f, idx, exc)
            time.sleep(sleep_seconds)
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--nlm-bin", type=Path, default=DEFAULT_NLM)
    parser.add_argument("--notebook", default="coral-regen-all")
    parser.add_argument("--append", action="store_true", help="Append to the audit file instead of overwriting it.")
    parser.add_argument("--sleep-seconds", type=float, default=2.0)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    args = parser.parse_args()
    return run_batches(args.output, args.nlm_bin, args.notebook, args.append, args.sleep_seconds, args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
