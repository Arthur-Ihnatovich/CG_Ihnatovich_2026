import tkinter as tk
from tkinter import colorchooser


def rgb_to_cmyk(r, g, b):
    k = 1 - max(r, g, b)
    if k == 1:
        return 0, 0, 0, 1
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)
    return c, m, y, k


def cmyk_to_rgb(c, m, y, k):
    r = (1 - c) * (1 - k)
    g = (1 - m) * (1 - k)
    b = (1 - y) * (1 - k)
    return r, g, b


def rgb_to_hls(r, g, b):
    """
    Переводит RGB (0-1) в HLS:

    H в градусах (0-360), L и S в диапазоне 0-1.

    H (Hue, оттенок) - угол на цветовом круге: 0 красный, 120 зелёный, 240 синий.
    L (Lightness, светлота) - середина между самым тёмным и самым светлым каналом: 0 - чёрный, 1 - белый, 0.5 - самый "чистый" цвет.
    S (Saturation, насыщенность) - насколько цвет далёк от серого.
    """

    mx = max(r, g, b)
    mn = min(r, g, b)
    delta = mx - mn  # разброс между каналами; если 0, то цвет серый

    l = (mx + mn) / 2

    # Насыщенность (у серого цвета она равна 0)
    if delta == 0:
        s = 0
    else:
        s = delta / (1 - abs(2 * l - 1))

    # Оттенок: зависит от того, какой канал самый большой
    if delta == 0:
        h = 0  # у серого оттенка нет, по договорённости берём 0
    elif mx == r:
        h = 60 * (((g - b) / delta) % 6)
    elif mx == g:
        h = 60 * ((b - r) / delta + 2)
    else:
        h = 60 * ((r - g) / delta + 4)

    return h, l, s


def hls_to_rgb(h, l, s):
    """
    Переводит HLS (H в градусах, L и S в 0-1) в RGB (0..1).

    Сначала считаем три вспомогательные величины: c, x, m.

    Потом по сектору оттенка (каждые 60 градусов) раскладываем c, x и 0 по каналам R, G, B и прибавляем m.
    """

    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2

    h = h % 360  # угол 360 это то же самое, что 0
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    return r + m, g + m, b + m


def clamp(value, low, high):
    """Ограничивает число диапазоном [low, high]."""
    return max(low, min(high, value))


