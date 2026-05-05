"""
gui.py - Interfaz Grafica de Usuario con Tkinter
Ventana principal con editor de codigo, tabla de tokens y visor del arbol AST.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import tempfile
import sys
import time

from PIL import Image, ImageTk
from lexer import AnalizadorLexico
from parser_ast import AnalizadorSintactico, GeneradorArbol
from pdf_exporter import ExportadorPDF
from semantic_analyzer import AnalizadorSemantico


# ─── Paleta de colores ────────────────────────────────────────────────────────
C = {
    'bg_main':    '#0F0F1A',
    'bg_panel':   '#1A1A2E',
    'bg_editor':  '#13131F',
    'bg_tabla':   '#111120',
    'bg_card':    '#1E1E35',
    'azul':       '#6C9CF8',
    'azul_glow':  '#4A7AF5',
    'verde':      '#4EC994',
    'verde_glow': '#2EA87A',
    'rojo':       '#F07070',
    'naranja':    '#F0A060',
    'morado':     '#B06CF0',
    'cyan':       '#50D0E0',
    'texto':      '#D0D8F0',
    'texto_dim':  '#505870',
    'borde':      '#2A2A45',
    'borde_glow': '#4A4A70',
    'fila_par':   '#161628',
    'header_tab': '#222238',
    'acento':     '#7B6CF0',
}

FUENTE_CODIGO = ('Consolas', 11) if sys.platform == 'win32' else ('Courier', 11)
FUENTE_UI     = ('Segoe UI', 10) if sys.platform == 'win32' else ('Helvetica', 10)
FUENTE_TITULO = ('Segoe UI', 13, 'bold') if sys.platform == 'win32' else ('Helvetica', 13, 'bold')
FUENTE_MONO   = ('Consolas', 9) if sys.platform == 'win32' else ('Courier', 9)

CODIGO_EJEMPLO = """
# Ejemplo de codigo para el analizador
def sumar(a, b):
    return a + b

def multiplicar(x, y):
    return x * y

resultado1 = sumar(5, 3)
resultado2 = sumar(5, 3, 99)
resultado3 = restar(10, 4)

