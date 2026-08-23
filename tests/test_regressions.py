from __future__ import annotations

import csv
import importlib.util
import io
import json
import math
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


merge_georef = load_module("merge_georef", "tools/merge_approx_georef_results.py")
queue_builder = load_module("queue_builder", "tools/build_approx_georef_queues.py")
finalize_covariates = load_module("finalize_covariates", "tools/finalize_notebook_covariates.py")
rebuild_manifest = load_module("rebuild_manifest", "tools/rebuild_screening_manifest.py")
finalize_adjudication = load_module("finalize_adjudication", "tools/finalize_adjudication.py")
pipeline_builder = load_module("pipeline_builder", "tools/build_pipeline_outputs.py")
audit_all_papers = load_module("audit_all_papers_module", "tools/audit_all_papers.py")
extraction_review = load_module("extraction_review", "tools/build_extraction_review_artifacts.py")
figure_audit_merge = load_module("figure_audit_merge", "tools/merge_figure_candidate_audits.py")
figure_visual_reaudit = load_module("figure_visual_reaudit", "tools/build_figure_visual_reaudit.py")
figure_crop_manifest = load_module("figure_crop_manifest", "tools/build_figure_crop_manifest.py")
figure_index_audit = load_module("figure_index_audit", "tools/audit_figure_indexing.py")
rate_extraction_audit = load_module("rate_extraction_audit", "tools/audit_rate_extraction_dataset.py")
trait_covariate_audit = load_module("trait_covariate_audit", "tools/audit_trait_covariate_coverage.py")
all_response_extraction = load_module("all_response_extraction", "tools/build_all_response_extraction_dataset.py")
notebooklm_validation = load_module("notebooklm_validation", "tools/run_notebooklm_validation_batches.py")
notebooklm_dataset_audit = load_module(
    "notebooklm_dataset_audit", "tools/audit_dataset_against_notebooklm.py"
)
analysis_ready_gate = load_module("analysis_ready_gate", "tools/build_analysis_ready_dataset.py")
taxon_trait_lookup = load_module("taxon_trait_lookup", "tools/build_taxon_trait_lookup.py")
model_covariates = load_module("model_covariates", "tools/build_model_covariates.py")
meta_analysis_inputs = load_module("meta_analysis_inputs", "tools/build_meta_analysis_inputs.py")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


class GeorefMergeTests(unittest.TestCase):
    def test_partial_approx_pair_does_not_drop_nonexact_coordinates(self) -> None:
        row = {
            "latitude": "10",
            "longitude": "20",
            "coordinate_basis": "reef_centroid",
            "coordinate_confidence": "medium",
            "latitude_approx": "11",
            "longitude_approx": "",
            "approx_location_notes": "",
        }

        merge_georef.reconcile_exact_vs_approx(row)

        self.assertEqual(row["latitude"], "")
        self.assertEqual(row["longitude"], "")
        self.assertEqual(row["latitude_approx"], "10")
        self.assertEqual(row["longitude_approx"], "20")
        self.assertEqual(row["latitude_best"], "10")
        self.assertEqual(row["longitude_best"], "20")
        self.assertIn("partial approximate coordinate", row["approx_location_notes"])

    def test_repair_validation_rejects_stale_source_id(self) -> None:
        queue_row = {"source_id": "source-a", "location_raw": "Moorea"}
        repair_row = {"source_id": "source-b", "location_raw": "Moorea"}

        with self.assertRaisesRegex(ValueError, "does not match queue row loc_001"):
            merge_georef.validate_against_queue("loc_001", repair_row, queue_row, "repair file")

    def test_repair_validation_rejects_blank_identity_and_stale_current_coordinates(self) -> None:
        queue_row = {
            "source_id": "source-a",
            "location_raw": "Moorea",
            "current_latitude": "10",
            "current_longitude": "20",
            "current_coordinate_basis": "reef_centroid",
        }

        with self.assertRaisesRegex(ValueError, "source_id"):
            merge_georef.validate_against_queue(
                "loc_001",
                {
                    "source_id": "",
                    "location_raw": "Moorea",
                    "current_latitude": "10",
                    "current_longitude": "20",
                    "current_coordinate_basis": "reef_centroid",
                },
                queue_row,
                "repair file",
            )

        with self.assertRaisesRegex(ValueError, "current_latitude"):
            merge_georef.validate_against_queue(
                "loc_001",
                {
                    "source_id": "source-a",
                    "location_raw": "Moorea",
                    "current_latitude": "11",
                    "current_longitude": "20",
                    "current_coordinate_basis": "reef_centroid",
                },
                queue_row,
                "repair file",
            )

    def test_exact_repair_fields_use_normalized_source_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            location_csv = tmp_path / "locations.csv"
            queue_csv = tmp_path / "queue.csv"
            repair_csv = tmp_path / "repair.csv"
            primary_csv = tmp_path / "primary.csv"
            all_csv = tmp_path / "all.csv"
            location_csv.write_text(
                "source_id,paper_title,location_raw,site_name,country_territory,water_body,latitude,longitude,coordinate_basis,coordinate_confidence\n"
                "s1,Paper,Moorea,,,,,,,\n"
            )
            queue_csv.write_text(
                "location_row_id,source_id,location_raw,site_name,country_territory,water_body,current_latitude,current_longitude,current_coordinate_basis,current_coordinate_confidence\n"
                "loc_001,s1,Moorea,,,,,,,\n"
            )
            repair_csv.write_text(
                "location_row_id,source_id,location_raw,site_name,country_territory,water_body,current_latitude,current_longitude,current_coordinate_basis,current_coordinate_confidence,depth_min_m\n"
                "loc_001,s1 ,Moorea,,,,,,,,5\n"
            )
            primary_csv.write_text("source_id,paper_title,notes,depth_min_m\ns1,Paper,,\n")
            all_csv.write_text("source_id,paper_title,notes,depth_min_m\ns1,Paper,,\n")

            argv = [
                "merge_approx_georef_results.py",
                "--location-csv",
                str(location_csv),
                "--primary-csv",
                str(primary_csv),
                "--all-sources-csv",
                str(all_csv),
                "--queue-csv",
                str(queue_csv),
                "--agent-csvs",
                str(repair_csv),
                "--output-location",
                str(tmp_path / "out_location.csv"),
                "--output-primary",
                str(tmp_path / "out_primary.csv"),
                "--output-all-sources",
                str(tmp_path / "out_all.csv"),
                "--output-audit",
                str(tmp_path / "out_audit.csv"),
            ]
            with patch.object(sys, "argv", argv):
                self.assertEqual(merge_georef.main(), 0)

            self.assertEqual(read_csv(tmp_path / "out_primary.csv")[0]["depth_min_m"], "5")

    def test_multisite_source_is_not_collapsed_to_first_location(self) -> None:
        locs = [
            {"latitude_best": "1", "longitude_best": "2", "best_coordinate_basis": "reef_centroid"},
            {"latitude_best": "3", "longitude_best": "4", "best_coordinate_basis": "reef_centroid"},
        ]

        chosen, status = merge_georef.choose_source_location(locs)

        self.assertIsNone(chosen)
        self.assertEqual(status, "multiple_locations_not_collapsed")

    def test_multisite_source_with_partial_location_resolution_is_not_collapsed(self) -> None:
        locs = [
            {"latitude_best": "1", "longitude_best": "2", "best_coordinate_basis": "reef_centroid"},
            {"latitude_best": "", "longitude_best": "", "best_coordinate_basis": ""},
        ]

        chosen, status = merge_georef.choose_source_location(locs)

        self.assertIsNone(chosen)
        self.assertEqual(status, "multiple_locations_not_collapsed")

    def test_missing_location_coordinates_clear_stale_covariate_summary(self) -> None:
        row = {
            "source_id": "s1",
            "latitude_approx": "10",
            "longitude_approx": "20",
            "latitude_best": "10",
            "longitude_best": "20",
            "approx_location_notes": "",
        }
        merge_georef.ensure_cov_fields(row)
        chosen, merge_status = merge_georef.choose_source_location(
            [{"source_id": "s1", "latitude": "", "longitude": "", "latitude_best": "", "longitude_best": ""}]
        )
        self.assertIsNone(chosen)
        self.assertEqual(merge_status, "no_location_coordinates")

        merge_georef.clear_cov_location_summary(row)
        merge_georef.append_note(row, "approx_location_notes", "[no location coordinates available in location manifest]")

        self.assertEqual(row["latitude_approx"], "")
        self.assertEqual(row["longitude_approx"], "")
        self.assertEqual(row["latitude_best"], "")
        self.assertEqual(row["longitude_best"], "")


