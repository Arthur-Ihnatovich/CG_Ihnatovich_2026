import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
from PIL import Image, ImageTk

def make_square_offsets(size):
    """Возвращает список смещений (dy, dx) для квадратного окна size x size.
    Например, для size = 3 это 9 смещений от (-1, -1) до (1, 1);
    смещение (0, 0) - сам пиксель."""
    r = size // 2
    offsets = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            offsets.append((dy, dx))
    return offsets


def make_structuring_element(shape, size):
    """Возвращает список смещений (dy, dx) для структурного элемента морфологии.
    Структурный элемент - это маленькая "форма", которой мы проходим по картинке.
    shape: "Квадрат", "Крест" или "Круг"; size: нечётный размер (3, 5, 7 ...)."""
    r = size // 2
    offsets = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if shape == "Квадрат":
                offsets.append((dy, dx))
            elif shape == "Крест":
                if dy == 0 or dx == 0:
                    offsets.append((dy, dx))
            elif shape == "Круг":
                if dy * dy + dx * dx <= r * r:
                    offsets.append((dy, dx))
    return offsets


def get_neighbors(channel, offsets):
    """Для каждого пикселя собирает значения его соседей.

    channel - серое изображение (2D массив);
    offsets - список смещений (dy, dx), определяющий, кто считается соседом.

    Возвращает 3D массив "число соседей x высота x ширина": слой номер k - это
    картинка, сдвинутая на k-е смещение. Поэтому neighbors[:, y, x] - это все
    значения соседей пикселя (y, x).
    На краях картинки недостающие пиксели повторяют крайние (mode="edge")."""
    height, width = channel.shape
    pad = max(max(abs(dy), abs(dx)) for dy, dx in offsets)  # на сколько расширить картинку
    padded = np.pad(channel, pad, mode="edge")

    layers = []
    for dy, dx in offsets:
        layer = padded[pad + dy: pad + dy + height, pad + dx: pad + dx + width]
        layers.append(layer)
    return np.stack(layers)


def order_filter(channel, method, size):
    """Фильтр на порядковых статистиках для одного канала (серого изображения).
    Значения соседей в окне size x size упорядочиваются по возрастанию, и из них
    выбирается одно число:
      "Медиана" - среднее по порядку (убирает точечный шум "соль и перец");
      "Минимум" - самое тёмное (убирает белые точки, "съедает" светлое);
      "Максимум" - самое светлое (убирает чёрные точки, "съедает" тёмное);
      "Середина диапазона" - (минимум + максимум) / 2 (хорошо для гауссова шума)."""
    neighbors = get_neighbors(channel, make_square_offsets(size))

    if method == "Медиана":
        result = np.median(neighbors, axis=0)
    elif method == "Минимум":
        result = neighbors.min(axis=0)
    elif method == "Максимум":
        result = neighbors.max(axis=0)
    else:  # "Середина диапазона"
        result = (neighbors.min(axis=0).astype(np.int32) + neighbors.max(axis=0)) / 2

    return np.round(result).astype(np.uint8)


def apply_to_image(image_array, function):
    """Применяет функцию function к изображению.
    Серое изображение обрабатывается целиком, а цветное - по каждому каналу
    (R, G, B) отдельно, после чего каналы собираются обратно."""
    if image_array.ndim == 2: # возвращает количество измерений массива
        return function(image_array)
    channels = []
    for i in range(image_array.shape[2]):
        channels.append(function(image_array[:, :, i]))
    return np.stack(channels, axis=2)


def binarize(gray, threshold, invert):
    """Делает изображение чёрно-белым: пиксели ярче порога становятся белыми (255),
    остальные - чёрными (0). Если invert = True, наоборот: тёмные пиксели
    становятся белыми (удобно, когда объекты тёмные на светлом фоне)."""
    if invert:
        mask = gray < threshold
    else:
        mask = gray >= threshold
    return np.where(mask, 255, 0).astype(np.uint8)


def erode(channel, offsets):
    """Эрозия: каждый пиксель заменяется МИНИМУМОМ среди соседей по структурному
    элементу. Белые объекты "худеют", мелкие белые точки исчезают."""
    return get_neighbors(channel, offsets).min(axis=0)


def dilate(channel, offsets):
    """Дилатация: каждый пиксель заменяется МАКСИМУМОМ среди соседей по структурному
    элементу. Белые объекты "толстеют", мелкие дырки и разрывы зарастают."""
    return get_neighbors(channel, offsets).max(axis=0)


