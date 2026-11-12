"""Ядро сравнения двух моделей. Не зависит от OCC — работает на моделях данных."""
from __future__ import annotations

from .models import (
    DiffResult, MetricDiff, Metrics, TopologyInfo, Verdict,
)


def _rel_diff(a: float, b: float) -> float:
    """Относительное расхождение с защитой от деления на ноль."""
    denom = max(abs(a), abs(b))
    if denom == 0.0:
        return 0.0
    return abs(a - b) / denom


def _compare_scalar(name: str, a: float, b: float, tol: float) -> MetricDiff:
    abs_diff = abs(a - b)
    rel_diff = _rel_diff(a, b)
    return MetricDiff(
        name=name,
        a=a, b=b,
        abs_diff=abs_diff,
        rel_diff=rel_diff,
        within_tol=abs_diff <= tol,
    )


def compare_metrics(a: Metrics, b: Metrics, tol: float = 1e-6) -> list[MetricDiff]:
    """Сравнивает скалярные метрики. Возвращает список расхождений."""
    diffs: list[MetricDiff] = []

    diffs.append(_compare_scalar("volume", a.volume, b.volume, tol))
    diffs.append(_compare_scalar("surface_area", a.surface_area, b.surface_area, tol))

    # центр масс — покомпонентно
    for axis, (ca, cb) in zip("xyz", zip(a.center_of_mass, b.center_of_mass)):
        diffs.append(_compare_scalar(f"com_{axis}", ca, cb, tol))

    # габариты
    for axis, (da, db) in zip("xyz", zip(a.bbox, b.bbox)):
        diffs.append(_compare_scalar(f"bbox_{axis}", da, db, tol))

    return diffs


def compare_topology(a: TopologyInfo, b: TopologyInfo) -> dict[str, tuple[int, int]]:
    """Возвращает только те счётчики, которые различаются: {name: (a, b)}."""
    counts = {
        "n_solids": (a.n_solids, b.n_solids),
        "n_shells": (a.n_shells, b.n_shells),
        "n_faces": (a.n_faces, b.n_faces),
        "n_wires": (a.n_wires, b.n_wires),
        "n_edges": (a.n_edges, b.n_edges),
        "n_vertices": (a.n_vertices, b.n_vertices),
    }
    diffs = {k: v for k, v in counts.items() if v[0] != v[1]}

    # типы граней
    for ftype in set(a.face_types) | set(b.face_types):
        ca = a.face_types.get(ftype, 0)
        cb = b.face_types.get(ftype, 0)
        if ca != cb:
            diffs[f"face_type:{ftype}"] = (ca, cb)

    return diffs


def compare(
    metrics_a: Metrics | None,
    metrics_b: Metrics | None,
    topology_a: TopologyInfo | None = None,
    topology_b: TopologyInfo | None = None,
    tol: float = 1e-6,
) -> DiffResult:
    """Главная функция ядра.
    
    Правила вердикта:
      - любая метрика вне допуска  -> MISMATCH
      - любое топологическое расхождение -> MISMATCH
      - иначе -> MATCH
    """
    result = DiffResult(verdict=Verdict.MATCH, tolerance=tol,
                        metrics_a=metrics_a, metrics_b=metrics_b,
                        topology_a=topology_a, topology_b=topology_b)

    if metrics_a is None or metrics_b is None:
        result.verdict = Verdict.ERROR
        result.messages.append("Одна из моделей не загружена (metrics is None)")
        return result

    result.metric_diffs = compare_metrics(metrics_a, metrics_b, tol)
    bad_metrics = [d for d in result.metric_diffs if not d.within_tol]
    if bad_metrics:
        result.verdict = Verdict.MISMATCH
        for d in bad_metrics:
            result.messages.append(
                f"metric '{d.name}': |{d.a:.6g} - {d.b:.6g}| = {d.abs_diff:.3g} > tol {tol:g}"
            )

    if topology_a is not None and topology_b is not None:
        result.topology_diffs = compare_topology(topology_a, topology_b)
        if result.topology_diffs:
            result.verdict = Verdict.MISMATCH
            for name, (ca, cb) in result.topology_diffs.items():
                result.messages.append(f"topology '{name}': {ca} != {cb}")

    return result