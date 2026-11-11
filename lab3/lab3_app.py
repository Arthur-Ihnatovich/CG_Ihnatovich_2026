"""Лабораторная 3. Базовые растровые алгоритмы - окно программы.

Запуск: python lab3_app.py (нужен только Python, без библиотек).
Пиксель (x, y) - клетка с центром в точке (x, y), т.е. квадрат [x-0.5, x+0.5] x [y-0.5, y+0.5].
Поэтому линии сетки идут по полуцелым координатам, а оси и подписи - по целым.
"""
import ctypes
import time
import tkinter as tk
from tkinter import ttk, messagebox

import raster

FONT = ("Segoe UI", 10)
BOLD = ("Segoe UI", 10, "bold")
MONO = ("Consolas", 10)

# название в списке -> (функция, окружность или нет, цвет)
ALGORITHMS = {
    "Пошаговый": (raster.step_by_step, False, "#e8a33d"),
    "ЦДА": (raster.dda, False, "#4caf50"),
    "Брезенхем (отрезок)": (raster.bresenham_line, False, "#3f7fd9"),
    "Брезенхем (окружность)": (raster.bresenham_circle, True, "#c0504d"),
}


def measure_time(function, args):
    """Среднее время одного вызова в мкс. Вызываем функцию, пока не наберется 0.2 с."""
    repeats = 0
    start = time.perf_counter()
    while True:
        function(*args)
        repeats += 1
        elapsed = time.perf_counter() - start
        if elapsed >= 0.2:
            return elapsed / repeats * 1e6, repeats