class QueueBuilderTests(unittest.TestCase):
    def test_unknown_region_is_explicit(self) -> None:
        row = {
            "location_raw": "Unspecified reef",
            "site_name": "",
            "country_territory": "",
            "water_body": "",
        }

        self.assertEqual(queue_builder.classify_region(row), "unknown_region")

    def test_dual_coast_countries_require_explicit_region_evidence(self) -> None:
        self.assertEqual(
            queue_builder.classify_region(
                {
                    "location_raw": "Pichilingue Bay, La Paz, BCS, Mexico",
                    "site_name": "",
                    "country_territory": "Mexico",
                    "water_body": "",
                }
            ),
            "pacific_region",
        )
        self.assertEqual(
            queue_builder.classify_region(
                {
                    "location_raw": "patch reef near Puerto Morelos, Mexico",
                    "site_name": "",
                    "country_territory": "Mexico",
                    "water_body": "Caribbean Sea",
                }
            ),
            "caribbean_region",
        )
        self.assertEqual(
            queue_builder.classify_region(
                {
                    "location_raw": "Saboga Is., Panama",
                    "site_name": "Saboga Is.",
                    "country_territory": "Panama",
                    "water_body": "eastern tropical Pacific",
                }
            ),
            "pacific_region",
        )

    def test_missingness_aliases_include_exact_and_best_coordinate_fields(self) -> None:
        issue_map = queue_builder.build_exact_missing_map(
            [
                {
                    "source_id": "s1",
                    "missing_location_raw": "0",
                    "missing_exact_coords_latlon": "1",
                    "missing_best_coords_latlon": "1",
                    "missing_depth": "0",
                    "missing_growth_form": "0",
                    "missing_tissue_type": "0",
                    "missing_area_mm2": "0",
                    "missing_temperature_c": "0",
                    "missing_sample_size": "0",
                }
            ]
        )

        self.assertIn("missing_exact_coords_latlon", issue_map["s1"])
        self.assertIn("missing_best_coords_latlon", issue_map["s1"])

    def test_all_bucket_files_are_rewritten_even_when_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            location_csv = tmp_path / "locations.csv"
            remaining_csv = tmp_path / "remaining.csv"
            out_dir = tmp_path / "queues"
            location_csv.write_text(
                "source_id,paper_title,location_raw,site_name,country_territory,water_body,latitude,longitude,coordinate_basis,coordinate_confidence\n"
                "s1,Paper,Unspecified reef,,,,,,,\n"
            )
            remaining_csv.write_text(
                "source_id,missing_location_raw,missing_coords_latlon,missing_depth,missing_growth_form,missing_tissue_type,missing_area_mm2,missing_temperature_c,missing_sample_size\n"
                "s1,0,1,0,0,0,0,0,0\n"
            )

            argv = [
                "build_approx_georef_queues.py",
                "--location-csv",
                str(location_csv),
                "--remaining-primary-csv",
                str(remaining_csv),
                "--output-dir",
                str(out_dir),
            ]
            with patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()):
                self.assertEqual(queue_builder.main(), 0)

            for filename in [
                "agent_georef_queue_1.csv",
                "agent_georef_queue_2.csv",
                "agent_georef_queue_3.csv",
                "agent_georef_queue_unknown.csv",
            ]:
                self.assertTrue((out_dir / filename).exists(), filename)
            self.assertEqual(read_csv(out_dir / "agent_georef_queue_1.csv"), [])
            self.assertEqual(read_csv(out_dir / "agent_georef_queue_2.csv"), [])
            self.assertEqual(read_csv(out_dir / "agent_georef_queue_3.csv"), [])
            unknown_rows = read_csv(out_dir / "agent_georef_queue_unknown.csv")
            self.assertEqual(len(unknown_rows), 1)
            self.assertEqual(unknown_rows[0]["location_row_id"], "loc_001")
            self.assertEqual(unknown_rows[0]["source_id"], "s1")


class CovariateFinalizationTests(unittest.TestCase):
    def test_negative_degrees_with_west_hemisphere_stay_negative(self) -> None:
        self.assertEqual(finalize_covariates.dms_to_decimal("-64° 00' W"), "-64.000000")
        self.assertEqual(finalize_covariates.dms_to_decimal("-64° 00' E"), "")

    def test_coordinate_ranges_and_out_of_bounds_values_do_not_parse(self) -> None:
        self.assertEqual(finalize_covariates.dms_to_decimal("10-20"), "")
        self.assertEqual(finalize_covariates.dms_to_decimal("10 to 20"), "")
        self.assertEqual(finalize_covariates.dms_to_decimal("91 N"), "")
        self.assertEqual(finalize_covariates.dms_to_decimal("181 E"), "")

    def test_location_basis_is_derived_from_merged_row(self) -> None:
        location_rows = [
            {
                "source_id": "s1",
                "paper_title": "Paper",
                "location_raw": "Existing site",
                "latitude": "1",
                "longitude": "2",
                "coordinate_basis": "",
                "coordinate_confidence": "",
            }
        ]
        cov_rows = [
            {
                "source_id": "s1",
                "paper_title": "Paper",
                "notebook_covariate_status": "parsed",
                "location_raw": "",
                "latitude": "",
                "longitude": "",
            }
        ]

        merged = finalize_covariates.merge_location_rows(location_rows, cov_rows)

        self.assertEqual(merged[0]["coordinate_basis"], "inferred_from_locality")
        self.assertEqual(merged[0]["coordinate_confidence"], "medium")

    def test_covariate_reported_raw_coordinates_keep_reported_exact_basis(self) -> None:
        location_rows = [
            {
                "source_id": "s1",
                "paper_title": "Paper",
                "location_raw": "",
                "latitude": "",
                "longitude": "",
                "coordinate_basis": "",
                "coordinate_confidence": "",
            }
        ]
        cov_rows = [
            {
                "source_id": "s1",
                "paper_title": "Paper",
                "notebook_covariate_status": "parsed",
                "location_raw": "Reported reef",
                "latitude_raw": "10 N",
                "longitude_raw": "20 W",
                "latitude": "10",
                "longitude": "-20",
            }
        ]

        merged = finalize_covariates.merge_location_rows(location_rows, cov_rows)

        self.assertEqual(merged[0]["coordinate_basis"], "reported_exact")
        self.assertEqual(merged[0]["coordinate_confidence"], "high")

    def test_unknown_worker_source_id_fails(self) -> None:
        with self.assertRaisesRegex(ValueError, "Worker repair source_id not found"):
            finalize_covariates.merge_worker_repairs(
                [{"source_id": "s1", "paper_title": "Paper"}],
                [{"source_id": "stale", "location_raw": "Moorea"}],
            )

    def test_main_writes_header_only_remaining_queue_when_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            base_primary = tmp_path / "primary.csv"
            base_all = tmp_path / "all.csv"
            base_location = tmp_path / "locations.csv"
            worker_csv = tmp_path / "worker.csv"
            cov_header = (
                "source_id,paper_title,location_raw,latitude,longitude,depth_min_m,depth_max_m,"
                "growth_form,tissue_type,area_mm2,temperature_c,sample_size,notes\n"
            )
            complete_row = "s1,Paper,Moorea,1,2,3,4,branching,live tissue,10,27,5,\n"
            base_primary.write_text(cov_header + complete_row)
            base_all.write_text(cov_header + complete_row)
            base_location.write_text(
                "source_id,paper_title,location_raw,location_standardized,site_name,reef_or_bay,island_or_coast,country_territory,water_body,latitude,longitude,depth_min_m,depth_max_m,location_type,coordinate_basis,coordinate_confidence,location_notes\n"
                "s1,Paper,Moorea,,,,,,Pacific,1,2,3,4,field_site,reported_exact,high,\n"
            )
            worker_csv.write_text("source_id,location_raw\n")

            argv = [
                "finalize_notebook_covariates.py",
                "--base-primary",
                str(base_primary),
                "--base-all-sources",
                str(base_all),
                "--worker-csvs",
                str(worker_csv),
                "--base-location",
                str(base_location),
                "--output-primary",
                str(tmp_path / "out_primary.csv"),
                "--output-all-sources",
                str(tmp_path / "out_all.csv"),
                "--output-missingness",
                str(tmp_path / "out_missing.csv"),
                "--output-remaining",
                str(tmp_path / "out_remaining.csv"),
                "--output-location",
                str(tmp_path / "out_location.csv"),
                "--output-summary",
                str(tmp_path / "summary.md"),
                "--output-audit",
                str(tmp_path / "audit.csv"),
            ]
            with patch.object(sys, "argv", argv):
                self.assertEqual(finalize_covariates.main(), 0)

            remaining_path = tmp_path / "out_remaining.csv"
            self.assertEqual(read_csv(remaining_path), [])
            self.assertEqual(
                remaining_path.read_text().splitlines()[0],
                "source_id,paper_title,missing_location_raw,missing_coords_latlon,missing_depth,missing_growth_form,missing_tissue_type,missing_area_mm2,missing_temperature_c,missing_sample_size,remaining_issue_count",
            )