return 42
"""


# ─── Widget de boton moderno ──────────────────────────────────────────────────

class BotonModerno(tk.Canvas):
    """Boton con gradiente, borde luminoso y animacion hover."""

    def __init__(self, parent, texto, comando, color_base, color_texto=C['bg_main'],
                 ancho=170, alto=36, icono='', **kwargs):
        super().__init__(parent, width=ancho, height=alto,
                         bg=C['bg_panel'], highlightthickness=0, **kwargs)
        self.texto       = texto
        self.icono       = icono
        self.comando     = comando
        self.color_base = color_base
        self.color_texto = color_texto
        self.ancho       = ancho
        self.alto        = alto
        self._hover    = False
        self._disabled = False
        self._pulse    = 0
        self._animando = False

        self._dibujar()
        self.bind('<Enter>',            self._on_enter)
        self.bind('<Leave>',            self._on_leave)
        self.bind('<ButtonPress-1>',    self._on_press)
        self.bind('<ButtonRelease-1>',  self._on_release)

    def _hex_to_rgb(self, hex_color):
        h = hex_color.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _rgb_to_hex(self, r, g, b):
        return '#%02x%02x%02x' % (
            max(0, min(255, int(r))),
            max(0, min(255, int(g))),
            max(0, min(255, int(b)))
        )

    def _mezclar(self, c1, c2, t):
        r1, g1, b1 = self._hex_to_rgb(c1)
        r2, g2, b2 = self._hex_to_rgb(c2)
        return self._rgb_to_hex(r1+(r2-r1)*t, g1+(g2-g1)*t, b1+(b2-b1)*t)

    def _aclarar(self, hex_color, delta):
        r, g, b = self._hex_to_rgb(hex_color)
        return self._rgb_to_hex(r+delta, g+delta, b+delta)

    def _dibujar(self, presionado=False):
        self.delete('all')
        W, H = self.ancho, self.alto
        r = 8

        if self._disabled:
            fill   = C['bg_card']
            borde  = C['borde']
            ftexto = C['texto_dim']
        elif presionado:
            fill   = self._mezclar(self.color_base, '#000000', 0.3)
            borde  = self.color_base
            ftexto = self.color_texto
        elif self._hover:
            fill   = self._mezclar(self.color_base, C['bg_main'], 0.2)
            borde  = self._aclarar(self.color_base, 40)
            ftexto = self.color_texto
        else:
            fill   = self._mezclar(self.color_base, C['bg_main'], 0.35)
            borde  = self.color_base
            ftexto = self.color_texto

        # Sombra
        self.create_rectangle(3, 3, W-1, H-1,
                               fill=self._mezclar(self.color_base, '#000000', 0.7),
                               outline='', tags='sombra')

        # Cuerpo redondeado (simulado con rectángulo + óvalos)
        self.create_rectangle(r, 0, W-r, H, fill=fill, outline='')
        self.create_rectangle(0, r, W, H-r, fill=fill, outline='')
        for cx, cy in [(r, r), (W-r, r), (r, H-r), (W-r, H-r)]:
            self.create_oval(cx-r, cy-r, cx+r, cy+r, fill=fill, outline='')

        # Borde luminoso
        if not self._disabled:
            self.create_rectangle(r, 0, W-r-1, H-1, fill='', outline=borde)
            self.create_rectangle(0, r, W-1, H-r-1, fill='', outline=borde)

        # Highlight superior (efecto cristal)
        if not self._disabled and not presionado:
            hi = self._aclarar(fill, 30)
            self.create_rectangle(r, 1, W-r-1, H//3, fill=hi, outline='')

        # Texto
        label = (self.icono + ' ' + self.texto) if self.icono else self.texto
        self.create_text(W//2, H//2, text=label,
                         font=(FUENTE_UI[0], FUENTE_UI[1], 'bold'),
                         fill=ftexto if not self._disabled else C['texto_dim'],
                         tags='label')

        if not self._disabled:
            self.config(cursor='hand2')
        else:
            self.config(cursor='')

    def _on_enter(self, e):
        if not self._disabled:
            self._hover = True
            self._dibujar()

    def _on_leave(self, e):
        self._hover = False
        self._dibujar()

    def _on_press(self, e):
        if not self._disabled:
            self._dibujar(presionado=True)

    def _on_release(self, e):
        if not self._disabled:
            self._dibujar()
            self.comando()

    def config_state(self, estado):
        self._disabled = (estado == 'disabled')
        self._hover = False
        self._dibujar()


# ─── Barra de etapas ──────────────────────────────────────────────────────────

class BarraEtapas(tk.Canvas):
    """Visualiza las etapas del analisis con iconos y progreso animado."""

    ETAPAS_LEX = [
        ('01', 'Lectura',     'Leyendo codigo fuente'),
        ('02', 'Tokenizar',   'Identificando tokens'),
        ('03', 'Validar',     'Verificando errores'),
        ('04', 'Tabla',       'Construyendo tabla'),
    ]
    ETAPAS_SIN = [
        ('01', 'Tokens',      'Preparando tokens'),
        ('02', 'Parsing',     'Analisis sintactico'),
        ('03', 'AST',         'Generando arbol'),
        ('04', 'Render',      'Renderizando imagen'),
    ]

    def __init__(self, parent, **kwargs):
        super().__init__(parent, height=70, bg=C['bg_panel'],
                         highlightthickness=0, **kwargs)
        self._etapa_actual = -1
        self._etapa_error  = -1   # etapa donde ocurrio el fallo (-1 = sin fallo)
        self._etapas       = self.ETAPAS_LEX
        self._pulse        = 0
        self._animando     = False
        self.bind('<Configure>', lambda e: self._dibujar())

    def _hex_to_rgb(self, h):
        h = h.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _mezclar(self, c1, c2, t):
        r1,g1,b1 = self._hex_to_rgb(c1)
        r2,g2,b2 = self._hex_to_rgb(c2)
        return '#%02x%02x%02x' % (
            int(r1+(r2-r1)*t), int(g1+(g2-g1)*t), int(b1+(b2-b1)*t))

    def _dibujar(self):
        self.delete('all')
        W = self.winfo_width()
        H = self.winfo_height()
        if W <= 1:
            return

        n    = len(self._etapas)
        paso = W // n
        hay_error = self._etapa_error >= 0

        for i, (num, nombre, desc) in enumerate(self._etapas):
            cx = i * paso + paso // 2
            cy = H // 2

            # ── Determinar estado visual de este nodo ─────────────────────
            if hay_error:
                if i < self._etapa_error:
                    color   = C['verde']
                    simbolo = '✓'
                    fondo_simbolo = C['bg_main']
                elif i == self._etapa_error:
                    # Pulsante en rojo si aun animando, fijo si termino
                    if self._animando:
                        t = abs((self._pulse % 40) - 20) / 20.0
                        color = self._mezclar(C['rojo'], '#FF2020', t)
                    else:
                        color = C['rojo']
                    simbolo = '✗'
                    fondo_simbolo = '#ffffff'
                else:
                    color   = C['borde']
                    simbolo = num
                    fondo_simbolo = C['texto_dim']
            else:
                if i < self._etapa_actual:
                    color   = C['verde']
                    simbolo = '✓'
                    fondo_simbolo = C['bg_main']
                elif i == self._etapa_actual:
                    t = abs((self._pulse % 40) - 20) / 20.0
                    color   = self._mezclar(C['azul'], C['morado'], t)
                    simbolo = num
                    fondo_simbolo = C['bg_main']
                else:
                    color   = C['borde']
                    simbolo = num
                    fondo_simbolo = C['texto_dim']

            # ── Linea conectora ───────────────────────────────────────────
            if i < n - 1:
                x_ini = cx + 22
                x_fin = cx + paso - 22
                if hay_error:
                    if i < self._etapa_error:
                        c_lin = C['verde']
                        dash  = None
                    elif i == self._etapa_error:
                        c_lin = C['rojo']
                        dash  = (3, 4)   # linea roja cortada — proceso abortado
                    else:
                        c_lin = C['borde']
                        dash  = (4, 3)
                else:
                    c_lin = C['verde'] if i < self._etapa_actual else C['borde']
                    dash  = None if i < self._etapa_actual else (4, 3)
                self.create_line(x_ini, cy, x_fin, cy,
                                 fill=c_lin, width=2, dash=dash)

            # ── Circulo con halo ──────────────────────────────────────────
            r = 16
            es_activo = (not hay_error and i == self._etapa_actual) or \
                        (hay_error and i == self._etapa_error and self._animando)
            if es_activo:
                t2  = abs((self._pulse % 30) - 15) / 15.0
                hr  = int(r + 5 + t2 * 4)
                halo = self._mezclar(color, C['bg_panel'], 0.5)
                self.create_oval(cx-hr, cy-hr, cx+hr, cy+hr,
                                 fill=halo, outline='')

            # Borde extra en rojo cuando hay error en esta etapa
            if hay_error and i == self._etapa_error:
                self.create_oval(cx-r-2, cy-r-2, cx+r+2, cy+r+2,
                                 fill='', outline=C['rojo'], width=2)

            self.create_oval(cx-r, cy-r, cx+r, cy+r,
                             fill=color,
                             outline=self._mezclar(color, '#ffffff', 0.3))

            self.create_text(cx, cy, text=simbolo,
                             font=(FUENTE_MONO[0], 8, 'bold'),
                             fill=fondo_simbolo)

            # ── Nombre debajo ─────────────────────────────────────────────
            color_nombre = color if (hay_error and i <= self._etapa_error) or \
                                    (not hay_error and i <= self._etapa_actual) \
                           else C['texto_dim']
            self.create_text(cx, cy + r + 8, text=nombre,
                             font=(FUENTE_MONO[0], 7),
                             fill=color_nombre)

        # ── Mensaje de error flotante sobre la etapa fallida ──────────────
        if hay_error:
            ex  = self._etapa_error * paso + paso // 2
            self.create_text(ex, H - 6,
                             text='ERROR',
                             font=(FUENTE_MONO[0], 7, 'bold'),
                             fill=C['rojo'])

    def iniciar(self, modo='lexico'):
        self._etapas = self.ETAPAS_LEX if modo == 'lexico' else self.ETAPAS_SIN
        self._etapa_actual = 0
        self._etapa_error  = -1
        self._animando = True
        self._animar()

    def avanzar(self):
        if self._etapa_actual < len(self._etapas) - 1:
            self._etapa_actual += 1
        self._dibujar()

    def fallar(self, etapa=None):
        """Detiene el proceso en la etapa indicada (o actual) y la marca en rojo."""
        if etapa is not None:
            self._etapa_error = etapa
        else:
            self._etapa_error = self._etapa_actual
        self._animando = False
        self._dibujar()

    def completar(self):
        self._etapa_actual = len(self._etapas)
        self._etapa_error  = -1
        self._animando = False
        self._dibujar()

    def resetear(self):
        self._etapa_actual = -1
        self._etapa_error  = -1
        self._animando = False
        self._dibujar()

    def _animar(self):
        if not self._animando:
            return
        self._pulse += 1
        self._dibujar()
        self.after(50, self._animar)


# ─── Panel de estadísticas ────────────────────────────────────────────────────

class PanelStats(tk.Frame):
    """Tarjetas con contadores animados."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=C['bg_panel'], **kwargs)
        self._cards = {}
        self._targets = {}
        self._values  = {}

        items = [
            ('tokens',     'Tokens',     C['azul'],    '0'),
            ('palabras_r', 'Palabras R.', C['morado'],  '0'),
            ('nums',       'Numeros',    C['cyan'],    '0'),
            ('ids',        'Identificad.', C['verde'],  '0'),
            ('err_lex',    'Err. Lexicos', C['rojo'],   '0'),
            ('err_sin',    'Err. Sint.',  C['naranja'], '—'),
        ]

        for key, label, color, val in items:
            card = self._crear_card(key, label, color, val)
            card.pack(side='left', padx=4, pady=4, fill='x', expand=True)
            self._cards[key] = card
            self._values[key] = 0
            self._targets[key] = 0

    def _crear_card(self, key, label, color, val):
        frame = tk.Frame(self, bg=C['bg_card'],
                         highlightbackground=color,
                         highlightthickness=1)
        tk.Label(frame, text=label, font=(FUENTE_MONO[0], 7),
                 bg=C['bg_card'], fg=C['texto_dim']).pack(pady=(4, 0))
        lbl = tk.Label(frame, text=val,
                       font=(FUENTE_UI[0], 14, 'bold'),
                       bg=C['bg_card'], fg=color)
        lbl.pack(pady=(0, 4))
        frame._lbl = lbl
        frame._color = color
        return frame

    def actualizar(self, datos):
        """datos: dict con las mismas claves de _cards."""
        for key, val in datos.items():
            if key in self._cards:
                if isinstance(val, int):
                    self._targets[key] = val
                    if val == 0:
                        # Forzar directo — la animacion no llega a 0 si ya estaba en 0
                        self._values[key] = 0
                        self._cards[key]._lbl.config(text='0')
                    else:
                        self._animar_contador(key)
                else:
                    self._cards[key]._lbl.config(text=str(val))

    def _animar_contador(self, key):
        curr = self._values[key]
        tgt  = self._targets[key]
        if curr == tgt:
            return
        diff = tgt - curr
        step = max(1, abs(diff) // 8)
        if diff > 0:
            nuevo = min(curr + step, tgt)
        else:
            nuevo = max(curr - step, tgt)
        self._values[key] = nuevo
        self._cards[key]._lbl.config(text=str(nuevo))
        if nuevo != tgt:
            self.after(30, lambda: self._animar_contador(key))


# ─── Aplicacion principal ─────────────────────────────────────────────────────

class AplicacionCompilador:
    """Ventana principal de la aplicacion."""

    def __init__(self, root):
        self.root = root
        self.root.title("Analizador Lexico y Sintactico — Compiladores")
        self.root.geometry("1400x860")
        self.root.configure(bg=C['bg_main'])
        self.root.minsize(1000, 650)

        # Estado del analisis
        self.tokens_actuales   = []
        self.errores_lexicos   = []
        self.errores_sintac    = []
        self.errores_semanticos = []
        self.ruta_imagen_arbol = None
        self.imagen_tk         = None
        self.img_original      = None
        self.zoom_nivel        = 1.0
        self._drag_x = 0
        self._drag_y = 0
        self.dir_temp = tempfile.mkdtemp()

        # Analisis lexico en vivo (debounce)
        self._job_live = None

        # Barra de progreso
        self._prog_valor    = 0.0
        self._prog_destino  = 0.0
        self._prog_animando = False
        self._prog_shimmer  = 0

        # Modulos del compilador
        self.lexer           = AnalizadorLexico()
        self.gen_arbol       = GeneradorArbol()
        self.exportador      = ExportadorPDF()
        self.analizador_sem  = AnalizadorSemantico()

        self._conf_estilos()
        self._crear_barra()
        self._crear_contenido()

        # Insertar codigo de ejemplo SIN disparar analisis
        self.editor.insert('1.0', CODIGO_EJEMPLO)
        self._actualizar_lineas()
        self._aplicar_colores_editor()   # solo colorea, NO analiza

    # ── Estilos TTK ──────────────────────────────────────────────────────────

    def _conf_estilos(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure('App.TNotebook',
                    background=C['bg_main'], borderwidth=0)
        s.configure('App.TNotebook.Tab',
                    background=C['bg_main'], foreground=C['texto_dim'],
                    padding=[18, 9], font=FUENTE_UI, borderwidth=0)
        s.map('App.TNotebook.Tab',
              background=[('selected', C['header_tab'])],
              foreground=[('selected', C['azul'])])
        s.configure('Tok.Treeview',
                    background=C['bg_tabla'], foreground=C['texto'],
                    fieldbackground=C['bg_tabla'], rowheight=26, font=FUENTE_UI)
        s.configure('Tok.Treeview.Heading',
                    background=C['header_tab'], foreground=C['azul'],
                    font=(FUENTE_UI[0], FUENTE_UI[1], 'bold'), relief='flat')
        s.map('Tok.Treeview',
              background=[('selected', C['acento'])],
              foreground=[('selected', C['bg_main'])])
        s.configure('TScrollbar',
                    background=C['bg_card'], troughcolor=C['bg_main'],
                    borderwidth=0, arrowcolor=C['texto_dim'])

    # ── Barra superior ────────────────────────────────────────────────────────

    def _crear_barra(self):
        barra = tk.Frame(self.root, bg=C['bg_panel'], height=56)
        barra.pack(fill='x', side='top')
        barra.pack_propagate(False)

        # Indicador de color a la izquierda
        acento = tk.Frame(barra, bg=C['acento'], width=4)
        acento.pack(side='left', fill='y')

        tk.Label(barra,
                 text='  ⬡  Analizador Lexico & Sintactico',
                 font=FUENTE_TITULO,
                 bg=C['bg_panel'], fg=C['texto']).pack(side='left', padx=16, pady=8)

        self.lbl_estado = tk.Label(barra, text='● Listo',
                                   font=(FUENTE_UI[0], FUENTE_UI[1], 'bold'),
                                   bg=C['bg_panel'], fg=C['verde'])
        self.lbl_estado.pack(side='right', padx=20)

        tk.Label(barra,
                 text='Compiladores — Python 3 + Tkinter  ',
                 font=(FUENTE_MONO[0], 8),
                 bg=C['bg_panel'], fg=C['texto_dim']).pack(side='right', padx=4)

    # ── Layout principal ──────────────────────────────────────────────────────

    def _crear_contenido(self):
        panel = tk.Frame(self.root, bg=C['bg_main'])
        panel.pack(fill='both', expand=True, padx=8, pady=8)

        izq = tk.Frame(panel, bg=C['bg_panel'], width=560)
        izq.pack(side='left', fill='both', padx=(0, 6))
        izq.pack_propagate(False)
        self._crear_editor(izq)

        der = tk.Frame(panel, bg=C['bg_main'])
        der.pack(side='right', fill='both', expand=True)
        self._crear_resultados(der)

    # ── Editor de codigo ──────────────────────────────────────────────────────

    def _crear_editor(self, padre):
        cabecera = tk.Frame(padre, bg=C['bg_panel'])
        cabecera.pack(fill='x', padx=8, pady=(8, 0))
        tk.Label(cabecera, text='◈ Editor de Codigo',
                 font=(FUENTE_UI[0], 11, 'bold'),
                 bg=C['bg_panel'], fg=C['texto']).pack(side='left')

        separador = tk.Frame(padre, bg=C['borde'], height=1)
        separador.pack(fill='x', padx=8, pady=4)

        frame = tk.Frame(padre, bg=C['bg_editor'])
        frame.pack(fill='both', expand=True, padx=6, pady=(0, 4))

        self.canvas_nums = tk.Canvas(frame, width=42, bg=C['bg_panel'],
                                      highlightthickness=0)
        self.canvas_nums.pack(side='left', fill='y')

        scroll_y = ttk.Scrollbar(frame)
        scroll_y.pack(side='right', fill='y')
        scroll_x = ttk.Scrollbar(frame, orient='horizontal')
        scroll_x.pack(side='bottom', fill='x')

        self.editor = tk.Text(
            frame, wrap='none', font=FUENTE_CODIGO,
            bg=C['bg_editor'], fg=C['texto'],
            insertbackground=C['azul'],
            selectbackground=C['acento'], selectforeground=C['bg_main'],
            relief='flat', bd=0, padx=10, pady=6, undo=True,
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
        )
        self.editor.pack(side='left', fill='both', expand=True)
        scroll_y.config(command=self.editor.yview)
        scroll_x.config(command=self.editor.xview)

        # Solo actualiza numeros de linea y colores — NO ejecuta analisis
        for evento in ('<KeyRelease>', '<MouseWheel>', '<Button-1>'):
            self.editor.bind(evento, self._actualizar_lineas)
        self.editor.bind('<KeyPress>',   self._aplicar_colores_editor)
        self.editor.bind('<KeyRelease>', self._aplicar_colores_editor)

        # Analisis lexico en vivo con debounce de 500 ms
        # <<Modified>> captura todo: teclado, pegar, borrar seleccion, Ctrl+A+Delete
        # Polling cada 300 ms — detecta teclado, paste y borrado masivo
        self._ultimo_codigo = ''
        self.root.after(300, self._poll_editor)

        # Tags de colores del editor (resaltado visual solamente)
        self.editor.tag_config('pr',  foreground='#A6E3A1')
        self.editor.tag_config('op',  foreground='#FAB387')
        self.editor.tag_config('num', foreground='#CBA6F7')
        self.editor.tag_config('id',  foreground='#89DCEB')
        self.editor.tag_config('str', foreground='#F38BA8')
        self.editor.tag_config('com', foreground='#6C7086')
        self.editor.tag_config('del', foreground='#CDD6F4')
        self.editor.tag_config('err', background='#4A1A1A', foreground=C['rojo'])

        self._crear_botones(padre)
        self._crear_panel_mensajes(padre)

    def _crear_botones(self, padre):
        # Fila principal de analisis
        fila1 = tk.Frame(padre, bg=C['bg_panel'])
        fila1.pack(fill='x', padx=6, pady=(2, 2))

        self.btn_lex = BotonModerno(
            fila1, 'Analizar Lexico', self._hacer_lexico,
            C['azul'], C['bg_main'], ancho=175, alto=34, icono='◈')
        self.btn_lex.pack(side='left', padx=3)

        self.btn_sin = BotonModerno(
            fila1, 'Analizar Sintactico', self._hacer_sintactico,
            C['verde'], C['bg_main'], ancho=185, alto=34, icono='⬡')
        self.btn_sin.pack(side='left', padx=3)

        self.btn_sem = BotonModerno(
            fila1, 'Analizar Semantico', self._hacer_semantico,
            C['morado'], C['bg_main'], ancho=185, alto=34, icono='◉')
        self.btn_sem.pack(side='left', padx=3)

        self.btn_limpiar = BotonModerno(
            fila1, 'Limpiar', self._limpiar,
            C['borde'], C['texto_dim'], ancho=90, alto=34)
        self.btn_limpiar.pack(side='right', padx=3)

        # Fila de exportacion
        fila2 = tk.Frame(padre, bg=C['bg_panel'])
        fila2.pack(fill='x', padx=6, pady=(0, 6))

        for texto, cmd, color in [
            ('PDF Lexico',    self._pdf_lexico,     C['borde']),
            ('PDF Sintactico', self._pdf_sintactico, C['borde']),
            ('PDF Semantico', self._pdf_semantico,  C['borde']),
            ('PDF Completo',  self._pdf_completo,   C['naranja']),
        ]:
            BotonModerno(fila2, texto, cmd, color,
                         C['texto'] if color == C['borde'] else C['bg_main'],
                         ancho=145, alto=28).pack(side='left', padx=3)

    def _crear_panel_mensajes(self, padre):
        frame = tk.Frame(padre, bg=C['bg_panel'])
        frame.pack(fill='x', padx=6, pady=(0, 6))

        tk.Label(frame, text='Consola', font=(FUENTE_MONO[0], 8),
                 bg=C['bg_panel'], fg=C['texto_dim']).pack(anchor='w', padx=4, pady=(2, 0))

        self.txt_msg = tk.Text(frame, height=4,
                                font=(FUENTE_MONO[0], 9),
                                bg=C['bg_main'], fg=C['texto'],
                                relief='flat', state='disabled', wrap='word',
                                padx=6, pady=4)
        self.txt_msg.pack(fill='x', padx=3, pady=(0, 3))
        self.txt_msg.tag_config('ok',   foreground=C['verde'])
        self.txt_msg.tag_config('err',  foreground=C['rojo'])
        self.txt_msg.tag_config('info', foreground=C['azul'])
        self.txt_msg.tag_config('warn', foreground=C['naranja'])

    # ── Numeros de linea ──────────────────────────────────────────────────────

    def _actualizar_lineas(self, event=None):
        self.canvas_nums.delete('all')
        contenido = self.editor.get('1.0', 'end-1c')
        n = contenido.count('\n') + 1
        primera = int(self.editor.index('@0,0').split('.')[0])
        for i in range(primera, n + 2):
            info = self.editor.dlineinfo('%d.0' % i)
            if info:
                self.canvas_nums.create_text(
                    36, info[1] + 2, text=str(i),
                    font=(FUENTE_CODIGO[0], FUENTE_CODIGO[1] - 1),
                    fill=C['texto_dim'], anchor='ne'
                )

    # ── Analisis lexico en vivo (polling) ────────────────────────────────────

    def _poll_editor(self):
        """Revisa cada 300 ms si el contenido cambio. Cubre teclado, paste y borrado masivo."""
        try:
            codigo = self.editor.get('1.0', 'end-1c')
        except Exception:
            self.root.after(300, self._poll_editor)
            return
        if codigo != self._ultimo_codigo:
            self._ultimo_codigo = codigo
            # Ejecutar directo, sin job intermedio, para no perder el estado vacio
            self._analisis_live_con(codigo)
        self.root.after(300, self._poll_editor)

    def _analisis_live(self):
        """Wrapper para compatibilidad — lee el editor y delega."""
        self._job_live = None
        codigo = self.editor.get('1.0', 'end-1c')
        self._analisis_live_con(codigo)

    def _analisis_live_con(self, codigo):
        """Corre el lexico con el codigo dado y actualiza la tabla."""
        if not codigo.strip():
            for item in self.tabla.get_children():
                self.tabla.delete(item)
            self.tabla.insert('', 'end',
                values=('—', 'Editor vacio', '', '', '', ''), tags=('del',))
            self.panel_stats.actualizar({
                'tokens': 0, 'palabras_r': 0,
                'nums': 0, 'ids': 0, 'err_lex': 0, 'err_sin': '—',
            })
            self.etapas_lex.resetear()
            return
        try:
            tokens, errores = self.lexer.analizar(codigo)
        except Exception:
            return
        self._mostrar_resultado_lexico_live(tokens, errores)

    def _mostrar_resultado_lexico_live(self, tokens, errores):
        """Igual que _mostrar_resultado_lexico pero sin animar etapas ni cambiar estado."""
        self.tokens_actuales = tokens
        self.errores_lexicos = errores

        for item in self.tabla.get_children():
            self.tabla.delete(item)

        for i, t in enumerate(tokens, 1):
            tag = self._tag(t.categoria, t.tipo)
            self.tabla.insert('', 'end',
                values=(i, t.valor, t.tipo, t.categoria, t.linea, t.columna),
                tags=(tag,))

        if errores:
            for e in errores:
                self.tabla.insert('', 'end',
                    values=('!', e['caracter'], 'ERROR_LEXICO', 'Error Lexico',
                            e['linea'], e['columna']),
                    tags=('err',))

        resumen = self.lexer.obtener_resumen()
        self.panel_stats.actualizar({
            'tokens':     len(tokens),
            'palabras_r': resumen.get('Palabra Reservada', resumen.get('Reservada', 0)),
            'nums':       resumen.get('Numero', resumen.get('Entero', 0)),
            'ids':        resumen.get('Identificador', 0),
            'err_lex':    len(errores),
            'err_sin':    '—',
        })
        self.etapas_lex.completar()

    # ── Coloreado del editor (SIN analizar ni llenar tabla) ───────────────────

    def _aplicar_colores_editor(self, event=None):
        """Solo aplica colores sintacticos en el editor. No toca la tabla ni el AST."""
        for tag in ('pr', 'op', 'num', 'id', 'str', 'com', 'del', 'err'):
            self.editor.tag_remove(tag, '1.0', 'end')

        codigo = self.editor.get('1.0', 'end-1c')
        if not codigo.strip():
            return

        try:
            tokens, errores = self.lexer.analizar(codigo)
        except Exception:
            return

        for token in tokens:
            inicio = '%d.%d' % (token.linea, token.columna - 1)
            fin    = '%d.%d' % (token.linea, token.columna - 1 + len(token.valor))
            tag = self._tag(token.categoria, token.tipo)
            self.editor.tag_add(tag, inicio, fin)

        for error in errores:
            inicio = '%d.%d' % (error['linea'], error['columna'] - 1)
            fin    = '%d.%d' % (error['linea'], error['columna'])
            self.editor.tag_add('err', inicio, fin)

    # ── Panel de resultados ───────────────────────────────────────────────────

    def _crear_resultados(self, padre):
        self.nb = ttk.Notebook(padre, style='App.TNotebook')
        self.nb.pack(fill='both', expand=True)

        tab_lex = tk.Frame(self.nb, bg=C['bg_main'])
        self.nb.add(tab_lex, text='  ◈ Analisis Lexico  ')
        self._crear_tab_lexico(tab_lex)

        tab_sin = tk.Frame(self.nb, bg=C['bg_main'])
        self.nb.add(tab_sin, text='  ⬡ Analisis Sintactico  ')
        self._crear_tab_sintactico(tab_sin)

        tab_sem = tk.Frame(self.nb, bg=C['bg_main'])
        self.nb.add(tab_sem, text='  ◉ Analisis Semantico  ')
        self._crear_tab_semantico(tab_sem)

    # ── Tab Lexico ────────────────────────────────────────────────────────────

    def _crear_tab_lexico(self, padre):
        # Panel de estadisticas (tarjetas animadas) — altura fija
        frame_stats = tk.Frame(padre, bg=C['bg_panel'], height=62)
        frame_stats.pack(fill='x', padx=6, pady=(6, 2))
        frame_stats.pack_propagate(False)
        self.panel_stats = PanelStats(frame_stats)
        self.panel_stats.pack(fill='both', expand=True)

        # Barra de etapas — altura fija
        frame_etapas = tk.Frame(padre, bg=C['bg_panel'], height=76)
        frame_etapas.pack(fill='x', padx=6, pady=(0, 4))
        frame_etapas.pack_propagate(False)
        self.etapas_lex = BarraEtapas(frame_etapas)
        self.etapas_lex.pack(fill='both', expand=True)
        # Forzar dibujado inicial cuando el widget tenga dimensiones reales
        padre.after(120, self.etapas_lex._dibujar)

        # Tabla de tokens
        frame = tk.Frame(padre, bg=C['bg_main'])
        frame.pack(fill='both', expand=True, padx=6, pady=(0, 6))

        cols = ('#', 'valor', 'tipo', 'categoria', 'linea', 'col')
        self.tabla = ttk.Treeview(frame, columns=cols, show='headings',
                                   style='Tok.Treeview', selectmode='browse')

        encabezados = {
            '#':         ('#',             45,  'center'),
            'valor':     ('Token (Valor)',  140, 'w'),
            'tipo':      ('Tipo Interno',   180, 'w'),
            'categoria': ('Categoria',      160, 'w'),
            'linea':     ('Linea',          60, 'center'),
            'col':       ('Col.',           50, 'center'),
        }
        for col, (texto, ancho, ancla) in encabezados.items():
            self.tabla.heading(col, text=texto,
                                anchor='center' if ancla == 'center' else 'w')
            self.tabla.column(col, width=ancho, minwidth=40, anchor=ancla)

        sy = ttk.Scrollbar(frame, orient='vertical',   command=self.tabla.yview)
        sx = ttk.Scrollbar(frame, orient='horizontal',  command=self.tabla.xview)
        self.tabla.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.pack(side='right', fill='y')
        sx.pack(side='bottom', fill='x')
        self.tabla.pack(fill='both', expand=True)

        self.tabla.tag_configure('pr',  background='#1E2E1E', foreground='#A6E3A1')
        self.tabla.tag_configure('op',  background='#2A2A1A', foreground='#FAB387')
        self.tabla.tag_configure('num', background='#1A1A2E', foreground='#CBA6F7')
        self.tabla.tag_configure('id',  background=C['bg_tabla'], foreground='#89DCEB')
        self.tabla.tag_configure('str', background='#2E1A1A', foreground='#F38BA8')
        self.tabla.tag_configure('del', background=C['fila_par'], foreground=C['texto_dim'])
        self.tabla.tag_configure('com', background='#1A2A1A', foreground='#6C7086')
        self.tabla.tag_configure('err', background='#3A1010', foreground=C['rojo'])
        self.tabla.tag_configure('warn', background='#2A2010', foreground=C['naranja'])

        # Placeholder inicial
        self.tabla.insert('', 'end',
                          values=('—', 'Presiona "Analizar Lexico" para ver los tokens',
                                  '', '', '', ''),
                          tags=('del',))

    # ── Tab Sintactico ────────────────────────────────────────────────────────

    def _crear_tab_sintactico(self, padre):
        # Barra de etapas — altura fija
        frame_etapas_sin = tk.Frame(padre, bg=C['bg_panel'], height=76)
        frame_etapas_sin.pack(fill='x', padx=6, pady=6)
        frame_etapas_sin.pack_propagate(False)
        self.etapas_sin = BarraEtapas(frame_etapas_sin)
        self.etapas_sin.pack(fill='both', expand=True)
        padre.after(120, self.etapas_sin._dibujar)

        # Barra de progreso
        self._crear_barra_progreso(padre)

        # Toolbar del AST
        tb = tk.Frame(padre, bg=C['bg_panel'])
        tb.pack(fill='x', padx=6, pady=(2, 4))
        tk.Label(tb, text='Arbol de Sintaxis Abstracta (AST)',
                 font=(FUENTE_UI[0], 10),
                 bg=C['bg_panel'], fg=C['texto_dim']).pack(side='left', padx=10, pady=6)

        self.lbl_zoom = tk.Label(tb, text='Zoom: 100%',
                                  font=FUENTE_UI, bg=C['bg_panel'], fg=C['texto_dim'])
        self.lbl_zoom.pack(side='right', padx=6)

        for txt, cmd in [('Abrir', self._abrir_arbol_ventana),
                         ('Fit',   self._zoom_fit),
                         ('+',     self._zoom_in),
                         ('-',     self._zoom_out),
                         ('100%',  self._zoom_reset)]:
            tk.Button(tb, text=txt, command=cmd,
                      font=(FUENTE_MONO[0], 9),
                      bg=C['borde'], fg=C['texto'],
                      activebackground=C['borde_glow'],
                      activeforeground=C['texto'],
                      relief='flat', cursor='hand2',
                      padx=8, pady=3, bd=0).pack(side='right', padx=2, pady=5)

        # --- PANEL DE ERRORES AL FONDO ---
        frame_err = tk.Frame(padre, bg=C['bg_panel'])
        frame_err.pack(side='bottom', fill='x', padx=6, pady=(4, 6))

        tk.Label(frame_err, text='Errores Sintacticos',
                 font=(FUENTE_UI[0], 9, 'bold'),
                 bg=C['bg_panel'], fg=C['rojo']).pack(anchor='w', padx=8, pady=(6, 2))

        cols_err = ('n', 'descripcion')
        # ---> TABLA DE ERRORES CON ALTURA DE 10 FILAS <---
        self.tabla_errores_sint = ttk.Treeview(
            frame_err, columns=cols_err, show='headings',
            style='Tok.Treeview', height=10)
        self.tabla_errores_sint.heading('n',           text='#',          anchor='center')
        self.tabla_errores_sint.heading('descripcion', text='Descripcion', anchor='w')
        self.tabla_errores_sint.column('n',            width=35,  minwidth=30,  anchor='center')
        self.tabla_errores_sint.column('descripcion',  width=600, minwidth=100, anchor='w')
        self.tabla_errores_sint.tag_configure('err', background='#3A1010', foreground=C['rojo'])
        self.tabla_errores_sint.tag_configure('ok',  background='#0A2A0A', foreground=C['verde'])
        
        # Scrollbar para la tabla de errores
        sy_err = ttk.Scrollbar(frame_err, orient='vertical', command=self.tabla_errores_sint.yview)
        self.tabla_errores_sint.configure(yscrollcommand=sy_err.set)
        sy_err.pack(side='right', fill='y')
        self.tabla_errores_sint.pack(fill='x', padx=5, pady=(0, 6))

        self.tabla_errores_sint.insert('', 'end',
            values=('—', 'Presiona "Analizar Sintactico" para ver resultados'),
            tags=('ok',))

        # --- CANVAS AST EN EL MEDIO (Ahorá con altura límite para dejar espacio) ---
        frame_ast = tk.Frame(padre, bg=C['bg_main'])
        frame_ast.pack(side='top', fill='both', expand=True, padx=6)
        
        sy = ttk.Scrollbar(frame_ast, orient='vertical')
        sx = ttk.Scrollbar(frame_ast, orient='horizontal')
        # ---> LIENZO MÁS PEQUEÑO CON height=250 <---
        self.canvas = tk.Canvas(frame_ast, bg=C['bg_editor'],
                                 highlightthickness=0,
                                 height=250, 
                                 yscrollcommand=sy.set,
                                 xscrollcommand=sx.set)
        sy.config(command=self.canvas.yview)
        sx.config(command=self.canvas.xview)
        sy.pack(side='right', fill='y')
        sx.pack(side='bottom', fill='x')
        self.canvas.pack(fill='both', expand=True)

        self.canvas.create_text(400, 125,
            text='Presiona "Analizar Sintactico"\npara ver el arbol AST aqui',
            font=(FUENTE_UI[0], 13), fill=C['texto_dim'],
            justify='center', tags='msg_inicial')

        self.canvas.bind('<MouseWheel>',      self._on_wheel)
        self.canvas.bind('<Button-4>',        self._on_wheel)
        self.canvas.bind('<Button-5>',        self._on_wheel)
        self.canvas.bind('<ButtonPress-1>',   self._drag_inicio)
        self.canvas.bind('<B1-Motion>',       self._drag_move)
        self.canvas.bind('<ButtonRelease-1>', self._drag_fin)

    # ── Barra de progreso ─────────────────────────────────────────────────────

    def _crear_barra_progreso(self, padre):
        frame_prog = tk.Frame(padre, bg=C['bg_panel'])
        frame_prog.pack(fill='x', padx=6, pady=(0, 4))

        fila = tk.Frame(frame_prog, bg=C['bg_panel'])
        fila.pack(fill='x', padx=8, pady=(4, 2))

        self.lbl_prog_texto = tk.Label(fila, text='Listo',
            font=(FUENTE_MONO[0], 8), bg=C['bg_panel'], fg=C['texto_dim'])
        self.lbl_prog_texto.pack(side='left')

        self.lbl_prog_pct = tk.Label(fila, text='',
            font=(FUENTE_MONO[0], 8, 'bold'), bg=C['bg_panel'], fg=C['naranja'])
        self.lbl_prog_pct.pack(side='right')

        self.canvas_prog = tk.Canvas(frame_prog, height=14,
                                      bg=C['bg_main'],
                                      highlightthickness=1,
                                      highlightbackground=C['borde'])
        self.canvas_prog.pack(fill='x', padx=8, pady=(0, 6))
        self.canvas_prog.bind('<Configure>', lambda e: self._dibujar_barra())
        frame_prog.after(150, self._dibujar_barra)

    def _color_barra(self):
        v = self._prog_valor
        if v < 0.35:   return C['azul']
        elif v < 0.70: return C['naranja']
        else:          return C['verde']

    def _ajustar_color(self, hex_color, delta):
        def clamp(x): return max(0, min(255, x))
        r = clamp(int(hex_color[1:3], 16) + delta)
        g = clamp(int(hex_color[3:5], 16) + delta)
        b = clamp(int(hex_color[5:7], 16) + delta)
        return '#%02x%02x%02x' % (r, g, b)

    def _dibujar_barra(self):
        c = self.canvas_prog
        c.delete('all')
        W = c.winfo_width()
        H = c.winfo_height()
        if W <= 1 or H <= 1:
            return

        c.create_rectangle(0, 0, W, H, fill=C['bg_main'], outline='')
        fill_w = int(W * self._prog_valor)

        if fill_w > 2:
            color = self._color_barra()
            c.create_rectangle(0, 0, fill_w, H, fill=color, outline='')
            c.create_rectangle(0, 0, fill_w, max(1, H//3),
                               fill=self._ajustar_color(color, 60), outline='')
            c.create_rectangle(0, H - max(1, H//4), fill_w, H,
                               fill=self._ajustar_color(color, -50), outline='')

            if self._prog_animando:
                sx = int((self._prog_shimmer % (W + 60)) - 30)
                x0 = max(0, min(sx,      fill_w))
                x1 = max(0, min(sx + 18, fill_w))
                if x1 > x0:
                    c.create_rectangle(x0, 0, x1, H,
                                       fill=self._ajustar_color(color, 90),
                                       outline='', stipple='gray50')
            bx = max(0, fill_w - 3)
            c.create_rectangle(bx, 0, fill_w, H,
                               fill=self._ajustar_color(color, 110),
                               outline='', stipple='gray25')

        for pct in (0.25, 0.50, 0.75):
            x = int(W * pct)
            c.create_line(x, 1, x, H-1, fill='#1A1A30', width=1)

        c.create_rectangle(0, 0, W-1, H-1, outline=C['borde'], fill='')

    def _animar_barra(self):
        if not self._prog_animando:
            return
        diff = self._prog_destino - self._prog_valor
        if abs(diff) < 0.003:
            self._prog_valor = self._prog_destino
        else:
            self._prog_valor += diff * 0.15
        self._prog_shimmer += 7
        pct = int(self._prog_valor * 100)
        self.lbl_prog_pct.config(
            text='%d%%' % pct,
            fg=C['verde'] if pct >= 100 else C['naranja'])
        self._dibujar_barra()
        if self._prog_animando:
            self.root.after(16, self._animar_barra)

    def _iniciar_progreso(self):
        self._prog_valor    = 0.0
        self._prog_destino  = 0.0
        self._prog_animando = True
        self._prog_shimmer  = 0
        self.lbl_prog_texto.config(text='Analizando...', fg=C['azul'])
        self.lbl_prog_pct.config(text='0%', fg=C['naranja'])
        self._animar_barra()

    def _avanzar_progreso(self, destino, texto=None):
        self._prog_destino = max(0.0, min(1.0, destino))
        if texto:
            self.lbl_prog_texto.config(text=texto, fg=C['azul'])

    def _finalizar_progreso(self):
        self._prog_destino = 1.0
        self.lbl_prog_texto.config(text='Completado', fg=C['verde'])
        self.root.after(900, self._reset_progreso)

    def _reset_progreso(self):
        self._prog_animando = False
        self._prog_valor    = 0.0
        self._prog_destino  = 0.0
        self.lbl_prog_texto.config(text='Listo', fg=C['texto_dim'])
        self.lbl_prog_pct.config(text='')
        self._dibujar_barra()

    # ── ANALISIS LEXICO (solo lexico) ─────────────────────────────────────────

    def _hacer_lexico(self):
        """Ejecuta SOLO el analisis lexico. No toca el AST."""
        codigo = self.editor.get('1.0', 'end-1c')
        if not codigo.strip():
            self._msg('No hay codigo para analizar.', 'warn')
            return

        self._set_estado('Analizando lexico...', C['naranja'])
        self.btn_lex.config_state('disabled')
        self._limpiar_mensajes()
        self.etapas_lex.iniciar(modo='lexico')

        def tarea():
            # ── Etapa 0: Lectura ──────────────────────────────────────────
            # (ya activa desde iniciar — etapa_actual=0)
            time.sleep(0.08)

            # ── Etapa 1: Tokenizar ────────────────────────────────────────
            self.root.after(0, lambda: self.etapas_lex.avanzar())   # → etapa 1
            time.sleep(0.06)
            tokens, errores_lex = self.lexer.analizar(codigo)

            # Si hay errores lexicos → fallo en etapa 1 (Tokenizar), detener aqui
            if errores_lex:
                self.root.after(0, lambda: self.etapas_lex.fallar(1))
                self.root.after(0, lambda: self._mostrar_fallo_lexico(tokens, errores_lex))
                return

            # ── Etapa 2: Validar ──────────────────────────────────────────
            self.root.after(0, lambda: self.etapas_lex.avanzar())   # → etapa 2
            time.sleep(0.06)
            # Validacion adicional (tokens vacios = nada reconocible)
            if not tokens:
                self.root.after(0, lambda: self.etapas_lex.fallar(2))
                self.root.after(0, lambda: self._mostrar_fallo_lexico(tokens, []))
                return

            # ── Etapa 3: Tabla ────────────────────────────────────────────
            self.root.after(0, lambda: self.etapas_lex.avanzar())   # → etapa 3
            time.sleep(0.06)

            self.root.after(0, lambda: self._mostrar_resultado_lexico(tokens, errores_lex))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_fallo_lexico(self, tokens, errores):
        """
        El lexer encontro errores pero siguio escaneando.
        Se muestran TODOS los tokens validos en la tabla + filas de error al final.
        La barra se detiene visualmente en Tokenizar (etapa 1).
        Las etapas Validar y Tabla quedan grises — no se ejecutaron.
        """
        self.tokens_actuales = tokens   # tokens validos disponibles
        self.errores_lexicos = errores

        # Llenar tabla con tokens validos
        for item in self.tabla.get_children():
            self.tabla.delete(item)

        for i, t in enumerate(tokens, 1):
            tag = self._tag(t.categoria, t.tipo)
            self.tabla.insert('', 'end',
                values=(i, t.valor, t.tipo, t.categoria, t.linea, t.columna),
                tags=(tag,))

        # Separador visual antes de los errores
        self.tabla.insert('', 'end',
            values=('', '─── Errores lexicos detectados ───', '', '', '', ''),
            tags=('warn',))

        # Filas de error en rojo
        for e in errores:
            self.tabla.insert('', 'end',
                values=('✗', e.get('caracter', '?'), 'ERROR_LEXICO',
                        'Error Lexico', e.get('linea', '?'), e.get('columna', '?')),
                tags=('err',))

        # Stats con tokens validos + errores
        resumen = self.lexer.obtener_resumen()
        self.panel_stats.actualizar({
            'tokens':     len(tokens),
            'palabras_r': resumen.get('Palabra Reservada', resumen.get('Reservada', 0)),
            'nums':       resumen.get('Numero', resumen.get('Entero', 0)),
            'ids':        resumen.get('Identificador', 0),
            'err_lex':    len(errores),
            'err_sin':    '—',
        })

        detalle = '%d token(s) validos, %d error(es) lexico(s):\n' % (len(tokens), len(errores))
        detalle += '\n'.join('  · Linea %s, Col %s: caracter no reconocido "%s"' % (
            e.get('linea', '?'), e.get('columna', '?'), e.get('caracter', '?')
        ) for e in errores)
        detalle += '\n\nCorrige los errores para poder ejecutar el analisis sintactico.'
        self._msg(detalle, 'err')
        self._set_estado('Error lexico', C['rojo'])
        self.btn_lex.config_state('normal')
        self.nb.select(0)

    def _mostrar_resultado_lexico(self, tokens, errores):
        """Actualiza la UI con el resultado del analisis lexico."""
        self.tokens_actuales = tokens
        self.errores_lexicos = errores

        # Llenar tabla
        for item in self.tabla.get_children():
            self.tabla.delete(item)

        for i, t in enumerate(tokens, 1):
            tag = self._tag(t.categoria, t.tipo)
            self.tabla.insert('', 'end',
                values=(i, t.valor, t.tipo, t.categoria, t.linea, t.columna),
                tags=(tag,))

        if errores:
            for e in errores:
                self.tabla.insert('', 'end',
                    values=('!', e['caracter'], 'ERROR_LEXICO', 'Error Lexico',
                            e['linea'], e['columna']),
                    tags=('err',))

        # Estadisticas animadas
        resumen = self.lexer.obtener_resumen()
        self.panel_stats.actualizar({
            'tokens':     len(tokens),
            'palabras_r': resumen.get('Palabra Reservada', resumen.get('Reservada', 0)),
            'nums':       resumen.get('Numero', resumen.get('Entero', 0)),
            'ids':        resumen.get('Identificador', 0),
            'err_lex':    len(errores),
            'err_sin':    '—',
        })

        self.etapas_lex.completar()

        if errores:
            self._msg('%d error(es) lexico(s) encontrados:\n' % len(errores) +
                      '\n'.join('  · ' + e['mensaje'] for e in errores), 'err')
            self._set_estado('Errores lexicos', C['rojo'])
        else:
            self._msg('Analisis lexico completado: %d tokens encontrados.' % len(tokens), 'ok')
            self._set_estado('Lexico OK', C['verde'])

        self.btn_lex.config_state('normal')
        self.nb.select(0)   # va al tab lexico

    # ── ANALISIS SINTACTICO (solo sintactico) ──────────────────────────────────

    def _hacer_sintactico(self):
        """Ejecuta SOLO el analisis sintactico (incluye re-tokenizar internamente)."""
        codigo = self.editor.get('1.0', 'end-1c')
        if not codigo.strip():
            self._msg('No hay codigo para analizar.', 'warn')
            return

        # Verificar errores lexicos antes de parsear
        _, errores_pre = self.lexer.analizar(codigo)
        if errores_pre:
            n = len(errores_pre)
            self.canvas.delete('all')
            self.canvas.create_text(400, 180,
                text='✗ No se puede generar el arbol AST',
                font=(FUENTE_UI[0], 14, 'bold'),
                fill=C['rojo'], justify='center')
            self.canvas.create_text(400, 230,
                text='Se encontraron %d error(es) lexico(s).\nCorrige el codigo fuente primero.' % n,
                font=(FUENTE_UI[0], 10),
                fill=C['naranja'], justify='center', width=500)

            for item in self.tabla_errores_sint.get_children():
                self.tabla_errores_sint.delete(item)
            self.tabla_errores_sint.insert('', 'end',
                values=('✗', 'Analisis bloqueado — corrige los errores lexicos primero'),
                tags=('err',))

            self._msg('Analisis sintactico bloqueado.\n'
                      'Hay %d error(es) lexico(s) sin corregir.' % n, 'err')
            self._set_estado('Error lexico', C['rojo'])
            self.nb.select(1)
            return

        self._set_estado('Generando arbol...', C['naranja'])
        self.btn_sin.config_state('disabled')
        self.root.update_idletasks()   # fuerza dimensiones del canvas antes de animar
        self._iniciar_progreso()
        self.etapas_sin.iniciar(modo='sintactico')

        def tarea():
            # ── Etapa 0: Tokens ───────────────────────────────────────────
            # (etapa_actual=0 desde iniciar)
            time.sleep(0.08)
            self.root.after(0, lambda: self._avanzar_progreso(0.20, 'Preparando tokens...'))

            # ── Etapa 1: Parsing ──────────────────────────────────────────
            self.root.after(0, lambda: self.etapas_sin.avanzar())   # → etapa 1
            self.root.after(0, lambda: self._avanzar_progreso(0.45, 'Analisis sintactico...'))
            tokens, _ = self.lexer.analizar(codigo)
            parser = AnalizadorSintactico(tokens.copy())
            raiz   = parser.analizar()
            errores_sint = parser.errores[:]
            time.sleep(0.06)

            # Si hay errores de parsing → fallo en etapa 1 (Parsing)
            if errores_sint:
                # Igual intentamos generar el AST parcial
                pass   # continuar — el AST parcial es informativo

            # ── Etapa 2: AST ──────────────────────────────────────────────
            self.root.after(0, lambda: self.etapas_sin.avanzar())   # → etapa 2
            self.root.after(0, lambda: self._avanzar_progreso(0.70, 'Generando AST...'))
            ruta_img = None
            fallo_ast = False
            try:
                ruta_base = os.path.join(self.dir_temp, 'arbol_ast')
                ruta_img  = self.gen_arbol.generar(raiz, ruta_base)
            except Exception as e:
                fallo_ast = True
                msg_e = str(e)
                if 'graphviz' in msg_e.lower() or 'dot' in msg_e.lower() or 'PATH' in msg_e:
                    errores_sint.append(
                        'GRAPHVIZ NO ENCONTRADO. '
                        'Reinstala desde graphviz.org/download y marca: '
                        'Add Graphviz to the system PATH for all users. '
                        'Luego cierra y reabre VS Code.')
                else:
                    errores_sint.append('Error al generar arbol: ' + msg_e)
            time.sleep(0.06)

            if fallo_ast:
                self.root.after(0, lambda: self.etapas_sin.fallar(2))
                self.root.after(0, lambda: self._mostrar_resultado_sintactico(
                    errores_sint, None, tokens))
                return

            # ── Etapa 3: Render ───────────────────────────────────────────
            self.root.after(0, lambda: self.etapas_sin.avanzar())   # → etapa 3
            self.root.after(0, lambda: self._avanzar_progreso(0.90, 'Renderizando...'))
            time.sleep(0.05)

            self.root.after(0, lambda: self._mostrar_resultado_sintactico(
                errores_sint, ruta_img, tokens))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_resultado_sintactico(self, errores_sint, ruta_img, tokens):
        """Actualiza la UI con el resultado del analisis sintactico."""
        self.errores_sintac    = errores_sint
        self.ruta_imagen_arbol = ruta_img

        # Actualizar stats con errores sintacticos
        self.panel_stats.actualizar({
            'tokens':     len(tokens),
            'err_sin':    len(errores_sint),
        })

        self.canvas.delete('all')

        for item in self.tabla_errores_sint.get_children():
            self.tabla_errores_sint.delete(item)

        if ruta_img and os.path.exists(ruta_img):
            self.img_original = Image.open(ruta_img)
            self.zoom_nivel   = 1.0
            self._render_arbol()

            if errores_sint:
                for i, e in enumerate(errores_sint, 1):
                    self.tabla_errores_sint.insert('', 'end',
                        values=(i, e), tags=('err',))
                self.tabla_errores_sint.insert('', 'end',
                    values=('⚠', 'El arbol generado es PARCIAL — no representa el programa correctamente'),
                    tags=('err',))
                self._msg('Se encontraron %d error(es) sintactico(s).\n'
                          'El arbol mostrado es parcial e invalido.' % len(errores_sint), 'err')
                self._set_estado('Errores sintacticos', C['rojo'])
                self.etapas_sin.fallar(1)   # fallo en Parsing — AST parcial visible
            else:
                self.tabla_errores_sint.insert('', 'end',
                    values=('✓', 'Sin errores sintacticos — arbol generado correctamente'),
                    tags=('ok',))
                self._msg('Arbol sintactico generado exitosamente.', 'ok')
                self._set_estado('Sintactico OK', C['verde'])
                self.etapas_sin.completar()
        else:
            self.canvas.create_text(400, 200,
                text='No se pudo generar el arbol.',
                font=(FUENTE_UI[0], 13), fill=C['rojo'], justify='center')
            if errores_sint:
                for i, e in enumerate(errores_sint, 1):
                    self.tabla_errores_sint.insert('', 'end',
                        values=(i, e), tags=('err',))
            self._set_estado('Error al generar', C['rojo'])
            self.etapas_sin.fallar(2)   # fallo en AST

        self.btn_sin.config_state('normal')
        self.nb.select(1)
        self._finalizar_progreso()

    # ── Tag de color ──────────────────────────────────────────────────────────

    def _tag(self, categoria, tipo):
        if 'Reservada'     in categoria: return 'pr'
        if 'Aritmetico'    in categoria: return 'op'
        if 'Comparacion'   in categoria: return 'op'
        if 'Asignacion'    in categoria: return 'op'
        if 'Compuesto'     in categoria: return 'op'
        if 'Entero'        in categoria: return 'num'
        if 'Flotante'      in categoria: return 'num'
        if 'Cadena'        in categoria: return 'str'
        if 'Identificador' in categoria: return 'id'
        if 'Comentario'    in categoria: return 'com'
        if 'Error'         in categoria: return 'err'
        return 'del'

    # ── Zoom y drag ──────────────────────────────────────────────────────────

    def _render_arbol(self):
        if not self.img_original:
            return
        w = int(self.img_original.width  * self.zoom_nivel)
        h = int(self.img_original.height * self.zoom_nivel)
        img = self.img_original.resize((w, h), Image.LANCZOS)
        self.imagen_tk = ImageTk.PhotoImage(img)
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, anchor='nw', image=self.imagen_tk)
        self.canvas.configure(scrollregion=(0, 0, w, h))
        self.lbl_zoom.config(text='Zoom: %d%%' % int(self.zoom_nivel * 100))

    def _zoom_in(self):
        if self.zoom_nivel < 4.0:
            self.zoom_nivel = min(4.0, round(self.zoom_nivel + 0.1, 2))
            self._render_arbol()

    def _zoom_out(self):
        if self.zoom_nivel > 0.2:
            self.zoom_nivel = max(0.2, round(self.zoom_nivel - 0.1, 2))
            self._render_arbol()

    def _zoom_reset(self):
        self.zoom_nivel = 1.0
        self._render_arbol()

    def _zoom_fit(self):
        if not self.img_original:
            return
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        iw, ih = self.img_original.size
        if iw > 0 and ih > 0:
            self.zoom_nivel = round(min(cw / iw, ch / ih) * 0.95, 2)
            self._render_arbol()

    def _on_wheel(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        zoom_anterior = self.zoom_nivel

        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            if self.zoom_nivel < 4.0:
                self.zoom_nivel = min(4.0, round(self.zoom_nivel + 0.1, 2))
        else:
            if self.zoom_nivel > 0.2:
                self.zoom_nivel = max(0.2, round(self.zoom_nivel - 0.1, 2))

        if self.zoom_nivel == zoom_anterior:
            return
        self._render_arbol()
        factor = self.zoom_nivel / zoom_anterior
        region = self.canvas.cget('scrollregion').split()
        if len(region) == 4:
            ancho = float(region[2])
            alto  = float(region[3])
            if ancho > 0:
                self.canvas.xview_moveto((cx * factor - event.x) / ancho)
            if alto > 0:
                self.canvas.yview_moveto((cy * factor - event.y) / alto)

    def _drag_inicio(self, event):
        self.canvas.config(cursor='fleur')
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_move(self, event):
        region = self.canvas.cget('scrollregion').split()
        if len(region) < 4:
            return
        ancho = float(region[2])
        alto  = float(region[3])
        dx = self._drag_x - event.x
        dy = self._drag_y - event.y
        if ancho > 0:
            self.canvas.xview_moveto(self.canvas.xview()[0] + dx / ancho)
        if alto > 0:
            self.canvas.yview_moveto(self.canvas.yview()[0] + dy / alto)
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_fin(self, event):
        self.canvas.config(cursor='arrow')

    # ── Ventana flotante del AST ──────────────────────────────────────────────

    def _abrir_arbol_ventana(self):
        if not self.img_original:
            self._msg('Primero genera el arbol sintactico.', 'warn')
            return

        win = tk.Toplevel(self.root)
        win.title('Arbol AST — Vista Completa')
        win.geometry('1000x700')
        win.configure(bg=C['bg_main'])

        tb = tk.Frame(win, bg=C['bg_panel'], height=40)
        tb.pack(fill='x', side='top')
        tb.pack_propagate(False)
        tk.Label(tb, text='Arbol de Sintaxis Abstracta',
                 font=FUENTE_UI, bg=C['bg_panel'], fg=C['texto_dim']
                 ).pack(side='left', padx=10, pady=8)
        lbl_zoom_win = tk.Label(tb, text='Zoom: 100%',
                                 font=FUENTE_UI, bg=C['bg_panel'], fg=C['texto_dim'])
        lbl_zoom_win.pack(side='right', padx=10)

        frame = tk.Frame(win, bg=C['bg_main'])
        frame.pack(fill='both', expand=True, padx=5, pady=5)
        sy = ttk.Scrollbar(frame, orient='vertical')
        sx = ttk.Scrollbar(frame, orient='horizontal')
        canvas_win = tk.Canvas(frame, bg=C['bg_editor'], highlightthickness=0,
                                yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.config(command=canvas_win.yview)
        sx.config(command=canvas_win.xview)
        sy.pack(side='right', fill='y')
        sx.pack(side='bottom', fill='x')
        canvas_win.pack(fill='both', expand=True)

        estado = {'zoom': 1.0, 'drag_x': 0, 'drag_y': 0, 'imagen_tk': None}

        def render(zoom=None):
            if zoom is not None:
                estado['zoom'] = zoom
            w = int(self.img_original.width  * estado['zoom'])
            h = int(self.img_original.height * estado['zoom'])
            img = self.img_original.resize((w, h), Image.LANCZOS)
            estado['imagen_tk'] = ImageTk.PhotoImage(img)
            canvas_win.delete('all')
            canvas_win.create_image(0, 0, anchor='nw', image=estado['imagen_tk'])
            canvas_win.configure(scrollregion=(0, 0, w, h))
            lbl_zoom_win.config(text='Zoom: %d%%' % int(estado['zoom'] * 100))

        def zoom_in():
            estado['zoom'] = min(4.0, round(estado['zoom'] + 0.1, 2)); render()

        def zoom_out():
            estado['zoom'] = max(0.2, round(estado['zoom'] - 0.1, 2)); render()

        def zoom_reset():
            render(zoom=1.0)

        def zoom_fit():
            cw = canvas_win.winfo_width()
            ch = canvas_win.winfo_height()
            iw, ih = self.img_original.size
            if iw > 0 and ih > 0:
                render(zoom=round(min(cw / iw, ch / ih) * 0.95, 2))

        def on_wheel(event):
            zoom_ant = estado['zoom']
            if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
                estado['zoom'] = min(4.0, round(estado['zoom'] + 0.1, 2))
            else:
                estado['zoom'] = max(0.2, round(estado['zoom'] - 0.1, 2))
            if estado['zoom'] == zoom_ant:
                return
            render()

        def drag_inicio(event):
            canvas_win.config(cursor='fleur')
            estado['drag_x'] = event.x
            estado['drag_y'] = event.y

        def drag_move(event):
            region = canvas_win.cget('scrollregion').split()
            if len(region) < 4:
                return
            ancho = float(region[2]); alto = float(region[3])
            dx = estado['drag_x'] - event.x
            dy = estado['drag_y'] - event.y
            if ancho > 0: canvas_win.xview_moveto(canvas_win.xview()[0] + dx / ancho)
            if alto  > 0: canvas_win.yview_moveto(canvas_win.yview()[0] + dy / alto)
            estado['drag_x'] = event.x
            estado['drag_y'] = event.y

        def drag_fin(event):
            canvas_win.config(cursor='arrow')

        for txt, cmd in [('Fit', zoom_fit), ('+', zoom_in),
                          ('-', zoom_out), ('100%', zoom_reset)]:
            tk.Button(tb, text=txt, command=cmd, font=(FUENTE_MONO[0], 9),
                      bg=C['borde'], fg=C['texto'], relief='flat',
                      cursor='hand2', padx=8, pady=3, bd=0
                      ).pack(side='right', padx=2, pady=6)

        canvas_win.bind('<MouseWheel>',      on_wheel)
        canvas_win.bind('<Button-4>',        on_wheel)
        canvas_win.bind('<Button-5>',        on_wheel)
        canvas_win.bind('<ButtonPress-1>',   drag_inicio)
        canvas_win.bind('<B1-Motion>',       drag_move)
        canvas_win.bind('<ButtonRelease-1>', drag_fin)
        win.after(100, zoom_fit)

    # ── Exportacion PDF ───────────────────────────────────────────────────────

    def _pdf_lexico(self):
        if not self.tokens_actuales:
            self._msg('Primero ejecuta el analisis lexico.', 'warn')
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension='.pdf', filetypes=[('PDF', '*.pdf')],
            initialfile='analisis_lexico.pdf', title='Guardar lexico como PDF')
        if ruta:
            try:
                self.exportador.exportar_lexico(
                    self.tokens_actuales, self.errores_lexicos,
                    self.editor.get('1.0', 'end-1c'), ruta)
                self._msg('PDF guardado: ' + ruta, 'ok')
                messagebox.showinfo('Exito', 'PDF guardado:\n' + ruta)
            except Exception as e:
                self._msg('Error al exportar: ' + str(e), 'err')

    def _pdf_sintactico(self):
        if not self.ruta_imagen_arbol:
            self._msg('Primero genera el arbol sintactico.', 'warn')
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension='.pdf', filetypes=[('PDF', '*.pdf')],
            initialfile='analisis_sintactico.pdf', title='Guardar sintactico como PDF')
        if ruta:
            try:
                self.exportador.exportar_sintactico(
                    self.ruta_imagen_arbol,
                    self.editor.get('1.0', 'end-1c'),
                    self.errores_sintac, ruta)
                self._msg('PDF guardado: ' + ruta, 'ok')
                messagebox.showinfo('Exito', 'PDF guardado:\n' + ruta)
            except Exception as e:
                self._msg('Error al exportar: ' + str(e), 'err')

    def _pdf_completo(self):
        if not self.tokens_actuales:
            self._msg('Primero ejecuta al menos el analisis lexico.', 'warn')
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension='.pdf', filetypes=[('PDF', '*.pdf')],
            initialfile='analisis_completo.pdf', title='Guardar analisis completo como PDF')
        if ruta:
            try:
                self.exportador.exportar_completo(
                    self.tokens_actuales, self.errores_lexicos,
                    self.editor.get('1.0', 'end-1c'),
                    self.ruta_imagen_arbol, self.errores_sintac, ruta)
                self._msg('PDF guardado: ' + ruta, 'ok')
                messagebox.showinfo('Exito', 'PDF guardado:\n' + ruta)
            except Exception as e:
                self._msg('Error al exportar: ' + str(e), 'err')

    # ── Utilidades ────────────────────────────────────────────────────────────

    # ── Tab Semantico ─────────────────────────────────────────────────────────

    def _crear_tab_semantico(self, padre):
        """Crea el tab con tabla de simbolos y tabla de errores semanticos."""

        # ── Encabezado ────────────────────────────────────────────────────────
        cabecera = tk.Frame(padre, bg=C['bg_panel'])
        cabecera.pack(fill='x', padx=6, pady=(6, 2))
        tk.Label(cabecera,
                 text='◉ Tabla de Simbolos',
                 font=(FUENTE_UI[0], 11, 'bold'),
                 bg=C['bg_panel'], fg=C['morado']).pack(side='left', padx=4)

        sep = tk.Frame(padre, bg=C['borde'], height=1)
        sep.pack(fill='x', padx=6, pady=(0, 4))

        # --- PANEL DE ERRORES AL FONDO (Ahora se empaqueta ANTES que la tabla principal) ---
        frame_err_sem = tk.Frame(padre, bg=C['bg_panel'])
        frame_err_sem.pack(side='bottom', fill='x', padx=6, pady=(4, 6))

        tk.Label(frame_err_sem,
                 text='Errores Semanticos',
                 font=(FUENTE_UI[0], 9, 'bold'),
                 bg=C['bg_panel'], fg=C['rojo']).pack(anchor='w', padx=8, pady=(6, 2))

        cols_esem = ('n', 'categoria', 'variable', 'descripcion')
        # ---> TABLA DE ERRORES SEMÁNTICOS CON ALTURA DE 10 <---
        self.tabla_errores_sem = ttk.Treeview(
            frame_err_sem, columns=cols_esem, show='headings',
            style='Tok.Treeview', height=10)

        self.tabla_errores_sem.heading('n',           text='#',          anchor='center')
        self.tabla_errores_sem.heading('categoria',   text='Categoria',  anchor='w')
        self.tabla_errores_sem.heading('variable',    text='Variable',   anchor='w')
        self.tabla_errores_sem.heading('descripcion', text='Descripcion', anchor='w')

        self.tabla_errores_sem.column('n',           width=35,  minwidth=30,  anchor='center')
        self.tabla_errores_sem.column('categoria',   width=180, minwidth=100, anchor='w')
        self.tabla_errores_sem.column('variable',    width=130, minwidth=60,  anchor='w')
        self.tabla_errores_sem.column('descripcion', width=480, minwidth=100, anchor='w')

        self.tabla_errores_sem.tag_configure('err', background='#3A1010', foreground=C['rojo'])
        self.tabla_errores_sem.tag_configure('ok',  background='#0A2A0A', foreground=C['verde'])

        sy_esem = ttk.Scrollbar(frame_err_sem, orient='vertical', command=self.tabla_errores_sem.yview)
        self.tabla_errores_sem.configure(yscrollcommand=sy_esem.set)
        sy_esem.pack(side='right', fill='y')
        self.tabla_errores_sem.pack(fill='x', padx=5, pady=(0, 6))

        self.tabla_errores_sem.insert('', 'end',
            values=('—', '—', '—', 'Presiona "Analizar Semantico" para ver resultados'),
            tags=('ok',))

        # --- TABLA DE SIMBOLOS EN EL MEDIO (Ahora limitada en altura para no acaparar espacio) ---
        frame_sim = tk.Frame(padre, bg=C['bg_main'])
        frame_sim.pack(side='top', fill='both', expand=True, padx=6, pady=(0, 4))

        cols_sim = ('nombre', 'tipo', 'categoria', 'alcance', 'linea')
        # ---> TABLA PRINCIPAL MÁS PEQUEÑA (height=8) <---
        self.tabla_simbolos = ttk.Treeview(
            frame_sim, columns=cols_sim, show='headings',
            style='Tok.Treeview', selectmode='browse', height=8)

        encabezados_sim = {
            'nombre':    ('Nombre',    180, 'w'),
            'tipo':      ('Tipo',      100, 'center'),
            'categoria': ('Categoria', 110, 'center'),
            'alcance':   ('Alcance',   120, 'center'),
            'linea':     ('Linea',      60, 'center'),
        }
        for col, (texto, ancho, ancla) in encabezados_sim.items():
            self.tabla_simbolos.heading(col, text=texto,
                                        anchor='center' if ancla == 'center' else 'w')
            self.tabla_simbolos.column(col, width=ancho, minwidth=40, anchor=ancla)

        # Colores por categoria
        self.tabla_simbolos.tag_configure('variable',  foreground='#89DCEB')
        self.tabla_simbolos.tag_configure('funcion',   foreground='#A6E3A1')
        self.tabla_simbolos.tag_configure('parametro', foreground='#FAB387')
        self.tabla_simbolos.tag_configure('placeholder', foreground=C['texto_dim'])

        sy_sim = ttk.Scrollbar(frame_sim, orient='vertical',   command=self.tabla_simbolos.yview)
        sx_sim = ttk.Scrollbar(frame_sim, orient='horizontal', command=self.tabla_simbolos.xview)
        self.tabla_simbolos.configure(yscrollcommand=sy_sim.set, xscrollcommand=sx_sim.set)
        sy_sim.pack(side='right', fill='y')
        sx_sim.pack(side='bottom', fill='x')
        self.tabla_simbolos.pack(fill='both', expand=True)

        self.tabla_simbolos.insert('', 'end',
            values=('—', '—', 'Presiona "Analizar Semantico" para ver la tabla', '—', '—'),
            tags=('placeholder',))

    # ── ANALISIS SEMANTICO ─────────────────────────────────────────────────────

    def _hacer_semantico(self):
        """
        Ejecuta el analisis semantico sobre el AST.
        Requiere que el codigo no tenga errores lexicos.
        El parser se ejecuta internamente para obtener el AST fresco.
        """
        codigo = self.editor.get('1.0', 'end-1c')
        if not codigo.strip():
            self._msg('No hay codigo para analizar.', 'warn')
            return

        # Bloquear si hay errores lexicos
        _, errores_pre = self.lexer.analizar(codigo)
        if errores_pre:
            self._msg('Analisis semantico bloqueado.\n'
                      'Corrige los %d error(es) lexico(s) primero.' % len(errores_pre), 'err')
            self._set_estado('Error lexico', C['rojo'])
            return

        self._set_estado('Analisis semantico...', C['morado'])
        self.btn_sem.config_state('disabled')
        self._limpiar_mensajes()

        def tarea():
            # Tokenizar y parsear para obtener el AST
            tokens, _ = self.lexer.analizar(codigo)
            parser    = AnalizadorSintactico(tokens.copy())
            raiz      = parser.analizar()

            # Ejecutar analizador semantico
            errores_sem, tabla_sim = self.analizador_sem.analizar(raiz)

            self.errores_semanticos = errores_sem
            self.root.after(0, lambda: self._mostrar_resultado_semantico(
                errores_sem, tabla_sim))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_resultado_semantico(self, errores_sem, tabla_sim):
        """Actualiza el tab semantico con los resultados del analisis."""

        # ── Tabla de simbolos ─────────────────────────────────────────────────
        for item in self.tabla_simbolos.get_children():
            self.tabla_simbolos.delete(item)

        filas = tabla_sim.exportar_tabla()
        if filas:
            for fila in filas:
                tag = fila['categoria'] if fila['categoria'] in ('variable', 'funcion', 'parametro') else 'variable'
                self.tabla_simbolos.insert('', 'end',
                    values=(fila['nombre'], fila['tipo'],
                            fila['categoria'], fila['alcance'], fila['linea']),
                    tags=(tag,))
        else:
            self.tabla_simbolos.insert('', 'end',
                values=('—', '—', 'No se encontraron simbolos', '—', '—'),
                tags=('placeholder',))

        # ── Tabla de errores semanticos ───────────────────────────────────────
        for item in self.tabla_errores_sem.get_children():
            self.tabla_errores_sem.delete(item)

        if errores_sem:
            for i, e in enumerate(errores_sem, 1):
                self.tabla_errores_sem.insert('', 'end',
                    values=(i,
                            e.categoria,
                            e.variable if e.variable else '—',
                            e.mensaje),
                    tags=('err',))
            self._msg('Analisis semantico: %d error(es) encontrado(s).' % len(errores_sem), 'err')
            self._set_estado('Errores semanticos', C['rojo'])
        else:
            self.tabla_errores_sem.insert('', 'end',
                values=('✓', '—', '—', 'Sin errores semanticos — programa correcto'),
                tags=('ok',))
            self._msg('Analisis semantico completado: %d simbolo(s), sin errores.' % len(filas), 'ok')
            self._set_estado('Semantico OK', C['verde'])

        self.btn_sem.config_state('normal')
        self.nb.select(2)   # ir al tab semantico

    # ── PDF Semantico ─────────────────────────────────────────────────────────

    def _pdf_semantico(self):
        tabla_filas = self.analizador_sem.tabla.exportar_tabla()
        if not tabla_filas and not self.errores_semanticos:
            self._msg('Primero ejecuta el analisis semantico.', 'warn')
            return
        ruta = filedialog.asksaveasfilename(
            defaultextension='.pdf', filetypes=[('PDF', '*.pdf')],
            initialfile='analisis_semantico.pdf', title='Guardar semantico como PDF')
        if ruta:
            try:
                self.exportador.exportar_semantico(
                    tabla_filas,
                    self.errores_semanticos,
                    self.editor.get('1.0', 'end-1c'),
                    ruta)
                self._msg('PDF guardado: ' + ruta, 'ok')
                messagebox.showinfo('Exito', 'PDF guardado:\n' + ruta)
            except Exception as e:
                self._msg('Error al exportar: ' + str(e), 'err')

    def _limpiar(self):
        if messagebox.askyesno('Limpiar', 'Limpiar todo el editor y los resultados?'):
            self.editor.delete('1.0', 'end')
            for item in self.tabla.get_children():
                self.tabla.delete(item)
            self.tabla.insert('', 'end',
                values=('—', 'Presiona "Analizar Lexico" para ver los tokens',
                        '', '', '', ''), tags=('del',))
            self.canvas.delete('all')
            self.canvas.create_text(400, 200,
                text='Presiona "Analizar Sintactico"\npara ver el arbol AST aqui',
                font=(FUENTE_UI[0], 13), fill=C['texto_dim'], justify='center')
            for item in self.tabla_errores_sint.get_children():
                self.tabla_errores_sint.delete(item)
            self.tabla_errores_sint.insert('', 'end',
                values=('—', 'Presiona "Analizar Sintactico" para ver resultados'),
                tags=('ok',))
            self.tokens_actuales    = []
            self.errores_lexicos    = []
            self.errores_sintac     = []
            self.errores_semanticos = []
            self.ruta_imagen_arbol  = None
            self.img_original       = None
            self.etapas_lex.resetear()
            self.etapas_sin.resetear()

            # Limpiar tab semantico
            for item in self.tabla_simbolos.get_children():
                self.tabla_simbolos.delete(item)
            self.tabla_simbolos.insert('', 'end',
                values=('—', '—', 'Presiona "Analizar Semantico" para ver la tabla', '—', '—'),
                tags=('placeholder',))
            for item in self.tabla_errores_sem.get_children():
                self.tabla_errores_sem.delete(item)
            self.tabla_errores_sem.insert('', 'end',
                values=('—', '—', '—', 'Presiona "Analizar Semantico" para ver resultados'),
                tags=('ok',))

            self.panel_stats.actualizar({
                'tokens': 0, 'palabras_r': 0,
                'nums': 0, 'ids': 0, 'err_lex': 0, 'err_sin': '—'
            })
            self._limpiar_mensajes()
            self._set_estado('Listo', C['verde'])
            self._actualizar_lineas()
            self._reset_progreso()

    def _limpiar_mensajes(self):
        self.txt_msg.config(state='normal')
        self.txt_msg.delete('1.0', 'end')
        self.txt_msg.config(state='disabled')

    def _msg(self, texto, tipo='info'):
        self.txt_msg.config(state='normal')
        self.txt_msg.delete('1.0', 'end')
        self.txt_msg.insert('end', texto, tipo)
        self.txt_msg.config(state='disabled')

    def _set_estado(self, texto, color):
        self.lbl_estado.config(text='● ' + texto, fg=color)