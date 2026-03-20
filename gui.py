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

from PIL import Image, ImageTk
from lexer import AnalizadorLexico
from parser_ast import AnalizadorSintactico, GeneradorArbol
from pdf_exporter import ExportadorPDF


# ─── Paleta de colores ────────────────────────────────────────────────────────
C = {
    'bg_main':    '#1E1E2E',
    'bg_panel':   '#2A2A3E',
    'bg_editor':  '#282828',
    'bg_tabla':   '#1A1A2A',
    'azul':       '#89B4FA',
    'verde':      '#A6E3A1',
    'rojo':       '#F38BA8',
    'naranja':    '#FAB387',
    'texto':      '#CDD6F4',
    'texto_dim':  '#6C7086',
    'borde':      '#45475A',
    'fila_par':   '#252538',
    'header_tab': '#313244',
}

FUENTE_CODIGO = ('Consolas', 11) if sys.platform == 'win32' else ('Courier', 11)
FUENTE_UI     = ('Segoe UI', 10) if sys.platform == 'win32' else ('Helvetica', 10)
FUENTE_TITULO = ('Segoe UI', 14, 'bold') if sys.platform == 'win32' else ('Helvetica', 14, 'bold')

CODIGO_EJEMPLO = """// Ejemplo de codigo para el analizador
inicial = 10
velocidad = 5
posicion = inicial + velocidad * 60

if (posicion > 100) {
    posicion = 0
    velocidad = velocidad + 1
}

while (inicial < 50) {
    inicial += 5
    posicion = inicial + velocidad * 60
}

def calcular(x, y) {
    return x + y * 2
}

resultado = calcular(inicial, velocidad)
print(resultado)
"""


