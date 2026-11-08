"""Геометрические свойства модели (участник 6).

compute_metrics(shape) -> Metrics: объём, площадь поверхности, центр масс, габариты,
количество граней и рёбер.
Зависит только от pythonocc-core. Чужой код заменён заглушками [Код участника N].
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

# --- Metrics: по плану лежит в models.py у участника 1 ---
try:
    from stepdiff.models import Metrics  # [Код участника 1]
except ImportError:
    print("[Код участника 1: models.Metrics]")

    @dataclass
    class Metrics:  # type: ignore[no-redef]
        """Временная копия, пока участник 1 не зафиксировал models.py."""

        volume: float
        surface_area: float
        center_of_mass: tuple[float, float, float]
        bbox_min: tuple[float, float, float]
        bbox_max: tuple[float, float, float]
        bbox_size: tuple[float, float, float]
        n_faces: int = 0
        n_edges: int = 0
        units: str = "mm"


DEFAULT_UNITS = "mm"


def _volume_props(shape: Any) -> Any:
    from OCC.Core.GProp import GProp_GProps

    props = GProp_GProps()
    try:
        from OCC.Core.BRepGProp import brepgprop

        brepgprop.VolumeProperties(shape, props)
    except ImportError:  # старые версии pythonocc
        from OCC.Core.BRepGProp import brepgprop_VolumeProperties

        brepgprop_VolumeProperties(shape, props)
    return props


def _surface_area(shape: Any) -> float:
    from OCC.Core.GProp import GProp_GProps

    props = GProp_GProps()
    try:
        from OCC.Core.BRepGProp import brepgprop

        brepgprop.SurfaceProperties(shape, props)
    except ImportError:
        from OCC.Core.BRepGProp import brepgprop_SurfaceProperties

        brepgprop_SurfaceProperties(shape, props)
    return float(props.Mass())


def _bounding_box(shape: Any) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Точный габаритный параллелепипед (без зазора по допускам)."""
    from OCC.Core.Bnd import Bnd_Box

    box = Bnd_Box()
    try:
        from OCC.Core.BRepBndLib import brepbndlib

        brepbndlib.AddOptimal(shape, box, False, False)
    except (ImportError, AttributeError):
        from OCC.Core.BRepBndLib import brepbndlib_AddOptimal

        brepbndlib_AddOptimal(shape, box, False, False)
    x0, y0, z0, x1, y1, z1 = box.Get()
    return (x0, y0, z0), (x1, y1, z1)


def _count_topology(shape: Any) -> tuple[int, int]:
    """Считает количество граней и рёбер в топологии B-rep (уникальные)."""
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE
    from OCC.Core.TopTools import TopTools_IndexedMapOfShape
    from OCC.Core.TopExp import topexp  # ← импорт класса, а не функции

    face_map = TopTools_IndexedMapOfShape()
    topexp.MapShapes(shape, TopAbs_FACE, face_map)  # ← точка вместо подчёркивания
    n_faces = face_map.Extent()

    edge_map = TopTools_IndexedMapOfShape()
    topexp.MapShapes(shape, TopAbs_EDGE, edge_map)  # ← точка вместо подчёркивания
    n_edges = edge_map.Extent()

    return n_faces, n_edges


def compute_metrics(shape: Any, units: str = DEFAULT_UNITS) -> Metrics:
    """Считает метрики одной формы.

    shape — TopoDS_Shape. В реальной цепочке сюда придёт ShapeData от участника 4:
    тогда форму и единицы берём из него.
    """
    # [Код участника 4]: ShapeData(shape=..., units=...) -> shape.shape, shape.units
    if hasattr(shape, "shape") and hasattr(shape, "units"):
        units, shape = shape.units, shape.shape

    props = _volume_props(shape)
    volume = float(props.Mass())
    if volume <= 0:
        raise ValueError("Нулевой или отрицательный объём: форма пустая или не замкнута")

    com = props.CentreOfMass()
    bmin, bmax = _bounding_box(shape)
    size = tuple(hi - lo for lo, hi in zip(bmin, bmax))
    n_faces, n_edges = _count_topology(shape)

    return Metrics(
        volume=volume,
        surface_area=_surface_area(shape),
        center_of_mass=(com.X(), com.Y(), com.Z()),
        bbox_min=bmin,
        bbox_max=bmax,
        bbox_size=size,  # type: ignore[arg-type]
        n_faces=n_faces,
        n_edges=n_edges,
        units=units,
    )


if __name__ == "__main__":
    # быстрая проверка без остальных модулей: коробка 10x20x30
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox

    result = compute_metrics(BRepPrimAPI_MakeBox(10, 20, 30).Shape())
    print(result)
    print(f"Грани: {result.n_faces}, Рёбра: {result.n_edges}")
    print("[Код участника 4: загрузка файла]")