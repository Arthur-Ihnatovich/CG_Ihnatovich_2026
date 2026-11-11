"""Проверка алгоритмов на случайных отрезках (цифры для отчета).

Для 3000 случайных отрезков проверяем: концы на месте, разрывов нет и каждый пиксель
не дальше 0.5 клетки от прямой. Отклонение считаем точно, через Fraction.
Ничья - прямая проходит ровно посередине между двумя пикселями (отклонение 0.5).
Еще проверяем накопление ошибки в ЦДА и окружности с R от 0 до 100.
Запуск: python check.py
"""
import math
import random
from fractions import Fraction

import raster

LINE_ALGORITHMS = {
    "Пошаговый": raster.step_by_step,
    "ЦДА": raster.dda,
    "Брезенхем": raster.bresenham_line,
}
COUNT = 3000


def exact_line(x1, y1, x2, y2):
    """Пошаговый алгоритм в точных дробях (Fraction), половинки округляются вверх."""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return [(x1, y1)]
    points = []
    if abs(dx) >= abs(dy):
        step = 1 if dx > 0 else -1
        for x in range(x1, x2 + step, step):
            y = y1 + Fraction(dy, dx) * (x - x1)
            points.append((x, math.floor(y + Fraction(1, 2))))
    else:
        step = 1 if dy > 0 else -1
        for y in range(y1, y2 + step, step):
            x = x1 + Fraction(dx, dy) * (y - y1)
            points.append((math.floor(x + Fraction(1, 2)), y))
    return points


def deviations(points, x1, y1, x2, y2):
    """Отклонение каждого пикселя от прямой по короткой оси, точно."""
    dx, dy = x2 - x1, y2 - y1
    result = []
    for x, y in points:
        if dx == 0 and dy == 0:
            result.append(Fraction(0))
        elif abs(dx) >= abs(dy):
            result.append(abs(y - (y1 + Fraction(dy, dx) * (x - x1))))
        else:
            result.append(abs(x - (x1 + Fraction(dx, dy) * (y - y1))))
    return result


def has_gap_or_wrong_ends(points, x1, y1, x2, y2):
    """True, если концы не те, пикселей не столько, сколько нужно, или есть разрыв."""
    if points[0] != (x1, y1) or points[-1] != (x2, y2):
        return True
    if len(points) != max(abs(x2 - x1), abs(y2 - y1)) + 1:
        return True
    return any(abs(xb - xa) > 1 or abs(yb - ya) > 1 for (xa, ya), (xb, yb) in zip(points, points[1:]))


random.seed(3)
segments = [tuple(random.randint(-50, 50) for _ in range(4)) for _ in range(COUNT)]
with_tie = sum(Fraction(1, 2) in deviations(exact_line(*s), *s) for s in segments)

print(f"отрезков: {COUNT} (концы от -50 до 50), из них с ничьей: {with_tie}\n")
print(f"{'алгоритм':14}{'ошибок':>8}{'макс. откл.':>13}{'как Брезенхем':>15}{'ничья не по правилу':>21}")
for name, function in LINE_ALGORITHMS.items():
    bad, worst, same, wrong_tie = 0, 0, 0, 0
    for segment in segments:
        points = function(*segment)
        deviation = max(deviations(points, *segment))
        worst = max(worst, deviation)
        bad += has_gap_or_wrong_ends(points, *segment) or deviation > Fraction(1, 2)
        same += points == raster.bresenham_line(*segment)
        wrong_tie += points != exact_line(*segment)
    tie_text = f"{wrong_tie} ({wrong_tie / COUNT:.1%})" if function in (raster.step_by_step, raster.dda) else "-"
    print(f"{name:14}{bad:8}{float(worst):13.2f}{same / COUNT:15.1%}{tie_text:>21}")
print("(у Брезенхема ничья решается без дробей, поэтому там прочерк)")

# ЦДА: насколько сумма dy/L расходится с умножением
worst = 0
for length in (10, 100, 1000):
    for dy in range(length + 1):
        y, k = 0.0, dy / length
        for i in range(1, length + 1):
            y += k
            worst = max(worst, abs(y - k * i))
print(f"\nЦДА: макс. накопленная ошибка на отрезках до 1000 шагов: {worst:.1e}")

# окружности
worst, bad = 0, 0
for r in range(101):
    points = set(raster.bresenham_circle(0, 0, r))
    worst = max(worst, max(abs(math.hypot(x, y) - r) for x, y in points))
    symmetric = points == {(y, x) for x, y in points} == {(-x, y) for x, y in points} == {(x, -y) for x, y in points}
    # нет разрыва, если у каждого пикселя хотя бы 2 соседа (по стороне или по углу)
    connected = r == 0 or all(
        sum((x + i, y + j) in points for i in (-1, 0, 1) for j in (-1, 0, 1) if i or j) >= 2
        for x, y in points)
    bad += not (symmetric and connected)
print(f"\nокружности R = 0..100: макс. отклонение {worst:.3f}, нет симметрии или есть разрыв: {bad}")