class AplicacionCompilador:
    """Ventana principal de la aplicacion."""

    def __init__(self, root):
        self.root = root
        self.root.title("Analizador Lexico y Sintactico - Compiladores")
        self.root.geometry("1300x800")
        self.root.configure(bg=C['bg_main'])
        self.root.minsize(900, 600)

        # Estado del analisis
        self.tokens_actuales   = []
        self.errores_lexicos   = []
        self.errores_sintac    = []
        self.ruta_imagen_arbol = None
        # Estado del visor de imagen
        self.imagen_tk         = None
        self.img_original      = None
        # Estado del zoom y arrastre
        self.zoom_nivel        = 1.0
        self._drag_x = 0
        self._drag_y = 0
        self.dir_temp = tempfile.mkdtemp()

        # Estado de la barra de progreso
        self._prog_valor    = 0.0
        self._prog_destino  = 0.0
        self._prog_animando = False
        self._prog_color    = C['azul']
        self._prog_shimmer  = 0

        # Modulos del compilador
        self.lexer     = AnalizadorLexico()
        self.gen_arbol = GeneradorArbol()
        self.exportador = ExportadorPDF()

        self._conf_estilos()
        self._crear_barra()
        self._crear_contenido()

        self.editor.insert('1.0', CODIGO_EJEMPLO)
        self._actualizar_lineas()
        self._resaltar_sintaxis()

    # ── Estilos TTK ──────────────────────────────────────────────────────────

    def _conf_estilos(self):
        s = ttk.Style()
        s.theme_use('clam')
        s.configure('App.TNotebook', background=C['bg_main'], borderwidth=0)
        s.configure('App.TNotebook.Tab',
            background=C['bg_main'], foreground=C['texto_dim'],
            padding=[15, 8], font=FUENTE_UI, borderwidth=0)
        s.map('App.TNotebook.Tab',
            background=[('selected', C['header_tab'])],
            foreground=[('selected', C['azul'])])
        s.configure('Tok.Treeview',
            background=C['bg_tabla'], foreground=C['texto'],
            fieldbackground=C['bg_tabla'], rowheight=24, font=FUENTE_UI)
        s.configure('Tok.Treeview.Heading',
            background=C['header_tab'], foreground=C['azul'],
            font=(FUENTE_UI[0], FUENTE_UI[1], 'bold'), relief='flat')
        s.map('Tok.Treeview',
            background=[('selected', C['azul'])],
            foreground=[('selected', C['bg_main'])])

    # ── Barra superior ────────────────────────────────────────────────────────

    def _crear_barra(self):
        barra = tk.Frame(self.root, bg=C['bg_panel'], height=60)
        barra.pack(fill='x', side='top')
        barra.pack_propagate(False)
        tk.Label(barra, text='Analizador Lexico y Sintactico',
                 font=FUENTE_TITULO, bg=C['bg_panel'], fg=C['azul']
                 ).pack(side='left', padx=20, pady=10)
        self.lbl_estado = tk.Label(barra, text='Listo',
            font=FUENTE_UI, bg=C['bg_panel'], fg=C['verde'])
        self.lbl_estado.pack(side='right', padx=20)
        tk.Label(barra, text='Compiladores - Analisis Lexico & Sintactico',
                 font=FUENTE_UI, bg=C['bg_panel'], fg=C['texto_dim']
                 ).pack(side='right', padx=10)

    # ── Layout principal ──────────────────────────────────────────────────────

    def _crear_contenido(self):
        panel = tk.Frame(self.root, bg=C['bg_main'])
        panel.pack(fill='both', expand=True, padx=10, pady=10)

        izq = tk.Frame(panel, bg=C['bg_panel'], width=580)
        izq.pack(side='left', fill='both', padx=(0, 5))
        izq.pack_propagate(False)
        self._crear_editor(izq)

        der = tk.Frame(panel, bg=C['bg_main'])
        der.pack(side='right', fill='both', expand=True)
        self._crear_resultados(der)

    # ── Editor de codigo ──────────────────────────────────────────────────────

    def _crear_editor(self, padre):
        tk.Label(padre, text='Editor de Codigo', font=(FUENTE_UI[0], 12),
                 bg=C['bg_panel'], fg=C['texto']).pack(anchor='w', padx=10, pady=(8, 0))

        frame = tk.Frame(padre, bg=C['bg_editor'])
        frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.canvas_nums = tk.Canvas(frame, width=40, bg=C['bg_panel'],
                                      highlightthickness=0)
        self.canvas_nums.pack(side='left', fill='y')

        scroll = ttk.Scrollbar(frame)
        scroll.pack(side='right', fill='y')

        self.editor = tk.Text(
            frame, wrap='none', font=FUENTE_CODIGO,
            bg=C['bg_editor'], fg=C['texto'],
            insertbackground=C['azul'],
            selectbackground=C['azul'], selectforeground=C['bg_main'],
            relief='flat', bd=0, padx=10, pady=5, undo=True,
            yscrollcommand=scroll.set
        )
        self.editor.pack(side='left', fill='both', expand=True)
        scroll.config(command=self.editor.yview)

        for evento in ('<KeyRelease>', '<MouseWheel>', '<Button-1>'):
            self.editor.bind(evento, self._actualizar_lineas)
        self.editor.bind('<KeyPress>',   self._resaltar_sintaxis)
        self.editor.bind('<KeyRelease>', self._resaltar_sintaxis)

        # Tags de color del editor
        self.editor.tag_config('pr',  foreground='#A6E3A1')
        self.editor.tag_config('op',  foreground='#FAB387')
        self.editor.tag_config('num', foreground='#CBA6F7')
        self.editor.tag_config('id',  foreground='#89DCEB')
        self.editor.tag_config('str', foreground='#F38BA8')
        self.editor.tag_config('com', foreground='#6C7086')
        self.editor.tag_config('del', foreground='#CDD6F4')

        self._crear_botones(padre)

        frame_msg = tk.Frame(padre, bg=C['bg_panel'])
        frame_msg.pack(fill='x', padx=5, pady=(0, 5))
        self.txt_msg = tk.Text(frame_msg, height=5, font=(FUENTE_CODIGO[0], 9),
                                bg=C['bg_main'], fg=C['texto'], relief='flat',
                                state='disabled', wrap='word')
        self.txt_msg.pack(fill='x', padx=3, pady=3)
        self.txt_msg.tag_config('ok',   foreground=C['verde'])
        self.txt_msg.tag_config('err',  foreground=C['rojo'])
        self.txt_msg.tag_config('info', foreground=C['azul'])
        self.txt_msg.tag_config('warn', foreground=C['naranja'])

    def _crear_botones(self, padre):
        fila1 = tk.Frame(padre, bg=C['bg_panel'])
        fila1.pack(fill='x', padx=5, pady=3)

        def btn(parent, texto, cmd, bg, fg=C['bg_main'], lado='left'):
            b = tk.Button(parent, text=texto, command=cmd, font=FUENTE_UI,
                          bg=bg, fg=fg, activebackground=C['borde'],
                          relief='flat', cursor='hand2', padx=12, pady=6, bd=0)
            b.pack(side=lado, padx=3)
            return b

        self.btn_lex = btn(fila1, 'Analizar Lexico',     self._hacer_lexico,     C['azul'])
        self.btn_sin = btn(fila1, 'Analizar Sintactico',  self._hacer_sintactico, C['verde'])
        btn(fila1, 'Limpiar', self._limpiar, C['bg_main'], C['texto_dim'], 'right')

        fila2 = tk.Frame(padre, bg=C['bg_panel'])
        fila2.pack(fill='x', padx=5, pady=(0, 5))
        btn(fila2, 'Exportar Lexico PDF',     self._pdf_lexico,     C['borde'], C['texto'])
        btn(fila2, 'Exportar Sintactico PDF', self._pdf_sintactico,  C['borde'], C['texto'])
        btn(fila2, 'Exportar Completo PDF',   self._pdf_completo,    C['naranja'])

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
                    34, info[1] + 2, text=str(i),
                    font=(FUENTE_CODIGO[0], FUENTE_CODIGO[1] - 1),
                    fill=C['texto_dim'], anchor='ne'
                )

    # ── Resaltado de sintaxis en tiempo real ─────────────────────────────────

    def _resaltar_sintaxis(self, event=None):
        for tag in ('pr', 'op', 'num', 'id', 'str', 'com', 'del'):
            self.editor.tag_remove(tag, '1.0', 'end')

        codigo = self.editor.get('1.0', 'end-1c')
        if not codigo.strip():
            for item in self.tabla.get_children():
                self.tabla.delete(item)
            self.lbl_stats.config(
                text='Ejecuta el analisis lexico para ver los tokens',
                fg=C['texto_dim'])
            return

        tokens, _ = self.lexer.analizar(codigo)

        for token in tokens:
            inicio = '%d.%d' % (token.linea, token.columna - 1)
            fin    = '%d.%d' % (token.linea, token.columna - 1 + len(token.valor))
            tag = self._tag(token.categoria, token.tipo)
            self.editor.tag_add(tag, inicio, fin)

        for item in self.tabla.get_children():
            self.tabla.delete(item)

        for i, t in enumerate(tokens, 1):
            tag = self._tag(t.categoria, t.tipo)
            self.tabla.insert('', 'end',
                values=(i, t.valor, t.tipo, t.categoria, t.linea, t.columna),
                tags=(tag,))

        resumen = self.lexer.obtener_resumen()
        txt = '%d tokens  |  ' % len(tokens)
        txt += '  '.join('%s: %d' % (k, v) for k, v in list(resumen.items())[:4])
        self.lbl_stats.config(text=txt, fg=C['azul'])

    # ── Panel de resultados ───────────────────────────────────────────────────

    def _crear_resultados(self, padre):
        self.nb = ttk.Notebook(padre, style='App.TNotebook')
        self.nb.pack(fill='both', expand=True)

        tab_lex = tk.Frame(self.nb, bg=C['bg_main'])
        self.nb.add(tab_lex, text='  Analisis Lexico  ')
        self._crear_tabla(tab_lex)

        tab_sin = tk.Frame(self.nb, bg=C['bg_main'])
        self.nb.add(tab_sin, text='  Analisis Sintactico  ')
        self._crear_visor_arbol(tab_sin)

    def _crear_tabla(self, padre):
        self.frame_stats = tk.Frame(padre, bg=C['bg_panel'], height=40)
        self.frame_stats.pack(fill='x', padx=5, pady=5)
        self.frame_stats.pack_propagate(False)
        self.lbl_stats = tk.Label(self.frame_stats,
            text='Ejecuta el analisis lexico para ver los tokens',
            font=FUENTE_UI, bg=C['bg_panel'], fg=C['texto_dim'])
        self.lbl_stats.pack(side='left', padx=10, pady=8)

        frame = tk.Frame(padre, bg=C['bg_main'])
        frame.pack(fill='both', expand=True, padx=5, pady=5)

        cols = ('#', 'valor', 'tipo', 'categoria', 'linea', 'col')
        self.tabla = ttk.Treeview(frame, columns=cols, show='headings',
                                   style='Tok.Treeview', selectmode='browse')

        encabezados = {
            '#':         ('#',            45,  'center'),
            'valor':     ('Token (Valor)', 140, 'w'),
            'tipo':      ('Tipo Interno',  180, 'w'),
            'categoria': ('Categoria',     160, 'w'),
            'linea':     ('Linea',         60,  'center'),
            'col':       ('Col.',          50,  'center'),
        }
        for col, (texto, ancho, ancla) in encabezados.items():
            self.tabla.heading(col, text=texto, anchor='center' if ancla == 'center' else 'w')
            self.tabla.column(col, width=ancho, minwidth=40, anchor=ancla)

        sy = ttk.Scrollbar(frame, orient='vertical',   command=self.tabla.yview)
        sx = ttk.Scrollbar(frame, orient='horizontal',  command=self.tabla.xview)
        self.tabla.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.pack(side='right', fill='y')
        sx.pack(side='bottom', fill='x')
        self.tabla.pack(fill='both', expand=True)

        self.tabla.tag_configure('pr',  background='#2A3A2A', foreground='#A6E3A1')
        self.tabla.tag_configure('op',  background='#3A3A2A', foreground='#FAB387')
        self.tabla.tag_configure('num', background='#2A2A3A', foreground='#CBA6F7')
        self.tabla.tag_configure('id',  background=C['bg_tabla'], foreground='#89DCEB')
        self.tabla.tag_configure('str', background='#3A2A2A', foreground='#F38BA8')
        self.tabla.tag_configure('del', background=C['fila_par'], foreground=C['texto_dim'])
        self.tabla.tag_configure('com', background='#2A3A2A', foreground='#6C7086')
        self.tabla.tag_configure('err', background='#4A1A1A', foreground=C['rojo'])

    def _crear_visor_arbol(self, padre):
        # Barra de herramientas
        tb = tk.Frame(padre, bg=C['bg_panel'], height=40)
        tb.pack(fill='x', padx=5, pady=5)
        tb.pack_propagate(False)
        tk.Label(tb, text='Arbol de Sintaxis Abstracta (AST)',
                 font=FUENTE_UI, bg=C['bg_panel'], fg=C['texto_dim']
                 ).pack(side='left', padx=10, pady=8)

        self.lbl_zoom = tk.Label(tb, text='Zoom: 100%', font=FUENTE_UI,
                                  bg=C['bg_panel'], fg=C['texto_dim'])
        self.lbl_zoom.pack(side='right', padx=5)

        for txt, cmd in [('Abrir', self._abrir_arbol_ventana),
                         ('Fit',   self._zoom_fit),
                         ('+',     self._zoom_in),
                         ('-',     self._zoom_out),
                         ('100%',  self._zoom_reset)]:
            tk.Button(tb, text=txt, command=cmd, font=('Consolas', 9),
                      bg=C['borde'], fg=C['texto'], relief='flat',
                      cursor='hand2', padx=8, pady=3, bd=0
                      ).pack(side='right', padx=2, pady=6)

        # Canvas con scrollbars
        frame = tk.Frame(padre, bg=C['bg_main'])
        frame.pack(fill='both', expand=True, padx=5, pady=5)
        sy = ttk.Scrollbar(frame, orient='vertical')
        sx = ttk.Scrollbar(frame, orient='horizontal')
        self.canvas = tk.Canvas(frame, bg=C['bg_editor'], highlightthickness=0,
                                 yscrollcommand=sy.set, xscrollcommand=sx.set)
        sy.config(command=self.canvas.yview)
        sx.config(command=self.canvas.xview)
        sy.pack(side='right', fill='y')
        sx.pack(side='bottom', fill='x')
        self.canvas.pack(fill='both', expand=True)

        self.canvas.create_text(400, 300,
            text='Ejecuta el Analisis Sintactico\npara ver el arbol AST aqui',
            font=(FUENTE_UI[0], 12), fill=C['texto_dim'], justify='center',
            tags='msg_inicial')

        # Eventos de zoom y drag
        self.canvas.bind('<MouseWheel>',      self._on_wheel)
        self.canvas.bind('<Button-4>',        self._on_wheel)
        self.canvas.bind('<Button-5>',        self._on_wheel)
        self.canvas.bind('<ButtonPress-1>',   self._drag_inicio)
        self.canvas.bind('<B1-Motion>',       self._drag_move)
        self.canvas.bind('<ButtonRelease-1>', self._drag_fin)

        # Barra de progreso estilo juego
        self._crear_barra_progreso(padre)

        # Tabla de errores sintacticos
        frame_err = tk.Frame(padre, bg=C['bg_panel'])
        frame_err.pack(fill='x', padx=5, pady=(0, 5))

        tk.Label(frame_err, text='Errores Sintacticos',
                 font=FUENTE_UI, bg=C['bg_panel'], fg=C['rojo']
                 ).pack(anchor='w', padx=10, pady=(6, 2))

        cols_err = ('n', 'descripcion')
        self.tabla_errores_sint = ttk.Treeview(
            frame_err, columns=cols_err, show='headings',
            style='Tok.Treeview', height=4)
        self.tabla_errores_sint.heading('n',           text='#',          anchor='center')
        self.tabla_errores_sint.heading('descripcion', text='Descripcion', anchor='w')
        self.tabla_errores_sint.column('n',            width=35,  minwidth=30,  anchor='center')
        self.tabla_errores_sint.column('descripcion',  width=600, minwidth=100, anchor='w')
        self.tabla_errores_sint.tag_configure('err', background='#4A1A1A', foreground=C['rojo'])
        self.tabla_errores_sint.tag_configure('ok',  background='#1A3A1A', foreground=C['verde'])
        self.tabla_errores_sint.pack(fill='x', padx=5, pady=(0, 5))

    # ── Barra de progreso estilo juego ────────────────────────────────────────

    def _crear_barra_progreso(self, padre):
        """Crea la barra de carga estilo RPG con Canvas."""
        frame_prog = tk.Frame(padre, bg=C['bg_panel'])
        frame_prog.pack(fill='x', padx=5, pady=(2, 2))

        # Fila de etiquetas: texto izquierda, porcentaje derecha
        fila = tk.Frame(frame_prog, bg=C['bg_panel'])
        fila.pack(fill='x', padx=8, pady=(4, 2))

        self.lbl_prog_texto = tk.Label(fila, text='Listo',
            font=(FUENTE_UI[0], 8), bg=C['bg_panel'], fg=C['texto_dim'])
        self.lbl_prog_texto.pack(side='left')

        self.lbl_prog_pct = tk.Label(fila, text='',
            font=(FUENTE_UI[0], 8, 'bold'), bg=C['bg_panel'], fg=C['naranja'])
        self.lbl_prog_pct.pack(side='right')

        # Canvas de la barra
        self.canvas_prog = tk.Canvas(frame_prog, height=18,
                                      bg='#0D0D1A',
                                      highlightthickness=1,
                                      highlightbackground=C['borde'])
        self.canvas_prog.pack(fill='x', padx=8, pady=(0, 6))
        self.canvas_prog.bind('<Configure>', lambda e: self._dibujar_barra())

    def _color_barra(self):
        """Retorna el color según el progreso actual."""
        v = self._prog_valor
        if v < 0.35:
            return '#89B4FA'   # azul
        elif v < 0.70:
            return '#FAB387'   # naranja
        else:
            return '#A6E3A1'   # verde

    def _ajustar_color(self, hex_color, delta):
        """Aclara (delta>0) u oscurece (delta<0) un color hex."""
        r = max(0, min(255, int(hex_color[1:3], 16) + delta))
        g = max(0, min(255, int(hex_color[3:5], 16) + delta))
        b = max(0, min(255, int(hex_color[5:7], 16) + delta))
        return '#%02x%02x%02x' % (r, g, b)

    def _dibujar_barra(self):
        """Dibuja la barra con efecto de volumen y shimmer."""
        c = self.canvas_prog
        c.delete('all')
        W = c.winfo_width()
        H = c.winfo_height()
        if W <= 1 or H <= 1:
            return

        # Fondo
        c.create_rectangle(0, 0, W, H, fill='#0D0D1A', outline='')

        fill_w = int(W * self._prog_valor)

        if fill_w > 2:
            color = self._color_barra()

            # Relleno principal
            c.create_rectangle(0, 0, fill_w, H, fill=color, outline='')

            # Highlight superior (brillo)
            c.create_rectangle(0, 0, fill_w, max(1, H // 3),
                                fill=self._ajustar_color(color, 70), outline='')

            # Sombra inferior
            c.create_rectangle(0, H - max(1, H // 4), fill_w, H,
                                fill=self._ajustar_color(color, -50), outline='')

            # Shimmer — franja brillante que viaja
            if self._prog_animando:
                sx = int((self._prog_shimmer % (W + 60)) - 30)
                x0 = max(0, min(sx,      fill_w))
                x1 = max(0, min(sx + 20, fill_w))
                if x1 > x0:
                    c.create_rectangle(x0, 0, x1, H,
                                       fill=self._ajustar_color(color, 100),
                                       outline='', stipple='gray50')

            # Destello en el borde derecho
            bx = max(0, fill_w - 3)
            c.create_rectangle(bx, 0, fill_w, H,
                                fill=self._ajustar_color(color, 120),
                                outline='', stipple='gray25')

        # Marcas cada 25%
        for pct in (0.25, 0.50, 0.75):
            x = int(W * pct)
            c.create_line(x, 1, x, H - 1, fill='#1A1A2E', width=1)

        # Borde exterior
        c.create_rectangle(0, 0, W - 1, H - 1, outline=C['borde'], fill='')

    def _animar_barra(self):
        """Loop de animacion ~60fps con interpolacion suave."""
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
        """Arranca la barra desde cero."""
        self._prog_valor    = 0.0
        self._prog_destino  = 0.0
        self._prog_animando = True
        self._prog_shimmer  = 0
        self.lbl_prog_texto.config(text='Analizando...', fg=C['azul'])
        self.lbl_prog_pct.config(text='0%', fg=C['naranja'])
        self._animar_barra()

    def _avanzar_progreso(self, destino, texto=None):
        """Mueve el destino de la barra (0.0 a 1.0)."""
        self._prog_destino = max(0.0, min(1.0, destino))
        if texto:
            self.lbl_prog_texto.config(text=texto, fg=C['azul'])

    def _finalizar_progreso(self):
        """Lleva la barra al 100% y luego la resetea."""
        self._prog_destino = 1.0
        self.lbl_prog_texto.config(text='Completado', fg=C['verde'])
        self.root.after(800, self._reset_progreso)

    def _reset_progreso(self):
        """Resetea la barra silenciosamente."""
        self._prog_animando = False
        self._prog_valor    = 0.0
        self._prog_destino  = 0.0
        self.lbl_prog_texto.config(text='Listo', fg=C['texto_dim'])
        self.lbl_prog_pct.config(text='')
        self._dibujar_barra()

    # ── Logica de analisis ────────────────────────────────────────────────────

    def _hacer_lexico(self):
        codigo = self.editor.get('1.0', 'end-1c')
        if not codigo.strip():
            self._msg('No hay codigo para analizar.', 'warn')
            return
        self._set_estado('Analizando...', C['naranja'])
        self.btn_lex.config(state='disabled')
        self._limpiar_mensajes()

        def tarea():
            tokens, errores = self.lexer.analizar(codigo)
            self.root.after(0, lambda: self._mostrar_lexico(tokens, errores))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_lexico(self, tokens, errores):
        self.tokens_actuales = tokens
        self.errores_lexicos = errores

        for item in self.tabla.get_children():
            self.tabla.delete(item)

        for i, t in enumerate(tokens, 1):
            tag = self._tag(t.categoria, t.tipo)
            self.tabla.insert('', 'end',
                values=(i, t.valor, t.tipo, t.categoria, t.linea, t.columna),
                tags=(tag,))

        resumen = self.lexer.obtener_resumen()
        txt = '%d tokens  |  %d errores  |  ' % (len(tokens), len(errores))
        txt += '  '.join('%s: %d' % (k, v) for k, v in list(resumen.items())[:4])
        self.lbl_stats.config(text=txt, fg=C['verde'])

        if errores:
            msg = '%d error(es) lexico(s):\n' % len(errores)
            msg += '\n'.join('  - ' + e['mensaje'] for e in errores)
            self._msg(msg, 'err')
        else:
            self._msg('Analisis lexico completado: %d tokens encontrados.' % len(tokens), 'ok')

        self.nb.select(0)
        self._set_estado('Lexico completado', C['verde'])
        self.btn_lex.config(state='normal')

    def _tag(self, categoria, tipo):
        if 'Reservada'    in categoria: return 'pr'
        if 'Aritmetico'   in categoria: return 'op'
        if 'Comparacion'  in categoria: return 'op'
        if 'Asignacion'   in categoria: return 'op'
        if 'Compuesto'    in categoria: return 'op'
        if 'Entero'       in categoria: return 'num'
        if 'Flotante'     in categoria: return 'num'
        if 'Cadena'       in categoria: return 'str'
        if 'Identificador' in categoria: return 'id'
        if 'Comentario'   in categoria: return 'com'
        if 'Error'        in categoria: return 'err'
        return 'del'

    def _hacer_sintactico(self):
        codigo = self.editor.get('1.0', 'end-1c')
        if not codigo.strip():
            self._msg('No hay codigo para analizar.', 'warn')
            return
        self._set_estado('Generando arbol...', C['naranja'])
        self.btn_sin.config(state='disabled')
        self._iniciar_progreso()

        def tarea():
            # 25% — tokenizacion
            self.root.after(0, lambda: self._avanzar_progreso(0.25, 'Tokenizando...'))
            tokens, errores_lex = self.lexer.analizar(codigo)

            # 50% — parsing
            self.root.after(0, lambda: self._avanzar_progreso(0.50, 'Parseando...'))
            parser = AnalizadorSintactico(tokens.copy())
            raiz = parser.analizar()
            errores_sint = parser.errores[:]

            # 75% — generando AST
            self.root.after(0, lambda: self._avanzar_progreso(0.75, 'Generando AST...'))
            ruta_img = None
            try:
                ruta_base = os.path.join(self.dir_temp, 'arbol_ast')
                ruta_img = self.gen_arbol.generar(raiz, ruta_base)
            except Exception as e:
                msg_e = str(e)
                if 'graphviz' in msg_e.lower() or 'dot' in msg_e.lower() or 'PATH' in msg_e:
                    errores_sint.append(
                        'GRAPHVIZ NO ENCONTRADO. '
                        'Reinstala graphviz desde graphviz.org/download y marca: '
                        'Add Graphviz to the system PATH for all users. '
                        'Luego cierra y reabre VS Code.'
                    )
                else:
                    errores_sint.append('Error al generar arbol: ' + msg_e)

            # 100% — render
            self.root.after(0, lambda: self._avanzar_progreso(1.0, 'Renderizando...'))
            self.root.after(0, lambda: self._mostrar_sintactico(
                errores_sint, ruta_img, tokens, errores_lex))

        threading.Thread(target=tarea, daemon=True).start()

    def _mostrar_sintactico(self, errores_sint, ruta_img, tokens, errores_lex):
        self.errores_sintac    = errores_sint
        self.ruta_imagen_arbol = ruta_img

        self._mostrar_lexico(tokens, errores_lex)

        self.canvas.delete('all')

        for item in self.tabla_errores_sint.get_children():
            self.tabla_errores_sint.delete(item)

        if ruta_img and os.path.exists(ruta_img):
            self.img_original = Image.open(ruta_img)
            self.zoom_nivel = 1.0
            self._render_arbol()

        if errores_sint:
            for i, e in enumerate(errores_sint, 1):
                self.tabla_errores_sint.insert('', 'end',
                    values=(i, e), tags=('err',))
            self._msg('%d error(es) sintactico(s) encontrado(s).' % len(errores_sint), 'err')
        else:
            self.tabla_errores_sint.insert('', 'end',
                values=('✓', 'Sin errores sintacticos'), tags=('ok',))
            self._msg('Arbol sintactico generado exitosamente.', 'ok')

        self.nb.select(1)
        self._set_estado('Listo', C['verde'])
        self.btn_sin.config(state='normal')
        self._finalizar_progreso()

    # ── Zoom del arbol (panel principal) ─────────────────────────────────────

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

    # ── Ventana flotante del arbol ────────────────────────────────────────────

    def _abrir_arbol_ventana(self):
        if not self.img_original:
            self._msg('Primero genera el arbol sintactico.', 'warn')
            return

        win = tk.Toplevel(self.root)
        win.title('Arbol AST - Vista Completa')
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
            estado['zoom'] = min(4.0, round(estado['zoom'] + 0.1, 2))
            render()

        def zoom_out():
            estado['zoom'] = max(0.2, round(estado['zoom'] - 0.1, 2))
            render()

        def zoom_reset():
            render(zoom=1.0)

        def zoom_fit():
            cw = canvas_win.winfo_width()
            ch = canvas_win.winfo_height()
            iw, ih = self.img_original.size
            if iw > 0 and ih > 0:
                render(zoom=round(min(cw / iw, ch / ih) * 0.95, 2))

        def on_wheel(event):
            cx = canvas_win.canvasx(event.x)
            cy = canvas_win.canvasy(event.y)
            zoom_ant = estado['zoom']
            if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
                estado['zoom'] = min(4.0, round(estado['zoom'] + 0.1, 2))
            else:
                estado['zoom'] = max(0.2, round(estado['zoom'] - 0.1, 2))
            if estado['zoom'] == zoom_ant:
                return
            render()
            factor = estado['zoom'] / zoom_ant
            region = canvas_win.cget('scrollregion').split()
            if len(region) == 4:
                ancho = float(region[2])
                alto  = float(region[3])
                if ancho > 0:
                    canvas_win.xview_moveto((cx * factor - event.x) / ancho)
                if alto > 0:
                    canvas_win.yview_moveto((cy * factor - event.y) / alto)

        def drag_inicio(event):
            canvas_win.config(cursor='fleur')
            estado['drag_x'] = event.x
            estado['drag_y'] = event.y

        def drag_move(event):
            region = canvas_win.cget('scrollregion').split()
            if len(region) < 4:
                return
            ancho = float(region[2])
            alto  = float(region[3])
            dx = estado['drag_x'] - event.x
            dy = estado['drag_y'] - event.y
            if ancho > 0:
                canvas_win.xview_moveto(canvas_win.xview()[0] + dx / ancho)
            if alto > 0:
                canvas_win.yview_moveto(canvas_win.yview()[0] + dy / alto)
            estado['drag_x'] = event.x
            estado['drag_y'] = event.y

        def drag_fin(event):
            canvas_win.config(cursor='arrow')

        for txt, cmd in [('Fit', zoom_fit), ('+', zoom_in),
                          ('-', zoom_out), ('100%', zoom_reset)]:
            tk.Button(tb, text=txt, command=cmd, font=('Consolas', 9),
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

    # ── Zoom y drag del panel principal ──────────────────────────────────────

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
        nueva_cx = cx * factor
        nueva_cy = cy * factor
        region = self.canvas.cget('scrollregion').split()
        if len(region) == 4:
            ancho_total = float(region[2])
            alto_total  = float(region[3])
            if ancho_total > 0:
                self.canvas.xview_moveto((nueva_cx - event.x) / ancho_total)
            if alto_total > 0:
                self.canvas.yview_moveto((nueva_cy - event.y) / alto_total)

    def _drag_inicio(self, event):
        self.canvas.config(cursor='fleur')
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_move(self, event):
        region = self.canvas.cget('scrollregion').split()
        if len(region) < 4:
            return
        ancho_total = float(region[2])
        alto_total  = float(region[3])
        dx = self._drag_x - event.x
        dy = self._drag_y - event.y
        if ancho_total > 0:
            self.canvas.xview_moveto(self.canvas.xview()[0] + dx / ancho_total)
        if alto_total > 0:
            self.canvas.yview_moveto(self.canvas.yview()[0] + dy / alto_total)
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_fin(self, event):
        self.canvas.config(cursor='arrow')

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

    def _limpiar(self):
        if messagebox.askyesno('Limpiar', 'Limpiar todo el editor y los resultados?'):
            self.editor.delete('1.0', 'end')
            for item in self.tabla.get_children():
                self.tabla.delete(item)
            self.canvas.delete('all')
            self.canvas.create_text(400, 300,
                text='Ejecuta el Analisis Sintactico\npara ver el arbol AST aqui',
                font=(FUENTE_UI[0], 12), fill=C['texto_dim'], justify='center')
            self.tokens_actuales   = []
            self.errores_lexicos   = []
            self.errores_sintac    = []
            self.ruta_imagen_arbol = None
            self.img_original      = None
            self.lbl_stats.config(
                text='Ejecuta el analisis lexico para ver los tokens',
                fg=C['texto_dim'])
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
        self.lbl_estado.config(text=texto, fg=color)