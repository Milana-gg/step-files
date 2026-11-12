"""Общие структуры данных проекта step-compare.

Все модули обмениваются только этими типами — это контракт.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Verdict(str, Enum):
    MATCH = "match"
    MISMATCH = "mismatch"
    ERROR = "error"


@dataclass(frozen=True)
class ShapeData:
    """Результат загрузки файла (участник 4)."""
    shape: Any                      
    filename: str
    units: str = "mm"
    n_solids: int = 0
    is_valid: bool = True
    error: str | None = None


@dataclass
class Metrics:
    """Геометрические метрики одной модели (участник 6)."""
    volume: float
    surface_area: float
    center_of_mass: tuple[float, float, float]
    bbox: tuple[float, float, float]   # dx, dy, dz

    def as_dict(self) -> dict[str, Any]:
        return {
            "volume": self.volume,
            "surface_area": self.surface_area,
            "center_of_mass": self.center_of_mass,
            "bbox": self.bbox,
        }


@dataclass
class TopologyInfo:
    """Топологическая структура модели (участник 8)."""
    n_solids: int = 0
    n_shells: int = 0
    n_faces: int = 0
    n_wires: int = 0
    n_edges: int = 0
    n_vertices: int = 0
    face_types: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_solids": self.n_solids,
            "n_shells": self.n_shells,
            "n_faces": self.n_faces,
            "n_wires": self.n_wires,
            "n_edges": self.n_edges,
            "n_vertices": self.n_vertices,
            "face_types": self.face_types,
        }


@dataclass
class MetricDiff:
    """Расхождение по одной скалярной метрике."""
    name: str
    a: float
    b: float
    abs_diff: float
    rel_diff: float
    within_tol: bool


@dataclass
class DiffResult:
    """Итог сравнения двух моделей (ядро — участник 1)."""
    verdict: Verdict
    metrics_a: Metrics | None = None
    metrics_b: Metrics | None = None
    topology_a: TopologyInfo | None = None
    topology_b: TopologyInfo | None = None
    metric_diffs: list[MetricDiff] = field(default_factory=list)
    topology_diffs: dict[str, tuple[int, int]] = field(default_factory=dict)
    tolerance: float = 1e-6
    messages: list[str] = field(default_factory=list)

    @property
    def is_match(self) -> bool:
        return self.verdict is Verdict.MATCH