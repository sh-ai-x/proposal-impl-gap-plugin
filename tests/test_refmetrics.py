from gap_plugin.refmetrics import CandidateDiagnostic, SectionDiagnostic, compute_metrics


def _diag(status: str, attempts: int, overlaps: list[float]) -> SectionDiagnostic:
    return SectionDiagnostic(
        doc_path="docs/proposals/x.md",
        section_id="s",
        status=status,
        attempts=attempts,
        candidates=[CandidateDiagnostic(file_path=f"f{i}.py", score=1.0, overlap=o) for i, o in enumerate(overlaps)],
    )


def test_completion_rate_is_fraction_resolved_as_answer() -> None:
    diags = [_diag("answer", 1, [0.9]), _diag("missing_info", 3, [0.1]), _diag("answer", 2, [0.5])]

    metrics = compute_metrics(diags, total_evidence_files=5)

    assert metrics.n_sections == 3
    assert metrics.retrieval_completion_rate == 2 / 3


def test_mean_attempts_and_first_try_rate() -> None:
    diags = [_diag("answer", 1, [0.9]), _diag("answer", 1, [0.8]), _diag("missing_info", 3, [0.1])]

    metrics = compute_metrics(diags, total_evidence_files=5)

    assert metrics.mean_attempts == (1 + 1 + 3) / 3
    assert metrics.first_try_rate == 2 / 3


def test_context_relevance_uses_best_candidate_overlap_per_section() -> None:
    diags = [_diag("answer", 1, [0.2, 0.9, 0.4]), _diag("missing_info", 3, [0.1, 0.3])]

    metrics = compute_metrics(diags, total_evidence_files=5)

    assert metrics.mean_context_relevance == (0.9 + 0.3) / 2


def test_context_relevance_is_zero_when_no_candidates_retrieved() -> None:
    diags = [_diag("missing_info", 3, [])]

    metrics = compute_metrics(diags, total_evidence_files=5)

    assert metrics.mean_context_relevance == 0.0


def test_evidence_diversity_is_distinct_cited_files_over_total() -> None:
    diags = [_diag("answer", 1, [0.9]), _diag("answer", 1, [0.8])]  # 2 distinct files: f0.py each section

    metrics = compute_metrics(diags, total_evidence_files=4)

    assert metrics.evidence_diversity == 1 / 4  # only "f0.py" ever cited, both sections' candidate 0


def test_empty_diagnostics_returns_nan_metrics_not_a_crash() -> None:
    metrics = compute_metrics([], total_evidence_files=0)

    assert metrics.n_sections == 0
    assert metrics.retrieval_completion_rate != metrics.retrieval_completion_rate  # NaN
