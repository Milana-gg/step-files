# stepdiff-qa

Проект для сравнения CAD-моделей (STEP/BREP).

## Как использовать ядро сравнения (Модуль 1)
Модуль `comparator.py` не зависит от OCC и работает с готовыми структурами данных.
Импортируйте функцию `compare` и передайте ей метрики и топологию двух моделей:

```python
from src.step_compare.comparator import compare
from src.step_compare.models import Metrics, TopologyInfo

# Получаете метрики от участника 6 и топологию от участника 8
result = compare(metrics_a, metrics_b, topo_a, topo_b, tol=1e-6)

if result.is_match:
    print("Модели совпадают!")
else:
    print("Расхождения:", result.messages)
