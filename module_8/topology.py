"""
Модуль 8: Топология B-rep.
Считает тела/оболочки/грани/рёбра/вершины, строит дерево структуры,
классифицирует поверхности и сравнивает топологию двух моделей.
"""

from __future__ import annotations

from OCC.Core.TopAbs import (
    TopAbs_SOLID, TopAbs_SHELL, TopAbs_FACE,
    TopAbs_WIRE, TopAbs_EDGE, TopAbs_VERTEX,
)
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopoDS import TopoDS_Shape
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import (
    GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone,
    GeomAbs_Sphere, GeomAbs_Torus, GeomAbs_BezierSurface,
    GeomAbs_BSplineSurface, GeomAbs_SurfaceOfRevolution,
    GeomAbs_SurfaceOfExtrusion, GeomAbs_OffsetSurface, GeomAbs_OtherSurface,
)

from models import TopologyInfo, FaceType, ShapeData


_TYPE_MAP = {
    "solids":  TopAbs_SOLID,
    "shells":  TopAbs_SHELL,
    "faces":   TopAbs_FACE,
    "wires":   TopAbs_WIRE,
    "edges":   TopAbs_EDGE,
    "vertices":TopAbs_VERTEX,
}


def _count(shape: TopoDS_Shape, kind: int) -> int:
    """Считает уникальные подобъекты заданного типа."""
    exp = TopExp_Explorer(shape, kind)
    seen, count = set(), 0
    while exp.More():
        item = exp.Current()
        key = item.HashCode()
        if key not in seen:
            seen.add(key)
            count += 1
        exp.Next()
    return count


def count_subshapes(shape: TopoDS_Shape) -> dict[str, int]:
    """Возвращает словарь с количеством тел/оболочек/граней/..."""
    return {name: _count(shape, kind) for name, kind in _TYPE_MAP.items()}


_FACE_TYPE_MAP = {
    GeomAbs_Plane:               FaceType.PLANE,
    GeomAbs_Cylinder:            FaceType.CYLINDER,
    GeomAbs_Cone:                FaceType.CONE,
    GeomAbs_Sphere:              FaceType.SPHERE,
    GeomAbs_Torus:               FaceType.TORUS,
    GeomAbs_BezierSurface:       FaceType.BEZIER,
    GeomAbs_BSplineSurface:      FaceType.BSPLINE,
    GeomAbs_SurfaceOfRevolution: FaceType.REVOLUTION,
    GeomAbs_SurfaceOfExtrusion:  FaceType.EXTRUSION,
    GeomAbs_OffsetSurface:       FaceType.OFFSET,
    GeomAbs_OtherSurface:        FaceType.OTHER,
}


def classify_faces(shape: TopoDS_Shape) -> dict[FaceType, int]:
    """Считает, сколько граней какого типа поверхности."""
    result: dict[FaceType, int] = {ft: 0 for ft in FaceType}
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = exp.Current()
        surf_type = BRepAdaptor_Surface(face).GetType()
        result[_FACE_TYPE_MAP[surf_type]] += 1
        exp.Next()
    return result


def build_topology_tree(shape: TopoDS_Shape) -> dict:
    """Строит дерево: Solid → Shell → Face → Wire → Edge → Vertex."""
    tree = []
    exp_s = TopExp_Explorer(shape, TopAbs_SOLID)
    while exp_s.More():
        solid = exp_s.Current()
        shells = []
        exp_h = TopExp_Explorer(solid, TopAbs_SHELL)
        while exp_h.More():
            shell = exp_h.Current()
            faces = []
            exp_f = TopExp_Explorer(shell, TopAbs_FACE)
            while exp_f.More():
                face = exp_f.Current()
                wires = []
                exp_w = TopExp_Explorer(face, TopAbs_WIRE)
                while exp_w.More():
                    wire = exp_w.Current()
                    edges = []
                    exp_e = TopExp_Explorer(wire, TopAbs_EDGE)
                    while exp_e.More():
                        edge = exp_e.Current()
                        verts = []
                        exp_v = TopExp_Explorer(edge, TopAbs_VERTEX)
                        while exp_v.More():
                            verts.append(exp_v.Current().HashCode())
                            exp_v.Next()
                        edges.append({"hash": edge.HashCode(), "vertices": verts})
                        exp_e.Next()
                    wires.append({"hash": wire.HashCode(), "edges": edges})
                    exp_w.Next()
                faces.append({"hash": face.HashCode(), "wires": wires})
                exp_f.Next()
            shells.append({"hash": shell.HashCode(), "faces": faces})
            exp_h.Next()
        tree.append({"hash": solid.HashCode(), "shells": shells})
        exp_s.Next()
    return tree


def get_topology_info(shape_data: ShapeData) -> TopologyInfo:
    """
    Вход: ShapeData из модуля 4 (загрузка файлов).
    Выход: TopologyInfo для модуля 1 (comparator).
    """
    shape = shape_data.shape
    counts = count_subshapes(shape)
    return TopologyInfo(
        file_name=shape_data.file_name,
        solids=counts["solids"],
        shells=counts["shells"],
        faces=counts["faces"],
        wires=counts["wires"],
        edges=counts["edges"],
        vertices=counts["vertices"],
        face_types=classify_faces(shape),
        tree=build_topology_tree(shape),
    )


def compare_topology(a: TopologyInfo, b: TopologyInfo) -> dict[str, tuple[int, int]]:
    """Сравнивает две топологии. Возвращает разницу по каждому показателю."""
    fields = ["solids", "shells", "faces", "wires", "edges", "vertices"]
    diff = {f: (getattr(a, f), getattr(b, f)) for f in fields}
    all_types = set(a.face_types) | set(b.face_types)
    diff["face_types"] = tuple(
        sum(1 for t in all_types if a.face_types.get(t, 0) != b.face_types.get(t, 0))
        for _ in [0]
    )
    return diff