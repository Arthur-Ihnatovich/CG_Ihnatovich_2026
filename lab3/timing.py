"""Замер времени алгоритмов (таблица 5 в отчете).

Отрезки с наклоном 3/7 длиной n шагов, окружности радиуса n.
Сначала 12 с прогрева (первые секунды ноутбук работает на пониженной частоте),
потом 7 раундов по всем алгоритмам и для каждого берем минимальное время,
потому что фоновые программы могут время только увеличить.
Запуск: python timing.py (около 30 секунд)
"""
import time

from lab3_app import ALGORITHMS, measure_time

LENGTHS = [10, 100, 1000]
ROUNDS = 7
WARM_UP = 12   # секунд


def arguments(is_circle, n):
    return (0, 0, n) if is_circle else (0, 0, n, n * 3 // 7)


# прогрев
start = time.perf_counter()
while time.perf_counter() - start < WARM_UP:
    for function, is_circle, _ in ALGORITHMS.values():
        function(*arguments(is_circle, 1000))

# замеры по кругу: в каждом раунде все алгоритмы по разу
times = {(name, n): [] for name in ALGORITHMS for n in LENGTHS}
for _ in range(ROUNDS):
    for name, (function, is_circle, _) in ALGORITHMS.items():
        for n in LENGTHS:
            times[name, n].append(measure_time(function, arguments(is_circle, n))[0])

print(f"{'алгоритм':24}" + "".join(f"{'n = ' + str(n):>14}" for n in LENGTHS)
      + f"{'пикселей':>10}{'нс/пиксель':>12}")
for name, (function, is_circle, _) in ALGORITHMS.items():
    row = [min(times[name, n]) for n in LENGTHS]
    pixels = len(function(*arguments(is_circle, LENGTHS[-1])))   # пикселей при самом большом n
    per_pixel = row[-1] * 1000 / pixels
    print(f"{name:24}" + "".join(f"{t:10.1f} мкс" for t in row) + f"{pixels:10}{per_pixel:12.0f}")
print(f"\nдля окружности n - это радиус. пиксели и нс/пиксель - при n = {LENGTHS[-1]}")