class ManifestRebuildTests(unittest.TestCase):
    def test_malformed_audit_section_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.md"
            answer = (
                "**Smith - 2020 - Coral lesion repair**\n"
                "Final Verdict: [Include in Bins 1]. Primary healing-rate data are reported.\n"
            )
            audit_path.write_text(
                "## Bad\n"
                "{\"value\":\n"
                "## Good\n"
                + json.dumps({"value": {"answer": answer}})
                + "\n"
            )

            with redirect_stderr(io.StringIO()):
                records = rebuild_manifest.parse_audit_records(audit_path)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].audit_title, "Smith - 2020 - Coral lesion repair")
            self.assertEqual(records[0].response_bins, ["rate"])

    def test_negative_reason_text_does_not_create_primary_bins(self) -> None:
        bins = rebuild_manifest.response_bins_from_verdict("[Include in Bins 5]", "no growth or survival effect sizes")

        self.assertEqual(bins, ["mechanism"])

    def test_local_pdf_assignment_is_one_to_one(self) -> None:
        title = "Sani et al. - 2024 - Ocean warming and acidification detrimentally affect coral tissue regeneration.pdf"
        author, year, rest = rebuild_manifest.split_author_year_title(title)
        sources = [
            rebuild_manifest.NotebookSource(f"s{i}", title, author, year, rest, rebuild_manifest.normalize_title(title))
            for i in range(2)
        ]
        pdf = rebuild_manifest.LocalPdf(
            "literature/META_ANALYSIS_POOL/" + title,
            title,
            "META_ANALYSIS_POOL",
            author,
            year,
            rest,
            rebuild_manifest.normalize_title(title),
        )

        assignments = rebuild_manifest.assign_sources_to_local_pdfs(sources, [pdf])

        self.assertEqual(len(assignments), 1)
        self.assertEqual({match[0].relpath for match in assignments.values()}, {pdf.relpath})

    def test_local_pdf_assignment_can_use_second_choice_to_preserve_matches(self) -> None:
        sources = [
            rebuild_manifest.NotebookSource("source-a", "Source A", "a", "2020", "alpha", "source a"),
            rebuild_manifest.NotebookSource("source-b", "Source B", "b", "2020", "beta", "source b"),
        ]
        pdfs = [
            rebuild_manifest.LocalPdf("x.pdf", "x.pdf", "", "x", "2020", "x", "x"),
            rebuild_manifest.LocalPdf("y.pdf", "y.pdf", "", "y", "2020", "y", "y"),
        ]
        scores = {
            ("source-a", "x.pdf"): 0.99,
            ("source-a", "y.pdf"): 0.90,
            ("source-b", "x.pdf"): 0.95,
            ("source-b", "y.pdf"): -1.0,
        }

        with patch.object(
            rebuild_manifest,
            "score_source_to_local",
            side_effect=lambda source, pdf: scores[(source.source_id, pdf.relpath)],
        ):
            assignments = rebuild_manifest.assign_sources_to_local_pdfs(sources, pdfs)

        self.assertEqual(assignments["source-a"][0].relpath, "y.pdf")
        self.assertEqual(assignments["source-b"][0].relpath, "x.pdf")


class AdjudicationTests(unittest.TestCase):
    def build_adjudication_outputs(self, rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_csv = tmp_path / "screening.csv"
            fieldnames = [
                "paper_title",
                "source_id",
                "notebook_present",
                "local_present",
                "local_relpath",
                "local_filename",
                "current_folder",
                "screening_bucket",
                "candidate_bins",
                "screening_notes",
                "audit_count",
                "audit_titles",
                "audit_verdicts",
                "conflicting_audits",
            ]
            with input_csv.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow({field: row.get(field, "") for field in fieldnames})

            finalize_adjudication.build_outputs(input_csv, tmp_path)

            with (tmp_path / "SCREENING_LOG_FINAL.csv").open(newline="") as f:
                final_rows = list(csv.DictReader(f))
            with (tmp_path / "HYPOTHESIS_X_RESPONSE_MATRIX.csv").open(newline="") as f:
                matrix_rows = list(csv.DictReader(f))
            return final_rows, matrix_rows

    def test_conflicted_bucket_remains_needs_adjudication(self) -> None:
        final_rows, _ = self.build_adjudication_outputs(
            [
                {
                    "local_filename": "Example conflict paper.pdf",
                    "screening_bucket": "include_primary_conflicted",
                    "candidate_bins": "rate",
                    "screening_notes": "[Include in Bins 1] || [Exclude]",
                    "conflicting_audits": "1",
                }
            ]
        )

        self.assertEqual(final_rows[0]["final_status"], "review_needed")
        self.assertEqual(final_rows[0]["extraction_readiness"], "needs_adjudication")

    def test_conflicting_audit_flag_overrides_nonconflict_bucket(self) -> None:
        final_rows, _ = self.build_adjudication_outputs(
            [
                {
                    "local_filename": "Example unresolved conflict.pdf",
                    "screening_bucket": "include_primary_needs_fulltext",
                    "candidate_bins": "rate",
                    "screening_notes": "[Include in Bins 1] || [Exclude]",
                    "conflicting_audits": "1",
                }
            ]
        )

        self.assertEqual(final_rows[0]["final_status"], "review_needed")
        self.assertEqual(final_rows[0]["extraction_readiness"], "needs_adjudication")
        self.assertEqual(final_rows[0]["adjudication_basis"], "conflicted_prior_audit")

    def test_title_keyword_fallback_does_not_auto_include(self) -> None:
        final_rows, matrix_rows = self.build_adjudication_outputs(
            [
                {
                    "local_filename": "Example predation behavior study.pdf",
                    "screening_bucket": "review_needed",
                }
            ]
        )

        self.assertEqual(final_rows[0]["final_status"], "review_needed")
        self.assertEqual(final_rows[0]["extraction_readiness"], "needs_adjudication")
        self.assertEqual(final_rows[0]["adjudication_basis"], "title_keyword_fallback")
        self.assertIn("full-text adjudication", final_rows[0]["final_rationale"])
        self.assertEqual(matrix_rows[0]["response_rate"], "0")
        self.assertEqual(matrix_rows[0]["response_growth"], "0")
        self.assertEqual(matrix_rows[0]["response_survival"], "0")

    def test_excluded_rows_do_not_keep_response_or_hypothesis_flags(self) -> None:
        final_rows, matrix_rows = self.build_adjudication_outputs(
            [
                {
                    "local_filename": "Da Silveira and VanT Hof - 1977 - Regeneration in the Gorgonian Plexura Flexuosa.pdf",
                    "screening_bucket": "exclude_scope",
                    "candidate_bins": "mechanism|rate",
                    "screening_notes": "Regeneration mechanism outside scleractinian scope.",
                }
            ]
        )

        self.assertEqual(final_rows[0]["final_status"], "exclude_scope")
        for field in ["response_rate", "response_growth", "response_reproduction", "response_survival", "response_mechanism"]:
            self.assertEqual(matrix_rows[0][field], "0")
        for field in [
            "hypothesis_traits",
            "hypothesis_environment",
            "hypothesis_wound_type",
            "hypothesis_geometry",
            "hypothesis_integration",
        ]:
            self.assertEqual(matrix_rows[0][field], "0")

    def test_cox_manual_review_exclusion_matches_curly_apostrophe_title(self) -> None:
        final_rows, _ = self.build_adjudication_outputs(
            [
                {
                    "local_filename": "Cox - 2014 - Corallivory The Coral’s Point of View.pdf",
                    "screening_bucket": "review_needed",
                }
            ]
        )

        self.assertEqual(final_rows[0]["final_status"], "exclude_review")
        self.assertEqual(final_rows[0]["adjudication_basis"], "manual_override")

    def test_manual_hypothesis_tags_are_written_to_matrix(self) -> None:
        final_rows, matrix_rows = self.build_adjudication_outputs(
            [
                {
                    "local_filename": "Van Woesik - 1998 - Lesion healing on massive Porites spp. corals.pdf",
                    "screening_bucket": "review_needed",
                }
            ]
        )

        self.assertEqual(final_rows[0]["final_status"], "include_primary")
        self.assertEqual(matrix_rows[0]["response_rate"], "1")
        self.assertEqual(matrix_rows[0]["hypothesis_geometry"], "1")

    def test_duplicate_canonical_keeps_duplicate_audit_evidence(self) -> None:
        final_rows, _ = self.build_adjudication_outputs(
            [
                {
                    "local_filename": "Smith - 2020 - Coral lesion repair.pdf",
                    "screening_bucket": "include_primary",
                    "candidate_bins": "rate",
                    "screening_notes": "note A",
                    "audit_count": "1",
                    "audit_titles": "audit A",
                    "audit_verdicts": "[Include in Bins 1]",
                },
                {
                    "local_filename": "Smith - 2020 - Coral lesion repair.pdf",
                    "screening_bucket": "include_primary",
                    "candidate_bins": "growth",
                    "screening_notes": "note B",
                    "audit_count": "1",
                    "audit_titles": "audit B",
                    "audit_verdicts": "[Include in Bins 2]",
                },
            ]
        )

        canonical = next(row for row in final_rows if row["final_status"] == "include_primary")
        duplicates = [row for row in final_rows if row["final_status"] == "duplicate_alias"]
        self.assertEqual(len([row for row in final_rows if row["final_status"] == "include_primary"]), 1)
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["extraction_readiness"], "not_for_extraction")
        self.assertEqual(duplicates[0]["alias_of"], canonical["paper_title"])
        self.assertEqual(canonical["audit_count"], "2")
        self.assertIn("note A", canonical["screening_notes"])
        self.assertIn("note B", canonical["screening_notes"])
        self.assertIn("audit A", canonical["audit_titles"])
        self.assertIn("audit B", canonical["audit_titles"])
        self.assertEqual(set(canonical["candidate_bins"].split("|")), {"rate", "growth"})
        self.assertEqual(canonical["response_rate"], "1")
        self.assertEqual(canonical["response_growth"], "1")