class ColorApp:
    def __init__(self, window):
        """Создаёт окно, все элементы интерфейса и показывает начальный цвет."""
        self.window = window
        self.window.title("Конвертер цветовых моделей CMYK, RGB, HLS")
        self.window.resizable(False, False)

        # Флаг защиты от зацикливания: когда программа сама двигает ползунки, сами ползунки вызывают обработчики.
        # Пока флаг True, обработчики молчат.
        self.updating = False

        self.r, self.g, self.b = 255, 0, 0
        self.c_val, self.m_val, self.y_val, self.k_val = 0.0, 100.0, 100.0, 0.0

        self.color_box = tk.Label(window, text="", font=("Verdana", 14, "bold"), width=40, height=3)
        self.color_box.pack(pady=(35, 6))

        btn_palette = tk.Button(window, text="Выбрать цвет из палитры", command=self.pick_color, font=("Verdana", 10))
        btn_palette.pack(pady=(0, 15))

        frames_container = tk.Frame(window)
        frames_container.pack(pady=(0, 0), fill="x", padx=20)

        # В каждом списке лежат кортежи (ползунок, поле ввода, максимум)
        self.cmyk_widgets = []
        self.rgb_widgets = []
        self.hls_widgets = []

        self.create_cmyk_frame(frames_container)
        self.create_rgb_frame(frames_container)
        self.create_hls_frame(frames_container)

        hint = tk.Label(window, text="Чтобы применить число из поля ввода, нажмите Enter", font=("Verdana", 10), fg="gray")
        hint.pack(pady=(0, 35))

        self.update_all()


    def create_cmyk_frame(self, parent):
        """Создаёт панель модели CMYK: 4 ползунка и 4 поля ввода. Шкала проценты 0-100%."""

        frame = tk.LabelFrame(parent, text="Модель CMYK", font=("Verdana", 10, "bold"), padx=10)
        frame.pack(side="left", expand=True, fill="both", padx=5)

        for i, name in enumerate(("C", "M", "Y", "K")):
            widgets = self.add_slider_and_entry(frame, name + " (0-100%):", 100, 0.1, "cmyk", i)
            self.cmyk_widgets.append(widgets)

    def create_rgb_frame(self, parent):
        """Создаёт панель модели RGB: 3 ползунка и 3 поля ввода. Шкала целые числа 0-255."""
        frame = tk.LabelFrame(parent, text="Модель RGB", font=("Verdana", 10, "bold"), padx=10, pady=10)
        frame.pack(side="left", expand=True, fill="both", padx=5)

        for i, name in enumerate(("R", "G", "B")):
            widgets = self.add_slider_and_entry(frame, name + " (0-255):", 255, 1, "rgb", i)
            self.rgb_widgets.append(widgets)

    def create_hls_frame(self, parent):
        """Создаёт панель модели HLS (Hue, Lightness, Saturation)."""
        frame = tk.LabelFrame(parent, text="Модель HLS", font=("Verdana", 10, "bold"), padx=10, pady=10)
        frame.pack(side="left", expand=True, fill="both", padx=5)

        hls_data = [
            ("H (0-360°):", 360),
            ("L (0-100%):", 100),
            ("S (0-100%):", 100)
        ]

        for i, (label_text, max_val) in enumerate(hls_data):
            widgets = self.add_slider_and_entry(frame, label_text, max_val, 0.1, "hls", i)
            self.hls_widgets.append(widgets)

    def add_slider_and_entry(self, parent, label_text, max_val, step, model, row_index):
        """
        Создаёт подпись, ползунок и поле ввода.

        model - название модели ("cmyk", "rgb" или "hls").
        Двигаем ползунок -> вызывается on_change(model, "scale").
        Нажимаем Enter в поле -> вызывается on_change(model, "entry").
        Возвращает кортеж (ползунок, поле ввода, максимум).
        """

        # 1. Текст-подпись (колонка 0)
        lbl = tk.Label(parent, text=label_text, font=("Verdana", 10))
        lbl.grid(row=row_index, column=0, sticky="w", padx=0, pady=5)

        # 2. Ползунок (колонка 1)
        scale = tk.Scale(parent, # родительский контейнер
                         from_=0, # минимальное значение ползунка
                         to=max_val, # максимальное значение ползунка
                         resolution=step, # шаг, с которым двигается ползунок
                         orient="horizontal", # ориентация ползунка
                         length=150, # длина ползунка в пикселях
                         showvalue=0, # отключает цифры над ползунком
                         command=lambda value: self.on_change(model, "scale")) # при движении ползунка автоматически запускается функция self.on_change
        scale.grid(row=row_index, column=1, padx=0, pady=5)

        # 3. Поле ввода (колонка 2)
        entry = tk.Entry(parent, width=10, font=("Verdana", 10))
        entry.grid(row=row_index, column=2, padx=(3, 0), pady=5)
        entry.bind("<Return>", lambda event: self.on_change(model, "entry"))

        return scale, entry, max_val

    # ОБРАБОТКА ДЕЙСТВИЙ ПОЛЬЗОВАТЕЛЯ

    def pick_color(self):
        """Открывает стандартную палитру. Если цвет выбран, сохраняет его как текущий и обновляет все модели."""
        result = colorchooser.askcolor(title="Выберите цвет")
        if result[0] is not None:  # None означает, что нажали "Отмена"
            self.r, self.g, self.b = result[0]

            c, m, y, k = rgb_to_cmyk(self.r/255, self.g/255, self.b/255)
            self.c_val, self.m_val, self.y_val, self.k_val = c * 100, m * 100, y * 100, k * 100

            self.update_all()

    def read_widgets(self, widgets, source):
        """Читает значения компонент одной модели и возвращает их списком чисел.

        source = "scale": значения берутся с ползунков;
        source = "entry": значения берутся из полей ввода (запятая тоже допустима).

        Каждое значение ограничивается диапазоном от 0 до максимума.
        Если в поле ввели не число, будет ошибка ValueError."""

        values = []
        for scale, entry, max_val in widgets:
            if source == "scale":
                value = float(scale.get())
            else:
                value = float(entry.get().replace(",", "."))
            values.append(clamp(value, 0, max_val))
        return values

    def on_change(self, model, source):
        """Общий обработчик: пользователь изменил компоненты модели model
        (ползунком или полем ввода, это определяет source).

        Шаги:
        1) прочитать значения;
        2) перевести в RGB и запомнить;
        3) пересчитать и показать все модели.
        """

        if self.updating:
            return

        try:
            if model == "rgb":
                self.r, self.g, self.b = self.read_widgets(self.rgb_widgets, source)
                # Пересчитываем CMYK под новый RGB
                c, m, y, k = rgb_to_cmyk(self.r/255, self.g/255, self.b/255)
                self.c_val, self.m_val, self.y_val, self.k_val = c * 100, m * 100, y * 100, k * 100

            elif model == "cmyk":
                # Читаем и сохраняем значения из полей CMYK
                self.c_val, self.m_val, self.y_val, self.k_val = self.read_widgets(self.cmyk_widgets, source)
                # Переводим CMYK в RGB
                r, g, b = cmyk_to_rgb(self.c_val/100, self.m_val/100, self.y_val/100, self.k_val/100)
                self.r, self.g, self.b = r * 255, g * 255, b * 255

            elif model == "hls":
                h, l, s = self.read_widgets(self.hls_widgets, source)
                r, g, b = hls_to_rgb(h, l / 100, s / 100)
                self.r, self.g, self.b = r * 255, g * 255, b * 255
                c, m, y, k = rgb_to_cmyk(self.r/255, self.g/255, self.b/255)
                self.c_val, self.m_val, self.y_val, self.k_val = c * 100, m * 100, y * 100, k * 100

        except ValueError:
            self.update_all()
            return

        self.update_all(source_model=model, source_kind=source)


    def update_all(self, source_model=None, source_kind=None):
        """Берёт текущий RGB, считает из него CMYK и HLS и показывает ВСЕ модели.

        source_model указывает, в какой именно панели произошло изменение ("rgb", "cmyk", "hls" (или быть None, если цвет изменился через палитру)).
        source_kind указывает, какой именно элемент управления тронул пользователь ("scale", "entry").

        Если указаны source_model и source_kind, то тот элемент, которым пользователь
        сейчас управляет (ползунок или поле), не перезаписывается: иначе из-за округлений
        он "прыгал" бы прямо под рукой."""

        self.updating = True

        # RGB в диапазоне 0-1 для формул
        r = clamp(self.r, 0, 255) / 255
        g = clamp(self.g, 0, 255) / 255
        b = clamp(self.b, 0, 255) / 255

        # Считаем значения для показа (в "экранных" единицах)
        rgb_values = [r * 255, g * 255, b * 255]

        # Используем сохраненные значения CMYK напрямую
        cmyk_values = [self.c_val, self.m_val, self.y_val, self.k_val]
        
        h, l, s = rgb_to_hls(r, g, b)
        hls_values = [h, l * 100, s * 100]

        skip_cmyk = source_kind if source_model == "cmyk" else None
        skip_rgb = source_kind if source_model == "rgb" else None
        skip_hls = source_kind if source_model == "hls" else None

        self.show_values(self.cmyk_widgets, cmyk_values, 1, skip_cmyk)
        self.show_values(self.rgb_widgets, rgb_values, 0, skip_rgb)
        self.show_values(self.hls_widgets, hls_values, 1, skip_hls)

        self.update_color_box(rgb_values)

        # Флаг снимаем не сразу, а когда tkinter доделает перерисовку ползунков.
        # Тогда "запоздавшие" вызовы command от ползунков будут проигнорированы.
        self.window.after_idle(self.finish_update)

    def finish_update(self):
        """Разрешает обработчикам снова реагировать на действия пользователя."""
        self.updating = False

    def show_values(self, widgets, values, decimals, skip):
        """
        Записывает значения values в ползунки и поля ввода одной модели.

        decimals - сколько знаков после запятой показывать в полях.

        skip = "scale" или "entry": этот вид элементов не обновляем; None: обновляем всё.
        """

        for (scale, entry, max_val), value in zip(widgets, values):
            if skip != "scale":
                scale.set(value)
            if skip != "entry":
                entry.delete(0, tk.END)
                entry.insert(0, f"{value:.{decimals}f}")

    def update_color_box(self, rgb_values):
        """Закрашивает прямоугольник-образец текущим цветом и пишет в нём HEX-код.
        Цвет текста выбирается чёрным или белым, чтобы он был читаем на любом фоне."""

        r, g, b = [round(v) for v in rgb_values]
        hex_color = f"#{r:02x}{g:02x}{b:02x}"

        brightness = 0.299 * r + 0.587 * g + 0.114 * b
        text_color = "black" if brightness > 140 else "white"

        self.color_box.config(bg=hex_color, fg=text_color, text=f"HEX: {hex_color.upper()}")


if __name__ == "__main__":
    window = tk.Tk()
    app = ColorApp(window)
    window.mainloop()