def morphology(channel, operation, offsets):
    """Морфологическая операция над серым или чёрно-белым изображением:
      "Эрозия" - erode;
      "Дилатация" - dilate;
      "Открытие" - эрозия, затем дилатация: убирает мелкие белые точки и тонкие
                           перемычки, почти не меняя размер крупных объектов;
      "Закрытие" - дилатация, затем эрозия: заполняет мелкие чёрные дырки и
                           соединяет близкие части объекта;
      "Выделение границ" - дилатация минус эрозия: остаётся только контур объектов."""
    if operation == "Эрозия":
        return erode(channel, offsets)
    if operation == "Дилатация":
        return dilate(channel, offsets)
    if operation == "Открытие":
        return dilate(erode(channel, offsets), offsets)
    if operation == "Закрытие":
        return erode(dilate(channel, offsets), offsets)
    # "Выделение границ"
    difference = dilate(channel, offsets).astype(np.int16) - erode(channel, offsets).astype(np.int16)
    return np.clip(difference, 0, 255).astype(np.uint8)


class ImageApp:
    MAX_SIDE = 600 # максимальная сторона изображения после загрузки

    def __init__(self, window):
        """Создаёт фиксированное окно приложения и размещает элементы интерфейса."""
        self.window = window
        self.window.title("Обработка изображений: порядковые статистики и морфология")
        self.window.geometry("1370x1050")
        self.window.resizable(False, False)

        self.original = None # загруженное изображение
        self.result = None # результат обработки

        method_frame = tk.LabelFrame(window, text="Метод обработки", font=("Verdana", 10, "bold"), padx=10, pady=5)
        method_frame.pack(fill="x", padx=10, pady=(10, 5))

        self.mode = tk.StringVar(value="filter")
        tk.Radiobutton(method_frame, text="Нелинейные фильтры (порядковые статистики)",
                       variable=self.mode, value="filter", command=self.switch_mode,
                       font=("Verdana", 10)).pack(side="left")
        tk.Radiobutton(method_frame, text="Морфологическая обработка",
                       variable=self.mode, value="morph", command=self.switch_mode,
                       font=("Verdana", 10)).pack(side="left", padx=20)

        params_frame = tk.LabelFrame(window, text="Параметры", font=("Verdana", 10, "bold"), padx=10, pady=5)
        params_frame.pack(fill="x", padx=10, pady=5)

        self.create_filter_panel(params_frame)
        self.create_morph_panel(params_frame)
        self.switch_mode()

        # --- Кнопка запуска обработки ---
        run_frame = tk.Frame(window)
        run_frame.pack(fill="x", padx=10, pady=5)
        tk.Button(run_frame,
                  text="Применить",
                  command=self.apply,
                  font=("Verdana", 11, "bold"),
                  width=15).pack()

        # --- Строка состояния и подсказка по центру над изображениями ---
        self.status = tk.Label(window, text="Откройте изображение кнопкой под левым окном",
                               font=("Verdana", 10), fg="gray", anchor="center")
        self.status.pack(fill="x", padx=10, pady=(5, 0))
        self.hint = tk.Label(window, text="Слева отображается исходное изображение, справа — результат обработки",
                             font=("Verdana", 9), fg="gray", anchor="center")
        self.hint.pack(fill="x", padx=10, pady=(0, 5))

        # --- Две фиксированные области для изображений: исходное слева, результат справа ---
        images = tk.Frame(window)
        images.pack(padx=10, pady=(5, 5))
        images.grid_columnconfigure(0, minsize=self.MAX_SIDE)
        images.grid_columnconfigure(1, minsize=50)
        images.grid_columnconfigure(2, minsize=self.MAX_SIDE)

        self.left_caption = tk.Label(images, text="Исходное изображение", font=("Verdana", 10, "bold"))
        self.left_caption.grid(row=0, column=0, pady=(0, 5))
        tk.Label(images, text="Результат", font=("Verdana", 10, "bold")).grid(row=0, column=2, pady=(0, 5))

        # Фиксированные рамки 600 x 600 не меняют размер при загрузке разных картинок.
        self.left_box = tk.Frame(images, width=self.MAX_SIDE, height=self.MAX_SIDE, relief="sunken", bd=1)
        self.left_box.grid(row=1, column=0, padx=5, pady=5)
        self.left_box.pack_propagate(False)
        self.left_label = tk.Label(self.left_box, text="(нет изображения)", anchor="center")
        self.left_label.pack(expand=True)

        # Маленькая кнопка между изображениями переносит результат в исходное.
        tk.Button(images, text="←", command=self.use_result_as_input,
                  font=("Verdana", 9, "bold"), width=5).grid(row=1, column=1, padx=2)

        self.right_box = tk.Frame(images, width=self.MAX_SIDE, height=self.MAX_SIDE, relief="sunken", bd=1)
        self.right_box.grid(row=1, column=2, padx=5, pady=5)
        self.right_box.pack_propagate(False)
        self.right_label = tk.Label(self.right_box, text="(нет результата)", anchor="center")
        self.right_label.pack(expand=True)

        # Кнопки находятся непосредственно под соответствующими изображениями.
        tk.Button(images, text="Загрузить изображение...", command=self.open_image,
                  font=("Verdana", 10)).grid(row=2, column=0, pady=(5, 0))
        tk.Button(images, text="Сохранить результат...", command=self.save_result,
                  font=("Verdana", 10)).grid(row=2, column=2, pady=(5, 0))



    def create_filter_panel(self, parent):
        """Создаёт панель параметров нелинейных фильтров: метод и размер окна."""
        self.filter_panel = tk.Frame(parent)
        self.filter_panel.grid(row=0, column=0, sticky="w")

        tk.Label(self.filter_panel, text="Фильтр:", font=("Verdana", 10)).grid(row=0, column=0, sticky="w")

        self.filter_method = ttk.Combobox(self.filter_panel,
                                          state="readonly",
                                          width=20,
                                          values=["Медиана", "Минимум", "Максимум", "Середина диапазона"])
        self.filter_method.current(0)
        self.filter_method.grid(row=0, column=1, padx=10, pady=3)

        tk.Label(self.filter_panel, text="Размер окна:", font=("Verdana", 10)).grid(row=1, column=0, sticky="w")

        self.filter_size = ttk.Combobox(self.filter_panel,
                                        state="readonly",
                                        width=5,
                                        values=["3", "5", "7", "9"])
        self.filter_size.current(0)
        self.filter_size.grid(row=1, column=1, padx=10, pady=3, sticky="w")

    def create_morph_panel(self, parent):
        """Создаёт панель параметров морфологии: операция, структурный элемент, бинаризация (порог и инверсия)."""
        self.morph_panel = tk.Frame(parent)
        self.morph_panel.grid(row=0, column=0, sticky="w")

        tk.Label(self.morph_panel, text="Операция:", font=("Verdana", 10)).grid(row=0, column=0, sticky="w")

        self.morph_operation = ttk.Combobox(self.morph_panel,
                                            state="readonly",
                                            width=20,
                                            values=["Эрозия", "Дилатация", "Открытие", "Закрытие", "Выделение границ"])
        self.morph_operation.current(0)
        self.morph_operation.grid(row=0, column=1, padx=10, pady=3)

        tk.Label(self.morph_panel, text="Структурный элемент:", font=("Verdana", 10)).grid(row=1, column=0, sticky="w")

        self.morph_shape = ttk.Combobox(self.morph_panel,
                                        state="readonly",
                                        width=20,
                                        values=["Квадрат", "Крест", "Круг"])
        self.morph_shape.current(0)
        self.morph_shape.grid(row=1, column=1, padx=10, pady=3)

        tk.Label(self.morph_panel, text="Размер элемента:", font=("Verdana", 10)).grid(row=2, column=0, sticky="w")

        self.morph_size = ttk.Combobox(self.morph_panel,
                                       state="readonly",
                                       width=5,
                                       values=["3", "5", "7", "9"])
        self.morph_size.current(0)
        self.morph_size.grid(row=2, column=1, padx=10, pady=3, sticky="w")

        self.binarize_var = tk.BooleanVar(value=True)

        self.binarize_check = tk.Checkbutton(
            self.morph_panel,
            text="Сначала сделать чёрно-белым (бинаризация)",
            variable=self.binarize_var,
            command=self.update_invert_state,
            font=("Verdana", 10)
        )
        self.binarize_check.grid(row=0, column=2, padx=20, sticky="w")

        threshold_row = tk.Frame(self.morph_panel)
        threshold_row.grid(row=1, column=2, padx=20, sticky="w")

        # Число порога хранится в этой переменной: ползунок записывает в неё значение, а окошко справа его показывает
        self.threshold_var = tk.IntVar(value=128)

        tk.Label(threshold_row, text="Порог:", font=("Verdana", 10)).pack(side="left")

        self.threshold = tk.Scale(threshold_row,
                                  from_=0,
                                  to=255,
                                  orient="horizontal",
                                  length=150,
                                  showvalue=0, # убирает цифру над ползунком
                                  variable=self.threshold_var)
        self.threshold.pack(side="left", padx=5)

        # Отдельное окошко справа от ползунка с текущим значением
        tk.Label(threshold_row,
                 textvariable=self.threshold_var,
                 width=4,
                 relief="sunken",
                 bg="white",
                 font=("Verdana", 10)).pack(side="left")

        self.invert_var = tk.BooleanVar(value=False)

        self.invert_check = tk.Checkbutton(
            self.morph_panel,
            text="Инвертировать",
            variable=self.invert_var,
            font=("Verdana", 10)
        )
        self.invert_check.grid(row=2, column=2, padx=20, sticky="w")

        self.update_invert_state()

    def update_invert_state(self):
        """Блокирует инверсию, если бинаризация отключена."""
        if self.binarize_var.get():
            self.invert_check.config(state="normal")
        else:
            self.invert_var.set(False)
            self.invert_check.config(state="disabled")

    def switch_mode(self):
        """Показывает панель параметров выбранного метода и прячет другую."""
        if self.mode.get() == "filter":
            self.morph_panel.grid_remove()
            self.filter_panel.grid()
        else:
            self.filter_panel.grid_remove()
            self.morph_panel.grid()


    def open_image(self):
        """Загружает изображение; большие изображения уменьшаются до MAX_SIDE по большей стороне."""
        path = filedialog.askopenfilename(
            title="Выберите изображение",
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff"), ("Все файлы", "*.*")])
        if not path:
            return
        try:
            image = Image.open(path).convert("RGB")
        except Exception:
            messagebox.showerror("Ошибка", "Не удалось открыть файл как изображение.")
            return

        image.thumbnail((self.MAX_SIDE, self.MAX_SIDE))
        self.original = np.array(image)
        self.result = None

        self.left_caption.config(text="Исходное изображение")
        self.show_image(self.left_label, self.original)
        self.right_label.config(image="", text="(нет результата)")
        self.right_label.image = None
        self.status.config(text=f"Размер изображения: {image.width} x {image.height}")
        self.hint.config(text="Выберите параметры и нажмите «Применить» для обработки изображения")

    def save_result(self):
        """Сохраняет результат обработки в файл."""
        if self.result is None:
            messagebox.showinfo("Нет результата", "Сначала нажмите «Применить».")
            return
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg")])
        if path:
            Image.fromarray(self.result).save(path)

    def use_result_as_input(self):
        """Делает результат новым исходным изображением. Нужно, чтобы применить несколько
        операций подряд (например, сначала открытие, а потом закрытие)."""
        if self.result is None:
            messagebox.showinfo("Нет результата", "Сначала нажмите «Применить».")
            return

        if self.result.ndim == 2:  # серое изображение превращаем в "цветное" из трёх одинаковых каналов
            self.original = np.stack([self.result] * 3, axis=2)
        else:
            self.original = self.result.copy()
        self.result = None

        self.left_caption.config(text="Исходное изображение")
        self.show_image(self.left_label, self.original)
        self.right_label.config(image="", text="(нет результата)")
        self.right_label.image = None
        self.status.config(text="Результат стал исходным изображением")
        self.hint.config(text="Теперь можно выбрать другие параметры и снова нажать «Применить»")

    def show_image(self, label, array):
        """Показывает изображение в исходном размере массива внутри фиксированной области 600 x 600."""
        image = Image.fromarray(array)
        photo = ImageTk.PhotoImage(image)
        label.config(image=photo, text="")
        label.image = photo  # без этой строки tkinter "забудет" картинку и покажет пустоту


    def apply(self):
        """Применяет выбранный метод к загруженному изображению и показывает результат."""
        if self.original is None:
            messagebox.showinfo("Нет изображения", "Сначала откройте изображение.")
            return

        start = time.time()

        if self.mode.get() == "filter":
            method = self.filter_method.get()
            size = int(self.filter_size.get())
            self.result = apply_to_image(self.original, lambda channel: order_filter(channel, method, size))
            description = f"{method}, окно {size}x{size}"
            self.left_caption.config(text="Исходное изображение")
            self.show_image(self.left_label, self.original)

        else:
            operation = self.morph_operation.get()
            shape = self.morph_shape.get()
            size = int(self.morph_size.get())
            offsets = make_structuring_element(shape, size)

            # Морфология работает с серым (или чёрно-белым) изображением
            gray = np.array(Image.fromarray(self.original).convert("L"))
            if self.binarize_var.get():
                gray = binarize(gray, self.threshold.get(), self.invert_var.get())
                self.left_caption.config(text="Вход морфологии (чёрно-белое)")
            else:
                self.left_caption.config(text="Вход морфологии (серое)")
            self.show_image(self.left_label, gray)

            self.result = morphology(gray, operation, offsets)
            description = f"{operation}, элемент «{shape}» {size}x{size}"

        self.show_image(self.right_label, self.result)
        self.status.config(text=f"{description}. Время обработки: {time.time() - start:.2f} с")
        self.hint.config(text="Чтобы применить следующую операцию к результату, нажмите кнопку «→ -<» между изображениями")


if __name__ == "__main__":
    window = tk.Tk()
    app = ImageApp(window)
    window.mainloop()