class AuditScriptTests(unittest.TestCase):
    def test_audit_script_fails_fast_when_nlm_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "audit.md"
            missing = Path(tmp) / "missing-nlm"

            with patch.object(audit_all_papers.subprocess, "run") as run, redirect_stderr(io.StringIO()):
                status = audit_all_papers.run_batches(output, missing, "notebook", False, 0, 1, 1)

            self.assertEqual(status, 2)
            run.assert_not_called()

    def test_audit_script_passes_timeout_to_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "audit.md"
            nlm_bin = Path(tmp) / "nlm"
            nlm_bin.write_text("#!/bin/sh\n")
            nlm_bin.chmod(0o755)

            with patch.object(audit_all_papers, "batches", [["Paper"]]), patch.object(
                audit_all_papers.subprocess,
                "run",
                return_value=audit_all_papers.subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr=""),
            ) as run, redirect_stdout(io.StringIO()):
                status = audit_all_papers.run_batches(output, nlm_bin, "notebook", False, 0, 1, 7)

            self.assertEqual(status, 0)
            self.assertEqual(run.call_args.kwargs["timeout"], 7)


class PipelineBuilderTests(unittest.TestCase):
    def test_excluded_rows_do_not_enter_extraction_workplan(self) -> None:
        screening_rows = [
            {
                "paper_title": "Excluded gorgonian mechanism paper.pdf",
                "source_id": "excluded-1",
                "final_status": "exclude_scope",
                "extraction_readiness": "not_for_extraction",
                "response_mechanism": "1",
            },
            {
                "paper_title": "Included coral mechanism paper.pdf",
                "source_id": "included-1",
                "final_status": "include_mechanism_only",
                "extraction_readiness": "not_for_extraction",
                "response_mechanism": "1",
            },
        ]

        workplan = pipeline_builder.build_extraction_workplan(screening_rows)

        self.assertEqual(len(workplan), 1)
        self.assertEqual(workplan[0]["source_id"], "included-1")
        self.assertEqual(workplan[0]["response_type"], "mechanism")
        self.assertEqual(workplan[0]["extraction_status"], "narrative_not_effect_size")

    def test_digitization_queue_requires_figure_identification_before_paths(self) -> None:
        workplan = [
            {
                "requires_digitization": "1",
                "source_id": "12345678-abcd",
                "paper_title": "Paper.pdf",
                "response_type": "rate",
                "source_file_status": "local_pdf_available",
                "local_relpath": "literature/META_ANALYSIS_POOL/Paper.pdf",
            }
        ]

        queue = pipeline_builder.build_digitization_queue(workplan)

        self.assertEqual(queue[0]["queue_id"], "DIG-12345678-rate")
        self.assertEqual(queue[0]["digitization_status"], "needs_figure_id")
        self.assertEqual(queue[0]["clip_path"], "")
        self.assertEqual(queue[0]["digitized_data_path"], "")
        self.assertEqual(queue[0]["qa_status"], "not_started")

    def test_digitization_queue_blocks_missing_local_pdf(self) -> None:
        workplan = [
            {
                "requires_digitization": "1",
                "source_id": "12345678-abcd",
                "paper_title": "Paper.pdf",
                "response_type": "rate",
                "source_file_status": "missing_local_pdf",
                "local_relpath": "",
            }
        ]

        queue = pipeline_builder.build_digitization_queue(workplan)

        self.assertEqual(queue[0]["digitization_status"], "blocked_missing_local_pdf")
        self.assertEqual(queue[0]["qa_status"], "blocked")
        self.assertIn("Retrieve the local PDF", queue[0]["notes"])

    def test_literature_reorg_audit_preserves_historical_rows_after_clean_commit(self) -> None:
        historical = [
            {
                "deleted_flat_relpath": "literature/Paper.pdf",
                "organized_relpath": "literature/META_ANALYSIS_POOL/Paper.pdf",
                "filename_match_count": "1",
                "tracked_blob_sha": "abc",
                "organized_blob_sha": "abc",
                "hash_status": "hash_match",
            }
        ]

        with patch.object(pipeline_builder, "run_git", return_value=[]), patch.object(
            pipeline_builder, "staged_literature_renames", return_value={}
        ), patch.object(
            pipeline_builder, "read_historical_literature_reorg_audit", return_value=historical
        ), patch.object(
            pipeline_builder, "literature_pdf_count", return_value=1
        ):
            rows, summary = pipeline_builder.build_literature_reorg_audit()

        self.assertEqual(rows, historical)
        self.assertEqual(summary["deleted_flat_pdf_count"], 1)
        self.assertEqual(summary["hash_matches"], 1)