class RasterApp:
    def __init__(self, window):
        self.window = window
        self.window.title("Лабораторная работа 3: базовые растровые алгоритмы")
        self.window.option_add("*Font", FONT)

        self.scale = 24              # сколько точек экрана в одной клетке
        self.origin = None           # где на экране точка (0, 0), задается при первой отрисовке
        self.figures = []            # построенные фигуры: (пиксели, цвет, идеальная фигура)
        self.drag_start = None

        # левая панель
        panel = tk.Frame(window, padx=10, pady=10)
        panel.pack(side="left", fill="y")

        tk.Label(panel, text="Алгоритм:", font=BOLD).pack(anchor="w")
        self.algorithm = ttk.Combobox(panel, state="readonly", width=26, values=list(ALGORITHMS))
        self.algorithm.current(2)
        self.algorithm.pack(anchor="w", pady=(2, 8))
        self.algorithm.bind("<<ComboboxSelected>>", lambda event: self.update_labels())

        fields = tk.Frame(panel)
        fields.pack(anchor="w")
        self.entries, self.entry_labels = {}, {}
        for row, (name, value) in enumerate([("x1", "-8"), ("y1", "-3"), ("x2", "9"), ("y2", "4"), ("R", "8")]):
            label = tk.Label(fields, text=name + ":")
            label.grid(row=row, column=0, sticky="w")
            entry = tk.Entry(fields, width=8)
            entry.insert(0, value)
            entry.grid(row=row, column=1, pady=2, padx=5)
            entry.bind("<Return>", lambda event: self.build())
            self.entries[name], self.entry_labels[name] = entry, label

        buttons = tk.Frame(panel)
        buttons.pack(anchor="w", pady=8, fill="x")
        tk.Button(buttons, text="Построить", font=BOLD, command=self.build).pack(fill="x")
        tk.Button(buttons, text="Очистить", command=self.clear).pack(fill="x", pady=3)
        tk.Button(buttons, text="Время всех алгоритмов", command=self.compare_times).pack(fill="x")

        self.show_ideal = tk.BooleanVar(value=True)
        tk.Checkbutton(panel, text="Показывать идеальную линию", variable=self.show_ideal,
                       command=self.redraw).pack(anchor="w")

        zoom = tk.Frame(panel)
        zoom.pack(anchor="w", pady=8)
        tk.Label(zoom, text="Масштаб:").pack(side="left")
        tk.Button(zoom, text=" − ", command=lambda: self.zoom(1 / 1.25)).pack(side="left", padx=3)
        tk.Button(zoom, text=" + ", command=lambda: self.zoom(1.25)).pack(side="left")
        tk.Button(zoom, text="В центр", command=self.reset_view).pack(side="left", padx=3)

        tk.Label(panel, justify="left", fg="#555555", wraplength=330, text=(
            "Пиксель (x, y) - клетка с центром в точке (x, y), т.е. квадрат "
            "[x-0.5, x+0.5] x [y-0.5, y+0.5]. Линии сетки идут по полуцелым координатам. "
            "Колесо мыши - масштаб (вокруг курсора), перетаскивание - сдвиг.")).pack(anchor="w")

        tk.Label(panel, text="Вычисления (первые шаги):", font=BOLD).pack(anchor="w", pady=(10, 2))
        self.log = tk.Text(panel, width=48, height=22, font=MONO, wrap="word")
        self.log.pack(fill="both", expand=True)

        # холст
        self.canvas = tk.Canvas(window, bg="white", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda event: self.redraw())
        self.canvas.bind("<MouseWheel>", lambda event: self.zoom(1.25 if event.delta > 0 else 1 / 1.25,
                                                                  (event.x, event.y)))
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<Motion>", self.show_cursor)

        self.update_labels()
        try:
            window.state("zoomed")
        except tk.TclError:
            window.geometry("1400x900")

    # перевод координат
    def to_screen(self, x, y):
        """Координаты сетки -> точка на холсте. На экране y идет вниз, поэтому минус."""
        ox, oy = self.origin
        return ox + x * self.scale, oy - y * self.scale

    def to_grid(self, sx, sy):
        """Точка на холсте -> пиксель сетки."""
        ox, oy = self.origin
        return round((sx - ox) / self.scale), round((oy - sy) / self.scale)

    # рисование
    def redraw(self):
        """Рисует все заново: сетку, пиксели, оси с подписями и идеальные фигуры."""
        c = self.canvas
        c.delete("all")
        width, height = c.winfo_width(), c.winfo_height()
        if self.origin is None:
            self.origin = (width // 2, height // 2)
        # какие координаты сейчас видны
        x_min, y_max = self.to_grid(0, 0)
        x_max, y_min = self.to_grid(width, height)

        # 1) сетка: границы клеток на полуцелых координатах
        if self.scale >= 6:
            for x in range(x_min - 1, x_max + 2):
                sx, _ = self.to_screen(x + 0.5, 0)
                c.create_line(sx, 0, sx, height, fill="#e2e2e2")
            for y in range(y_min - 1, y_max + 2):
                _, sy = self.to_screen(0, y + 0.5)
                c.create_line(0, sy, width, sy, fill="#e2e2e2")

        # 2) пиксели фигур
        for pixels, color, _ in self.figures:
            for x, y in pixels:
                x0, y0 = self.to_screen(x - 0.5, y + 0.5)
                x1, y1 = self.to_screen(x + 0.5, y - 0.5)
                c.create_rectangle(x0, y0, x1, y1, fill=color, outline="#999999" if self.scale >= 6 else "")

        # 3) оси через x = 0 и y = 0, засечки и подписи
        ox, oy = self.origin
        c.create_line(0, oy, width - 2, oy, arrow="last", width=1.5)
        c.create_line(ox, height, ox, 2, arrow="last", width=1.5)
        c.create_text(width - 12, oy - 12, text="x", font=BOLD)
        c.create_text(ox + 12, 12, text="y", font=BOLD)
        step = self.label_step()
        for x in range(x_min - x_min % step, x_max + 1, step):
            if x != 0:
                sx, _ = self.to_screen(x, 0)
                c.create_line(sx, oy - 4, sx, oy + 4, width=1.5)
                c.create_text(sx, oy + 14, text=str(x), fill="#333333")
        for y in range(y_min - y_min % step, y_max + 1, step):
            if y != 0:
                _, sy = self.to_screen(0, y)
                c.create_line(ox - 4, sy, ox + 4, sy, width=1.5)
                c.create_text(ox - 8, sy, text=str(y), anchor="e", fill="#333333")
        c.create_text(ox - 8, oy + 14, text="0", anchor="e", fill="#333333")

        # 4) идеальные фигуры красным поверх пикселей
        if self.show_ideal.get():
            for _, _, ideal in self.figures:
                if ideal[0] == "line":
                    c.create_line(*self.to_screen(*ideal[1:3]), *self.to_screen(*ideal[3:5]), fill="red", width=2)
                else:
                    _, xc, yc, r = ideal
                    c.create_oval(*self.to_screen(xc - r, yc + r), *self.to_screen(xc + r, yc - r),
                                  outline="red", width=2)

        c.create_text(10, height - 10, anchor="sw", fill="#555555",
                      text=f"Масштаб: {self.scale:.0f} px на клетку")
        self.cursor_text = c.create_text(width - 10, height - 10, anchor="se", fill="#555555", text="")

    def label_step(self):
        """Шаг подписей на осях, чтобы подписи были не ближе 40 точек друг к другу."""
        for step in (1, 2, 5, 10, 20, 50, 100, 200, 500):
            if step * self.scale >= 40:
                return step
        return 1000

    # масштаб и сдвиг
    def zoom(self, factor, center=None):
        """Меняет масштаб, точка center (курсор) остается на месте. Без center - середина холста."""
        new_scale = min(80, max(2, self.scale * factor))
        if center is None:
            center = (self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2)
        if self.origin is not None:
            # сдвигаем начало координат, чтобы точка под курсором не уехала
            ratio = new_scale / self.scale
            cx, cy = center
            ox, oy = self.origin
            self.origin = (cx - (cx - ox) * ratio, cy - (cy - oy) * ratio)
        self.scale = new_scale
        self.redraw()

    def reset_view(self):
        self.scale = 24
        self.origin = None
        self.redraw()

    def start_drag(self, event):
        self.drag_start = (event.x, event.y)

    def drag(self, event):
        dx, dy = event.x - self.drag_start[0], event.y - self.drag_start[1]
        self.origin = (self.origin[0] + dx, self.origin[1] + dy)
        self.drag_start = (event.x, event.y)
        self.redraw()

    def show_cursor(self, event):
        if self.origin is not None:
            x, y = self.to_grid(event.x, event.y)
            self.canvas.itemconfig(self.cursor_text, text=f"Пиксель под курсором: ({x}, {y})")

    # построение
    def update_labels(self):
        """Для окружности x1, y1 - это центр, а x2, y2 не нужны."""
        is_circle = ALGORITHMS[self.algorithm.get()][1]
        self.entry_labels["x1"].config(text="xc:" if is_circle else "x1:")
        self.entry_labels["y1"].config(text="yc:" if is_circle else "y1:")
        for name in ("x2", "y2"):
            self.entries[name].config(state="disabled" if is_circle else "normal")
        self.entries["R"].config(state="normal" if is_circle else "disabled")

    def read_numbers(self):
        try:
            return {name: int(entry.get()) for name, entry in self.entries.items()}
        except ValueError:
            messagebox.showerror("Ошибка", "Координаты и радиус должны быть целыми числами.")
            return None

    def build(self):
        values = self.read_numbers()
        if values is None:
            return
        name = self.algorithm.get()
        function, is_circle, color = ALGORITHMS[name]
        if is_circle:
            if values["R"] < 0:
                messagebox.showerror("Ошибка", "Радиус не может быть отрицательным.")
                return
            args = (values["x1"], values["y1"], values["R"])
            ideal = ("circle", *args)
        else:
            args = (values["x1"], values["y1"], values["x2"], values["y2"])
            ideal = ("line", *args)

        log = []
        pixels = function(*args, log)
        microseconds, repeats = measure_time(function, args)
        self.figures.append((pixels, color, ideal))
        self.redraw()

        self.log.delete("1.0", "end")
        self.log.insert("end", f"{name}: {args}\n")
        self.log.insert("end", "\n".join(log[:60]))
        if len(log) > 60:
            self.log.insert("end", f"\n... еще {len(log) - 60} строк")
        self.log.insert("end", f"\n\nпикселей: {len(pixels)}\n"
                               f"время: {microseconds:.2f} мкс (запусков: {repeats})")

    def clear(self):
        self.figures = []
        self.log.delete("1.0", "end")
        self.redraw()

    def compare_times(self):
        """Время всех алгоритмов на текущих координатах (окружность - с текущим R)."""
        values = self.read_numbers()
        if values is None:
            return
        line = (values["x1"], values["y1"], values["x2"], values["y2"])
        self.log.delete("1.0", "end")
        self.log.insert("end", f"отрезок {line}, окружность R = {values['R']}\n\n")
        for name, (function, is_circle, _) in ALGORITHMS.items():
            args = (values["x1"], values["y1"], abs(values["R"])) if is_circle else line
            microseconds, _ = measure_time(function, args)
            self.log.insert("end", f"{name:24} {microseconds:9.2f} мкс\n")
            self.window.update_idletasks()


if __name__ == "__main__":
    # иначе при масштабе экрана 125-150 % окно будет размытым
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    window = tk.Tk()
    app = RasterApp(window)
    window.mainloop()