class ExtractionReviewArtifactTests(unittest.TestCase):
    def test_caption_candidates_are_ranked_without_assigning_clip_paths(self) -> None:
        pages = [
            "\n".join(
                [
                    "Introduction",
                    "Fig. 1. Lesion regeneration through time for wounded coral colonies.",
                    "Values show mean tissue area remaining with standard errors.",
                    "",
                    "Table 1. Growth and calcification results.",
                ]
            )
        ]
        candidates = extraction_review.caption_candidates_from_pages(pages)

        self.assertEqual(candidates[0]["candidate_label"], "Fig. 1")
        score, terms = extraction_review.score_candidate(candidates[0], "rate")
        self.assertGreater(score, 0)
        self.assertIn("regeneration", terms)

        mentions = extraction_review.mention_candidates_from_pages(
            ["The fastest rates occurred early in the experiment (Figs. 2 and 3; Table 1)."]
        )
        self.assertEqual([row["candidate_label"] for row in mentions], ["Fig. 2", "Fig. 3", "Table 1"])

        unlabeled = extraction_review.mention_candidates_from_pages(
            [
                "Regeneration of damaged colonies of the coral Porites lutea. A, one colony used in the experiment; B, mechanically damaged colony after 1 month; C, regenerated lesion after 3 months."
            ]
        )
        self.assertEqual(unlabeled[0]["candidate_label"], "unlabeled figure")

        rows = extraction_review.build_figure_source_review_rows(
            [
                {
                    "queue_id": "DIG-0001",
                    "digitization_status": "blocked_missing_local_pdf",
                    "source_id": "12345678-abcd",
                    "paper_title": "Missing.pdf",
                    "response_type": "rate",
                    "source_file_status": "missing_local_pdf",
                    "local_relpath": "",
                }
            ]
        )

        self.assertEqual(rows[0]["review_status"], "blocked_missing_local_pdf")
        self.assertNotIn("fig-XX", rows[0]["required_clip_naming_rule"])
        self.assertEqual(rows[0]["candidate_label"], "")

    def test_legacy_extraction_qa_flags_missing_source_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / "rates.csv"
            table.write_text(
                "source_id,paper_title,local_relpath,response_type,source_match_status,figure_or_table_label,page,panel_label,extraction_provenance,qa_status,Author,Year,Species,Wound_Area_mm2,Rate_Value,Rate_Unit,Variance_Type,Variance_Value,Sample_Size,Location,Stressor,Notes\n"
                "source-1,Paper.pdf,,rate,manual_source_match,,,,legacy row,needs_source_provenance_review,A,2000,Coral,1,0.1,mm2 d-1,SE,0.01,10,Site,None,Note\n",
                encoding="utf-8",
            )

            rows = extraction_review.build_legacy_extraction_qa_rows(
                {"rates.csv": table},
                [{"source_id": "source-1", "response_type": "growth"}],
            )

        self.assertEqual(rows[0]["review_status"], "needs_source_provenance_review")
        self.assertEqual(rows[0]["workplan_crosswalk_status"], "response_not_in_workplan")
        self.assertIn("local_relpath", rows[0]["missing_required_fields"])
        self.assertIn("figure_or_table_label", rows[0]["missing_required_fields"])
        self.assertEqual(rows[0]["units_value"], "mm2 d-1")
        self.assertEqual(rows[0]["variance_type_value"], "SE")
        self.assertEqual(rows[0]["sample_size_value"], "10")

    def test_figure_candidate_audit_merge_preserves_pending_coverage(self) -> None:
        base_rows = [
            {
                "queue_id": "DIG-source-rate",
                "source_id": "source-1",
                "paper_title": "Paper.pdf",
                "response_type": "rate",
                "candidate_rank": "1",
                "candidate_type": "figure",
                "candidate_label": "Fig. 1",
                "candidate_page": "3",
                "review_status": "candidate_review_needed",
            },
            {
                "queue_id": "DIG-source-rate",
                "source_id": "source-1",
                "paper_title": "Paper.pdf",
                "response_type": "rate",
                "candidate_rank": "2",
                "candidate_type": "figure",
                "candidate_label": "Fig. 2",
                "candidate_page": "4",
                "review_status": "candidate_review_needed",
            },
        ]
        audit_rows = [
            {
                "source_id": "source-1",
                "paper_title": "Paper.pdf",
                "response_type": "rate",
                "queue_id": "DIG-source-rate",
                "original_candidate_rank": "1",
                "original_candidate_type": "figure",
                "original_candidate_label": "Fig. 1",
                "original_candidate_page": "3",
                "audit_status": "replace",
                "corrected_candidate_type": "figure",
                "corrected_candidate_label": "Fig. 3",
                "corrected_candidate_page": "5",
                "corrected_candidate_text": "Fig. 3. Lesion recovery through time.",
                "reason": "Fig. 3 is the wound-recovery time series.",
                "needs_manual_visual_review": "yes",
                "evidence_method": "pdftotext",
                "audit_file": "digitization/source_review/agent_audits/figure_candidate_audit_agent1.csv",
                "audit_key_status": "valid_status",
            }
        ]

        validated, merged, summary = figure_audit_merge.build_validated_rows(base_rows, audit_rows)

        self.assertEqual(validated[0]["validated_review_status"], "candidate_replacement_available")
        self.assertEqual(validated[0]["corrected_candidate_label"], "Fig. 3")
        self.assertEqual(validated[1]["validated_review_status"], "pending_agent_review")
        self.assertEqual(merged[0]["coverage_status"], "matched_base_candidate")
        self.assertEqual(summary["missing_candidate_rows"], 1)

        queue_rows = figure_audit_merge.build_queue_summary_rows(validated)

        self.assertEqual(queue_rows[0]["queue_audit_status"], "audited_candidate_available")
        self.assertIn("figure:Fig. 3:p5", queue_rows[0]["recommended_candidates"])
        self.assertEqual(queue_rows[0]["recommended_candidate_count"], 1)

    def test_figure_visual_reaudit_keeps_rejected_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            image_path = tmp_root / "digitization" / "figures" / "source_pages" / "source__page-001.png"
            image_path.parent.mkdir(parents=True)
            try:
                from PIL import Image
            except Exception as exc:  # pragma: no cover - test environment should provide Pillow.
                self.skipTest(f"Pillow unavailable: {exc}")
            Image.new("RGB", (20, 20), color=(255, 255, 255)).save(image_path)
            # Add a dark square so the image is not classified as blank.
            image = Image.open(image_path)
            for x in range(5, 15):
                for y in range(5, 15):
                    image.putpixel((x, y), (0, 0, 0))
            image.save(image_path)

            render_rows = [
                {
                    "queue_id": "DIG-source-rate",
                    "source_id": "source-1",
                    "paper_title": "Paper.pdf",
                    "response_type": "rate",
                    "candidate_descriptor": "figure:Fig. 1:p1",
                    "candidate_type": "figure",
                    "candidate_label": "Fig. 1",
                    "pdf_page": "1",
                    "source_page_render": "digitization/figures/source_pages/source__page-001.png",
                    "render_status": "rendered",
                    "candidate_text": "Fig. 1. Mean lesion recovery rate with SE error bars.",
                },
                {
                    "queue_id": "DIG-source-growth",
                    "source_id": "source-1",
                    "paper_title": "Paper.pdf",
                    "response_type": "growth",
                    "candidate_descriptor": "figure:Fig. 1:p1",
                    "candidate_type": "figure",
                    "candidate_label": "Fig. 1",
                    "pdf_page": "1",
                    "source_page_render": "digitization/figures/source_pages/source__page-001.png",
                    "render_status": "already_rendered",
                    "candidate_text": "Fig. 1. Mean growth rate with SE error bars.",
                }
            ]
            caption_rows = [
                {
                    "audit_status": "remove",
                    "queue_id": "DIG-source-survival",
                    "source_id": "source-1",
                    "paper_title": "Paper.pdf",
                    "response_type": "survival",
                    "reason": "no_valid_candidate_found",
                    "original_candidate_type": "figure",
                    "original_candidate_label": "Fig. 2",
                    "original_candidate_page": "2",
                }
            ]

            with patch.object(figure_visual_reaudit, "ROOT", tmp_root):
                rows = figure_visual_reaudit.build_visual_reaudit_rows(render_rows, caption_rows)

        self.assertEqual(rows[0]["reaudit_row_type"], "accepted_visual_candidate")
        self.assertEqual(rows[0]["visual_reaudit_status"], "source_page_image_verified")
        self.assertEqual(rows[0]["extractability_class"], "quantitative_plot_candidate")
        self.assertEqual(rows[1]["visual_reaudit_status"], "source_page_image_verified")
        self.assertEqual(rows[2]["reaudit_row_type"], "retained_caption_rejected")
        self.assertEqual(rows[2]["crop_readiness"], "do_not_crop_from_caption_audit")

    def test_figure_crop_manifest_creates_reviewable_proposal_and_keeps_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            render_path = tmp_root / "digitization" / "figures" / "source_pages" / "source__page-001.png"
            crop_dir = tmp_root / "digitization" / "figures" / "crop_review"
            pdf_path = tmp_root / "paper.pdf"
            render_path.parent.mkdir(parents=True)
            pdf_path.write_bytes(b"%PDF-1.4\n")
            try:
                from PIL import Image, ImageDraw
            except Exception as exc:  # pragma: no cover - test environment should provide Pillow.
                self.skipTest(f"Pillow unavailable: {exc}")
            image = Image.new("RGB", (200, 200), color=(255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.rectangle((35, 45, 130, 110), fill=(0, 0, 0))
            draw.text((20, 125), "Figure 1", fill=(0, 0, 0))
            image.save(render_path)

            bbox_html = """<html><body><doc><page width="100" height="100">
                <word xMin="10" yMin="65" xMax="30" yMax="72">Figure</word>
                <word xMin="32" yMin="65" xMax="38" yMax="72">1</word>
                <word xMin="40" yMin="65" xMax="70" yMax="72">Recovery</word>
                </page></doc></body></html>"""
            visual_rows = [
                {
                    "reaudit_row_type": "accepted_visual_candidate",
                    "extractability_class": "quantitative_plot_candidate",
                    "queue_id": "DIG-source-rate",
                    "source_id": "source-1",
                    "paper_title": "Paper.pdf",
                    "response_type": "rate",
                    "candidate_descriptor": "figure:Figure 1:p1",
                    "candidate_type": "figure",
                    "candidate_label": "Figure 1",
                    "pdf_page": "1",
                    "source_page_render": "digitization/figures/source_pages/source__page-001.png",
                    "image_width": "200",
                    "image_height": "200",
                    "candidate_text": "Figure 1. Recovery rate.",
                },
                {
                    "reaudit_row_type": "retained_caption_rejected",
                    "extractability_class": "not_a_valid_visual_candidate",
                    "queue_id": "DIG-source-survival",
                    "source_id": "source-1",
                    "paper_title": "Paper.pdf",
                    "response_type": "survival",
                    "candidate_type": "figure",
                    "candidate_label": "Figure 2",
                    "pdf_page": "2",
                    "caption_rejection_reason": "wrong outcome",
                },
            ]
            source_rows = [
                {
                    "queue_id": "DIG-source-rate",
                    "candidate_descriptor": "figure:Figure 1:p1",
                    "local_relpath": "paper.pdf",
                }
            ]

            with patch.object(figure_crop_manifest, "ROOT", tmp_root), patch.object(
                figure_crop_manifest, "CROP_REVIEW_DIR", crop_dir
            ), patch.object(figure_crop_manifest, "run_pdftotext_bbox", return_value=(bbox_html, "")):
                rows = figure_crop_manifest.build_crop_rows(visual_rows, source_rows)
            crop_exists = (tmp_root / str(rows[0]["crop_path"])).exists()

        self.assertEqual(rows[0]["crop_status"], "auto_crop_proposal_created")
        self.assertEqual(rows[0]["crop_review_status"], "needs_human_crop_box_qa")
        self.assertEqual(rows[0]["caption_locator_status"], "caption_bbox_found")
        self.assertIn("digitization/figures/crop_review/", rows[0]["crop_path"])
        self.assertTrue(crop_exists)
        self.assertEqual(rows[1]["crop_status"], "retained_rejected_not_cropped")
        self.assertEqual(rows[1]["crop_review_status"], "do_not_crop_from_caption_audit")


class RateExtractionAuditTests(unittest.TestCase):
    def test_strict_csv_reader_flags_underfilled_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text("a,b,c\n1,2\n", encoding="utf-8")
            issues: list[dict[str, str]] = []

            header, rows = rate_extraction_audit.read_csv_strict(path, issues)

        self.assertEqual(header, ["a", "b", "c"])
        self.assertEqual(rows[0]["c"], "")
        self.assertIn("csv_row_width_mismatch", {issue["check_id"] for issue in issues})
        self.assertEqual(issues[0]["severity"], "error")

    def test_analysis_ready_curated_rows_require_ready_qc_status(self) -> None:
        issues: list[dict[str, str]] = []
        source_rows = [{"source_id": "source-1"}]
        observation_rows = [
            {
                "observation_id": "obs-1",
                "source_id": "source-1",
                "analysis_ready": "1",
                "qa_status": "extracted_needs_independent_qc",
                "rate_derivation_basis": "reported_areal_rate",
                "observation_type": "reported_rate",
                "species": "Porites astreoides",
                "timepoint_or_interval": "8 d",
                "figure_or_table_label": "Table 1",
                "page": "5",
                "evidence_key": "pdf_page_5_table_1",
                "sample_size": "12",
                "variance_type": "SE",
                "variance_value": "1.2",
            }
        ]

        rate_extraction_audit.audit_curated_observations(issues, observation_rows, source_rows)

        self.assertIn("curated_ready_without_ready_qc", {issue["check_id"] for issue in issues})


class TraitCovariateCoverageTests(unittest.TestCase):
    def test_raw_overview_source_ids_keep_only_plotted_rows(self) -> None:
        rows = [
            {"source_id": "s2", "plot_status": "not_plotted"},
            {"source_id": "s1", "plot_status": "plotted"},
            {"source_id": "s1", "plot_status": "plotted_duplicate"},
            {"source_id": "s3", "plot_status": "plotted_from_legacy"},
        ]

        self.assertEqual(trait_covariate_audit.source_ids_raw_overview(rows), ["s1", "s3"])

    def test_missing_model_covariate_layer_reports_model_fields_absent(self) -> None:
        covariate_rows = [
            {
                "source_id": "s1",
                "paper_title": "Paper",
                "species": "Porites astreoides",
                "growth_form": "massive",
                "tissue_type": "perforate",
                "notes": "",
            }
        ]

        rows = trait_covariate_audit.build_coverage(covariate_rows, [], {"test_set": ["s1"]})
        by_field = {row["field"]: row for row in rows}

        self.assertEqual(by_field["species"]["n_present"], 1)
        self.assertEqual(by_field["family"]["field_status"], "model_column_absent")
        self.assertEqual(by_field["skeletal_porosity"]["field_status"], "model_column_absent")
        self.assertEqual(by_field["tissue_type_mentions_perforate_or_imperforate"]["n_present"], 1)

    def test_model_covariate_layer_counts_model_ready_trait_fields(self) -> None:
        covariate_rows = [
            {"source_id": "s1", "species": "Porites astreoides", "growth_form": "massive", "tissue_type": "perforate"}
        ]
        model_rows = [
            {
                "source_id": "s1",
                "genus": "Porites",
                "family": "Poritidae",
                "growth_form_standard": "massive_submassive",
                "skeletal_porosity": "perforate",
            }
        ]

        rows = trait_covariate_audit.build_coverage(covariate_rows, model_rows, {"test_set": ["s1"]})
        by_field = {row["field"]: row for row in rows}

        self.assertEqual(by_field["family"]["field_status"], "model_column_present")
        self.assertEqual(by_field["family"]["n_present"], 1)
        self.assertEqual(by_field["skeletal_porosity"]["n_present"], 1)


class AllResponseExtractionTests(unittest.TestCase):
    def test_covariate_prefill_prefers_model_covariates_for_taxon_traits(self) -> None:
        value, status, source = all_response_extraction.covariate_prefill(
            "family",
            {"species": "Porites astreoides"},
            {"family": "Poritidae"},
            Path("notebook_covariates/notebook_covariates_primary_geoaugmented.csv"),
            Path("data/extraction/meta_analysis/META_ANALYSIS_COVARIATES.csv"),
        )

        self.assertEqual(value, "Poritidae")
        self.assertEqual(status, "existing_model_covariate")
        self.assertEqual(source, "data/extraction/meta_analysis/META_ANALYSIS_COVARIATES.csv")
        self.assertEqual(all_response_extraction.needs_pdf_verification("family", status), 0)
        self.assertEqual(all_response_extraction.needs_pdf_verification("depth_m", status), 1)

    def test_text_windows_and_snippets_find_response_covariate_evidence(self) -> None:
        text = (
            "Methods. Circular lesions were made with a Dremel tool on each colony. "
            "Initial lesion area was 50 mm2 and wounds were photographed after 30 days. "
            "Treatment tanks were maintained at 29 degrees C with n = 12 colonies."
        )

        windows = all_response_extraction.text_windows(text)
        snippets = all_response_extraction.snippets_for("initial_wound_area_mm2", windows)
        sample_size = all_response_extraction.snippets_for("sample_size", windows)

        self.assertTrue(windows)
        self.assertTrue(any("Initial lesion area" in snippet for snippet in snippets))
        self.assertTrue(any("n = 12" in snippet for snippet in sample_size))

    def test_notebooklm_batches_are_response_specific_and_deduplicated(self) -> None:
        workplan_rows = [
            {"source_id": "s1", "response_type": "rate"},
            {"source_id": "s1", "response_type": "rate"},
            {"source_id": "s2", "response_type": "rate"},
            {"source_id": "s3", "response_type": "survival"},
        ]
        schema_rows = [
            {"tier": "1", "covariate": "taxon_raw"},
            {"tier": "2", "covariate": "depth_m"},
            {"tier": "3", "covariate": "family"},
        ]

        rows = all_response_extraction.build_notebooklm_batches(workplan_rows, schema_rows, batch_size=1)

        self.assertEqual([row["batch_id"] for row in rows], ["rate_01", "rate_02", "survival_01"])
        self.assertEqual(rows[0]["source_ids"], "s1")
        self.assertIn("taxon_raw", rows[0]["query_prompt"])
        self.assertIn("depth_m", rows[0]["query_prompt"])
        self.assertNotIn("family", rows[0]["query_prompt"])


class NotebookLMValidationTests(unittest.TestCase):
    def test_parse_answer_stats_accepts_cli_json_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "batch.json"
            path.write_text(json.dumps({"answer": "abc", "sources_used": ["s1", "s2"]}), encoding="utf-8")

            answer_chars, sources_used_count = notebooklm_validation.parse_answer_stats(path)

        self.assertEqual(answer_chars, 3)
        self.assertEqual(sources_used_count, 2)

    def test_audit_prompt_is_concise_validation_not_full_csv_extraction(self) -> None:
        prompt = notebooklm_validation.validation_prompt("growth")

        self.assertIn("Validate the extraction scaffold", prompt)
        self.assertIn("growth sources", prompt)
        self.assertIn("key missing covariates", prompt)
        self.assertNotIn("Return strict CSV rows", prompt)


class NotebookLMDatasetAuditTests(unittest.TestCase):
    def test_split_source_ids_accepts_single_pipe_and_comma_lists(self) -> None:
        row = {"source_id": "s1", "source_ids": "s2|s3,s4"}

        self.assertEqual(notebooklm_dataset_audit.split_source_ids(row), ["s1", "s2", "s3", "s4"])

    def test_title_similarity_handles_notebook_filename_format(self) -> None:
        similarity = notebooklm_dataset_audit.title_similarity(
            "Bak and Steward-Van Es - 1980 - Regeneration of superficial damage in the scleractinian corals.pdf",
            "Bak_1980_Regeneration_of_superficial_damage_in_the_scleractinian_cora....pdf",
        )

        self.assertGreaterEqual(similarity, 0.35)

    def test_support_for_value_detects_direct_and_token_matches(self) -> None:
        content = (
            "Methods. Circular lesions were made at 18-23 m. "
            "The experimental colonies were Porites astreoides and Agaricia agaricites."
        )

        direct = notebooklm_dataset_audit.support_for_value("Porites astreoides", content)
        token = notebooklm_dataset_audit.support_for_value("Agaricia at 18-23 m", content)

        self.assertEqual(direct["support_status"], "direct_string_match")
        self.assertIn(token["support_status"], {"high_token_match", "partial_token_or_numeric_match"})

    def test_derived_target_covariates_are_not_forced_to_paper_text(self) -> None:
        records = {}
        notebooklm_dataset_audit.add_value_record(
            records,
            source_id="s1",
            paper_title="Paper",
            covariate="family",
            value="Poritidae",
            kind="derived_or_model_covariate",
            dataset_file=Path("data/extraction/all_responses/ALL_RESPONSE_COVARIATE_TARGETS.csv"),
        )

        [record] = records.values()
        self.assertEqual(record["value_kind"], "derived_or_model_covariate")
        self.assertEqual(record["row_count"], 1)


class AnalysisReadyGateTests(unittest.TestCase):
    def test_label_matching_handles_fig_abbreviations_and_compound_labels(self) -> None:
        row = {
            "source_id": "s1",
            "response_type": "rate",
            "figure_or_table_label": "Figure 1; Table 1",
            "page": "4",
        }
        crop_rows = [
            {
                "source_id": "s1",
                "response_type": "rate",
                "candidate_label": "Fig. 1",
                "pdf_page": "4",
            },
            {
                "source_id": "s1",
                "response_type": "rate",
                "candidate_label": "Figure 2",
                "pdf_page": "4",
            },
        ]

        matches = analysis_ready_gate.crop_rows_for_observation(row, crop_rows)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["candidate_label"], "Fig. 1")

    def test_figure_row_blocks_on_unreviewed_placeholder_digitization(self) -> None:
        row = {
            "normalized_row_id": "row-1",
            "source_table": "data/extraction/rate/RATE_EXTRACTED_OBSERVATIONS.csv",
            "source_row": "2",
            "source_id": "s1",
            "response_type": "rate",
            "taxon_raw": "Acropora pulchra",
            "response_value": "1.2",
            "response_unit": "mm d-1",
            "sample_size": "12",
            "figure_or_table_label": "Figure 1",
            "page": "4",
            "qa_status": "extracted_needs_independent_qc",
        }
        original = {
            "timepoint_or_interval": "14 d",
            "variance_type": "SE",
            "variance_value": "0.2",
        }
        crop_rows = [
            {
                "source_id": "s1",
                "response_type": "rate",
                "candidate_label": "Fig. 1",
                "pdf_page": "4",
                "crop_review_status": "needs_human_crop_box_qa",
                "final_clip_path": "digitization/figures/s1__rate__fig-1_panel-<panel>.png",
                "digitized_data_path": "digitization/data/s1__rate__fig-1_panel-<panel>.csv",
            }
        ]

        audit_row, issues = analysis_ready_gate.audit_observation(row, original, crop_rows)
        issue_ids = {issue["issue_id"] for issue in issues}

        self.assertEqual(audit_row["analysis_ready"], 0)
        self.assertIn("qa_status_not_ready", issue_ids)
        self.assertIn("figure_crop_not_qc_passed", issue_ids)
        self.assertIn("figure_final_clip_missing", issue_ids)
        self.assertIn("figure_digitized_data_missing", issue_ids)

    def test_survival_raw_counts_satisfy_variance_requirement_but_not_qc(self) -> None:
        row = {
            "normalized_row_id": "row-1",
            "source_table": "data/extraction/EXTRACTION_SURVIVAL.csv",
            "source_row": "2",
            "source_id": "s1",
            "response_type": "survival",
            "taxon_raw": "Pocillopora damicornis",
            "control_value": "14",
            "wounded_value": "24",
            "sample_size": "38",
            "duration_days": "395",
            "figure_or_table_label": "Table 2",
            "page": "6",
            "qa_status": "needs_source_provenance_review",
        }
        original = {
            "Control_Total": "14",
            "Control_Dead": "1",
            "Wounded_Total": "24",
            "Wounded_Dead": "14",
        }

        audit_row, issues = analysis_ready_gate.audit_observation(row, original, [])
        issue_ids = {issue["issue_id"] for issue in issues}

        self.assertEqual(audit_row["analysis_ready"], 0)
        self.assertNotIn("variance_missing", issue_ids)
        self.assertIn("qa_status_not_ready", issue_ids)


class MetaAnalysisInputTests(unittest.TestCase):
    def test_taxon_lookup_prefers_coral_homonym(self) -> None:
        record = taxon_trait_lookup.select_coral_record(
            [
                {
                    "scientificname": "Acropora",
                    "rank": "Genus",
                    "status": "unaccepted",
                    "valid_name": "Porina",
                    "family": "Porinidae",
                    "order": "Cheilostomatida",
                    "class": "Gymnolaemata",
                    "phylum": "Bryozoa",
                },
                {
                    "scientificname": "Acropora",
                    "rank": "Genus",
                    "status": "accepted",
                    "valid_name": "Acropora",
                    "family": "Acroporidae",
                    "order": "Scleractinia",
                    "class": "Hexacorallia",
                    "phylum": "Cnidaria",
                },
            ]
        )

        assert record is not None
        self.assertEqual(record["family"], "Acroporidae")

    def test_model_covariates_normalize_taxonomy_traits_and_numeric_fields(self) -> None:
        lookup = model_covariates.lookup_by_genus(
            [
                {
                    "genus_raw": "Acropora",
                    "genus": "Acropora",
                    "family": "Acroporidae",
                    "taxonomy_lookup_status": "worms_scleractinia_match",
                }
            ]
        )

        row = model_covariates.build_covariate_row(
            {
                "source_id": "s1",
                "paper_title": "Paper",
                "species": "Acropora palmata",
                "growth_form": "branched",
                "tissue_type": "perforate",
                "study_type": "field",
                "depth_min_m": "2",
                "depth_max_m": "4",
                "area_mm2": "35, 105",
                "temperature_c": "26-31",
                "ph_or_pco2": "400, 1000 uatm",
            },
            lookup,
        )

        self.assertEqual(row["genus"], "Acropora")
        self.assertEqual(row["family"], "Acroporidae")
        self.assertEqual(row["growth_form_standard"], "branching")
        self.assertEqual(row["skeletal_porosity"], "perforate")
        self.assertEqual(row["field_lab_mesocosm"], "field")
        self.assertEqual(float(row["depth_mid_m"]), 3.0)
        self.assertEqual(float(row["initial_wound_area_mid_mm2"]), 70.0)
        self.assertEqual(float(row["temperature_mid_c"]), 28.5)
        self.assertEqual(float(row["pCO2_uatm_mid"]), 700.0)

    def test_model_covariates_do_not_collapse_multi_taxon_porosity_candidate(self) -> None:
        lookup = model_covariates.lookup_by_genus(
            [
                {"genus_raw": "Porites", "genus": "Porites", "family": "Poritidae"},
                {"genus_raw": "Pocillopora", "genus": "Pocillopora", "family": "Pocilloporidae"},
            ]
        )

        row = model_covariates.build_covariate_row(
            {
                "source_id": "s1",
                "paper_title": "Paper",
                "species": "Porites spp., Pocillopora meandrina",
                "growth_form": "massive, branching",
                "tissue_type": "perforate",
                "study_type": "field",
            },
            lookup,
        )

        self.assertEqual(row["taxon_parse_status"], "multi_taxon")
        self.assertEqual(row["skeletal_porosity_candidates"], "perforate")
        self.assertEqual(row["skeletal_porosity"], "")
        self.assertEqual(row["skeletal_porosity_model_status"], "single_porosity_candidate_multi_taxon_not_model_ready")

    def test_sampling_variance_from_se_sd_and_ci(self) -> None:
        self.assertEqual(meta_analysis_inputs.sampling_variance_from_summary("SE", "0.5", 31), (0.25, None))
        self.assertEqual(meta_analysis_inputs.sampling_variance_from_summary("SD", "2", 4), (1.0, None))

        vi, blocker = meta_analysis_inputs.sampling_variance_from_summary("95% CI", "0.170-0.267", None)

        self.assertIsNone(blocker)
        self.assertAlmostEqual(vi, ((0.267 - 0.170) / (2 * 1.96)) ** 2)

    def test_survival_effect_uses_log_odds_ratio_for_mortality(self) -> None:
        yi, vi, blocker = meta_analysis_inputs.survival_effect(
            {
                "Control_Total": "10",
                "Control_Dead": "1",
                "Wounded_Total": "10",
                "Wounded_Dead": "4",
            }
        )

        self.assertIsNone(blocker)
        self.assertAlmostEqual(float(yi), math.log((4 * 9) / (6 * 1)))
        self.assertAlmostEqual(float(vi), 1 / 4 + 1 / 6 + 1 / 1 + 1 / 9)

    def test_continuous_rom_blocks_when_group_sample_sizes_are_unknown(self) -> None:
        yi, vi, blocker = meta_analysis_inputs.continuous_rom_effect(
            {"control_value": "6.2", "wounded_value": "5.1", "variance_type": "SE", "sample_size": "57"},
            {"Control_Var": "0.08", "Wounded_Var": "0.07"},
        )

        selfEqual = self.assertEqual
        selfEqual(yi, "")
        selfEqual(vi, "")
        selfEqual(blocker, "group_sample_sizes_missing")

    def test_ready_rate_row_becomes_model_input_when_yi_vi_are_computable(self) -> None:
        row = {
            "normalized_row_id": "row-1",
            "source_table": "data/extraction/rate/RATE_EXTRACTED_OBSERVATIONS.csv",
            "source_row": "2",
            "source_id": "s1",
            "response_type": "rate",
            "taxon_raw": "Porites astreoides",
            "rate_value": "12.4",
            "rate_unit": "mm2 d-1",
            "variance_type": "SE",
            "variance_value": "0.5",
            "sample_size": "31",
            "timepoint_or_interval": "first 8 d",
            "figure_or_table_label": "Table 1",
            "page": "5",
            "value_data_file": "data/extraction/rate/RATE_EXTRACTED_OBSERVATIONS.csv",
        }
        issues: list[dict[str, str]] = []

        meta_row = meta_analysis_inputs.build_meta_row(row, {}, {}, issues)

        self.assertEqual(meta_row["model_include"], 1)
        self.assertEqual(meta_row["effect_size_metric"], "raw_rate_or_endpoint_mean")
        self.assertEqual(meta_row["analysis_stratum"], "rate:absolute_areal_rate:mm2_d_1")
        self.assertEqual(float(meta_row["yi"]), 12.4)
        self.assertEqual(float(meta_row["vi"]), 0.25)
        self.assertEqual(issues, [])

    def test_meta_row_carries_normalized_covariates(self) -> None:
        row = {
            "normalized_row_id": "row-1",
            "source_id": "s1",
            "response_type": "rate",
            "taxon_raw": "Porites astreoides",
            "rate_value": "12.4",
            "rate_unit": "mm2 d-1",
            "variance_type": "SE",
            "variance_value": "0.5",
            "sample_size": "31",
        }
        model_covariate = {
            "genus": "Porites",
            "family": "Poritidae",
            "growth_form_standard": "massive_submassive",
            "skeletal_porosity": "perforate",
            "field_lab_mesocosm": "field",
            "depth_mid_m": "5",
            "initial_wound_area_mid_mm2": "100",
            "covariate_readiness_status": "core_covariates_ready",
        }
        issues: list[dict[str, str]] = []

        meta_row = meta_analysis_inputs.build_meta_row(row, {}, {}, issues, model_covariate)

        self.assertEqual(meta_row["model_include"], 1)
        self.assertEqual(meta_row["family"], "Poritidae")
        self.assertEqual(meta_row["skeletal_porosity"], "perforate")
        self.assertEqual(meta_row["growth_form_standard"], "massive_submassive")
        self.assertEqual(meta_row["depth_mid_m"], "5")


class FigureIndexAuditTests(unittest.TestCase):
    def test_source_id_prefix_collisions_are_blocking_index_errors(self) -> None:
        issues: list[dict[str, str]] = []

        figure_index_audit.audit_prefixes(
            issues,
            {
                "12345678-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "12345678-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "87654321-cccc-cccc-cccc-cccccccccccc",
            },
        )

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["severity"], "error")
        self.assertEqual(issues[0]["check"], "source_id_prefix_collision")

    def test_concrete_digitized_data_paths_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            source_path = tmp_root / "digitization" / "figures" / "source_pages" / "source__page-001.png"
            crop_path = tmp_root / "digitization" / "figures" / "crop_review" / "source__rate__figure-fig-1__page-1__crop-001.png"
            try:
                from PIL import Image
            except Exception as exc:  # pragma: no cover - test environment should provide Pillow.
                self.skipTest(f"Pillow unavailable: {exc}")
            source_path.parent.mkdir(parents=True)
            crop_path.parent.mkdir(parents=True)
            Image.new("RGB", (100, 100), color=(255, 255, 255)).save(source_path)
            Image.new("RGB", (50, 50), color=(255, 255, 255)).save(crop_path)

            crop_rows = [
                {
                    "crop_row_type": "accepted_visual_candidate",
                    "crop_status": "auto_crop_proposal_created",
                    "queue_id": "DIG-source-rate",
                    "source_id": "source-1",
                    "response_type": "rate",
                    "candidate_descriptor": "figure:Fig. 1:p1",
                    "crop_path": "digitization/figures/crop_review/source__rate__figure-fig-1__page-1__crop-001.png",
                    "source_page_render": "digitization/figures/source_pages/source__page-001.png",
                    "source_page_width": "100",
                    "source_page_height": "100",
                    "crop_box_xywh": "10,10,50,50",
                    "digitized_data_path": "digitization/data/source__rate__figure-fig-1_panel-all.csv",
                    "final_clip_path": "digitization/figures/source__rate__figure-fig-1_panel-all.png",
                }
            ]
            visual_rows = [
                {
                    "reaudit_row_type": "accepted_visual_candidate",
                    "queue_id": "DIG-source-rate",
                    "candidate_descriptor": "figure:Fig. 1:p1",
                }
            ]

            with patch.object(figure_index_audit, "ROOT", tmp_root), patch.object(
                figure_index_audit, "CROP_REVIEW_DIR", tmp_root / "digitization" / "figures" / "crop_review"
            ), patch.object(
                figure_index_audit, "DIGITIZED_DATA_DIR", tmp_root / "digitization" / "data"
            ):
                issues: list[dict[str, str]] = []
                stats = figure_index_audit.audit_crop_manifest(issues, crop_rows, visual_rows)

        self.assertEqual(stats["concrete_digitized_data_paths"], 1)
        self.assertEqual(stats["missing_concrete_digitized_data_paths"], 1)
        self.assertIn("digitized_data_path_missing", {issue["check"] for issue in issues})


if __name__ == "__main__":
    unittest.main()
