"""
lexer.py - Analizador Lexico
Divide el codigo fuente Python en tokens y detecta errores lexicos.
Soporta unicamente: Python 3
"""

import re

# ─── Definicion de tokens ─────────────────────────────────────────────────────
# REGLA DE ORO: los patrones MAS LARGOS y ESPECIFICOS siempre primero.

TOKEN_DEFINICIONES = [

    # ── 1. Comentarios ───────────────────────────────────────────────────────
    ('COMENTARIO',          r'#[^\n]*'),

    # ── 2. Strings (triple comilla ANTES que simple) ──────────────────────────
    ('CADENA_TRIPLE_DOBLE', r'"""[\s\S]*?"""'),
    ('CADENA_TRIPLE_SIMPLE',r"'''[\s\S]*?'''"),
    ('CADENA_DOBLE',        r'"[^"\\]*(?:\\.[^"\\]*)*"'),
    ('CADENA_SIMPLE',       r"'[^'\\]*(?:\\.[^'\\]*)*'"),

    # ── 3. Numeros (especificos primero) ──────────────────────────────────────
    ('NUMERO_CIENTIFICO',   r'\b\d+(\.\d+)?[eE][+-]?\d+\b'),
    ('NUMERO_HEX',          r'\b0[xX][0-9A-Fa-f]+\b'),
    ('NUMERO_OCTAL',        r'\b0[oO][0-7]+\b'),
    ('NUMERO_BINARIO',      r'\b0[bB][01]+\b'),
    ('NUMERO_FLOAT',        r'\b\d+\.\d+\b'),
    ('NUMERO_INT',          r'\b\d+\b'),

    # ── 4. Palabras reservadas Python 3 (antes que IDENTIFICADOR) ─────────────
    ('PR_FALSE',    r'\bFalse\b'),
    ('PR_NONE',     r'\bNone\b'),
    ('PR_TRUE',     r'\bTrue\b'),
    ('PR_AND',      r'\band\b'),
    ('PR_AS',       r'\bas\b'),
    ('PR_ASSERT',   r'\bassert\b'),
    ('PR_ASYNC',    r'\basync\b'),
    ('PR_AWAIT',    r'\bawait\b'),
    ('PR_BREAK',    r'\bbreak\b'),
    ('PR_CLASS',    r'\bclass\b'),
    ('PR_CONTINUE', r'\bcontinue\b'),
    ('PR_DEF',      r'\bdef\b'),
    ('PR_DEL',      r'\bdel\b'),
    ('PR_ELIF',     r'\belif\b'),
    ('PR_ELSE',     r'\belse\b'),
    ('PR_EXCEPT',   r'\bexcept\b'),
    ('PR_FINALLY',  r'\bfinally\b'),
    ('PR_FOR',      r'\bfor\b'),
    ('PR_FROM',     r'\bfrom\b'),
    ('PR_GLOBAL',   r'\bglobal\b'),
    ('PR_IF',       r'\bif\b'),
    ('PR_IMPORT',   r'\bimport\b'),
    ('PR_IN',       r'\bin\b'),
    ('PR_IS',       r'\bis\b'),
    ('PR_LAMBDA',   r'\blambda\b'),
    ('PR_NONLOCAL', r'\bnonlocal\b'),
    ('PR_NOT',      r'\bnot\b'),
    ('PR_OR',       r'\bor\b'),
    ('PR_PASS',     r'\bpass\b'),
    ('PR_RAISE',    r'\braise\b'),
    ('PR_RETURN',   r'\breturn\b'),
    ('PR_TRY',      r'\btry\b'),
    ('PR_WHILE',    r'\bwhile\b'),
    ('PR_WITH',     r'\bwith\b'),
    ('PR_YIELD',    r'\byield\b'),
    # Builtins comunes
    ('PR_PRINT',    r'\bprint\b'),
    ('PR_INPUT',    r'\binput\b'),
    ('PR_LEN',      r'\blen\b'),
    ('PR_RANGE',    r'\brange\b'),
    ('PR_TYPE',     r'\btype\b'),
    ('PR_INT_BT',   r'\bint\b'),
    ('PR_FLOAT_BT', r'\bfloat\b'),
    ('PR_STR_BT',   r'\bstr\b'),
    ('PR_LIST',     r'\blist\b'),
    ('PR_DICT',     r'\bdict\b'),
    ('PR_SET',      r'\bset\b'),
    ('PR_TUPLE',    r'\btuple\b'),
    ('PR_BOOL_BT',  r'\bbool\b'),

    # ── 5. Identificadores ────────────────────────────────────────────────────
    ('IDENTIFICADOR', r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'),

    # ── 6. Operadores (mas largos primero) ────────────────────────────────────
    # 3 caracteres
    ('OP_DESPLAZ_IZQ_IGUAL', r'<<='),
    ('OP_DESPLAZ_DER_IGUAL', r'>>='),
    ('OP_POTENCIA_IGUAL',    r'\*\*='),
    ('OP_DIV_ENTERA_IGUAL',  r'//='),
    # 2 caracteres
    ('OP_POTENCIA',     r'\*\*'),
    ('OP_DIV_ENTERA',   r'//'),
    ('OP_DESPLAZ_IZQ',  r'<<'),
    ('OP_DESPLAZ_DER',  r'>>'),
    ('OP_IGUAL_IGUAL',  r'=='),
    ('OP_DIFERENTE',    r'!='),
    ('OP_MAYOR_IGUAL',  r'>='),
    ('OP_MENOR_IGUAL',  r'<='),
    ('OP_WALRUS',       r':='),
    ('OP_MAS_IGUAL',    r'\+='),
    ('OP_MENOS_IGUAL',  r'-='),
    ('OP_MULT_IGUAL',   r'\*='),
    ('OP_DIV_IGUAL',    r'/='),
    ('OP_MOD_IGUAL',    r'%='),
    ('OP_AND_IGUAL',    r'&='),
    ('OP_OR_IGUAL',     r'\|='),
    ('OP_XOR_IGUAL',    r'\^='),
    ('OP_FLECHA',       r'->'),
    # 1 caracter
    ('OP_ASIGNACION',   r'='),
    ('OP_MAS',          r'\+'),
    ('OP_MENOS',        r'-'),
    ('OP_MULT',         r'\*'),
    ('OP_DIV',          r'/'),
    ('OP_MODULO',       r'%'),
    ('OP_MAYOR',        r'>'),
    ('OP_MENOR',        r'<'),
    ('OP_AND_BIT',      r'&'),
    ('OP_OR_BIT',       r'\|'),
    ('OP_XOR',          r'\^'),
    ('OP_NEGACION_BIT', r'~'),
    ('OP_ARROBA',       r'@'),

    # ── 7. Delimitadores ──────────────────────────────────────────────────────
    ('PUNTOS_SUSPENS',  r'\.\.\.'),
    ('PAREN_ABRE',      r'\('),   ('PAREN_CIERRA',  r'\)'),
    ('LLAVE_ABRE',      r'\{'),   ('LLAVE_CIERRA',  r'\}'),
    ('CORCHETE_ABRE',   r'\['),   ('CORCHETE_CIERRA',r'\]'),
    ('PUNTO_COMA',      r';'),    ('DOS_PUNTOS',     r':'),
    ('COMA',            r','),    ('PUNTO',          r'\.'),

    # ── 8. Espacios y saltos de linea ─────────────────────────────────────────
    ('NUEVA_LINEA',     r'\n'),
    ('ESPACIO',         r'[ \t\r]+'),
]

PATRON_MAESTRO = re.compile(
    '|'.join('(?P<%s>%s)' % (n, p) for n, p in TOKEN_DEFINICIONES)
)


# ─── Categoria legible ────────────────────────────────────────────────────────

def _cat(tipo):
    """Retorna la categoria legible de un tipo de token."""
    if tipo.startswith('PR_'):
        return 'Palabra Reservada'
    if tipo in ('NUMERO_INT', 'NUMERO_FLOAT'):
        return 'Numero'
    if tipo == 'NUMERO_HEX':
        return 'Numero Hexadecimal'
    if tipo == 'NUMERO_OCTAL':
        return 'Numero Octal'
    if tipo == 'NUMERO_BINARIO':
        return 'Numero Binario'
    if tipo == 'NUMERO_CIENTIFICO':
        return 'Numero Cientifico'
    if tipo == 'IDENTIFICADOR':
        return 'Identificador'
    if tipo in ('CADENA_DOBLE', 'CADENA_SIMPLE',
                'CADENA_TRIPLE_DOBLE', 'CADENA_TRIPLE_SIMPLE'):
        return 'Cadena de Texto'
    if tipo == 'COMENTARIO':
        return 'Comentario'
    if tipo in ('OP_ASIGNACION', 'OP_WALRUS'):
        return 'Operador Asignacion'
    if tipo in ('OP_IGUAL_IGUAL', 'OP_DIFERENTE', 'OP_MAYOR',
                'OP_MENOR', 'OP_MAYOR_IGUAL', 'OP_MENOR_IGUAL'):
        return 'Operador Comparacion'
    if tipo in ('OP_MAS', 'OP_MENOS', 'OP_MULT', 'OP_DIV',
                'OP_MODULO', 'OP_POTENCIA', 'OP_DIV_ENTERA', 'OP_ARROBA'):
        return 'Operador Aritmetico'
    if tipo in ('OP_MAS_IGUAL', 'OP_MENOS_IGUAL', 'OP_MULT_IGUAL',
                'OP_DIV_IGUAL', 'OP_MOD_IGUAL', 'OP_POTENCIA_IGUAL',
                'OP_DIV_ENTERA_IGUAL'):
        return 'Operador Compuesto'
    if tipo in ('OP_AND_BIT', 'OP_OR_BIT', 'OP_XOR', 'OP_NEGACION_BIT',
                'OP_DESPLAZ_IZQ', 'OP_DESPLAZ_DER',
                'OP_DESPLAZ_IZQ_IGUAL', 'OP_DESPLAZ_DER_IGUAL',
                'OP_AND_IGUAL', 'OP_OR_IGUAL', 'OP_XOR_IGUAL'):
        return 'Operador Bit a Bit'
    if tipo == 'OP_FLECHA':
        return 'Anotacion de Tipo'
    if tipo in ('PAREN_ABRE', 'PAREN_CIERRA', 'LLAVE_ABRE', 'LLAVE_CIERRA',
                'CORCHETE_ABRE', 'CORCHETE_CIERRA', 'PUNTO_COMA',
                'DOS_PUNTOS', 'COMA', 'PUNTO', 'PUNTOS_SUSPENS'):
        return 'Delimitador'
    if tipo == 'ERROR':
        return 'Error Lexico'
    return tipo


# ─── Token ────────────────────────────────────────────────────────────────────

class Token:
    """Un token individual del codigo fuente."""

    def __init__(self, tipo, valor, linea, columna):
        self.tipo      = tipo
        self.valor     = valor
        self.linea     = linea
        self.columna   = columna
        self.categoria = _cat(tipo)

    def __repr__(self):
        return 'Token(%s, %r, L%d:C%d)' % (
            self.tipo, self.valor, self.linea, self.columna)


# ─── Analizador Lexico ────────────────────────────────────────────────────────

class AnalizadorLexico:
    """
    Analizador Lexico principal.
    Recorre el codigo fuente Python y produce una lista de Token.
    """

    def __init__(self):
        self.tokens  = []
        self.errores = []
        self.codigo  = ''

    def analizar(self, codigo):
        """
        Analiza el codigo fuente y retorna (tokens, errores).

        Parametros:
            codigo : str — codigo Python a analizar
        Retorna:
            (list[Token], list[dict])
        """
        self.tokens  = []
        self.errores = []
        self.codigo  = codigo

        linea_actual = 1
        inicio_linea = 0

        for coincidencia in PATRON_MAESTRO.finditer(codigo):
            tipo    = coincidencia.lastgroup
            valor   = coincidencia.group()
            inicio  = coincidencia.start()
            columna = inicio - inicio_linea + 1

            if tipo == 'NUEVA_LINEA':
                linea_actual += 1
                inicio_linea = coincidencia.end()
                continue

            if tipo == 'ESPACIO':
                continue

            self.tokens.append(Token(tipo, valor, linea_actual, columna))

        # ── Detectar caracteres no reconocidos ────────────────────────────────
        posiciones_cubiertas = set()
        for m in PATRON_MAESTRO.finditer(codigo):
            posiciones_cubiertas.update(range(m.start(), m.end()))

        linea_err        = 1
        inicio_linea_err = 0
        for i, char in enumerate(codigo):
            if char == '\n':
                linea_err += 1
                inicio_linea_err = i + 1
                continue
            if i not in posiciones_cubiertas and not char.isspace():
                col_err = i - inicio_linea_err + 1
                self.errores.append({
                    'caracter': char,
                    'linea':    linea_err,
                    'columna':  col_err,
                    'mensaje':  "Caracter no reconocido '%s' en linea %d, columna %d"
                                % (char, linea_err, col_err)
                })

        return self.tokens, self.errores

    def obtener_resumen(self):
        """Retorna un diccionario con conteo de tokens por categoria."""
        resumen = {}
        for token in self.tokens:
            cat = token.categoria
            resumen[cat] = resumen.get(cat, 0) + 1
        return resumen


# ─── Buffer de Entrada (Doble Centinela) ─────────────────────────────────────

class BufferEntrada:
    """
    Buffer de doble centinela para lectura caracter a caracter.
    Implementa el mecanismo clasico de compiladores:

        [ bloque A  \\0 ][ bloque B  \\0 ]

    El puntero 'adelante' avanza leyendo caracteres. Al tocar un
    centinela (\\0) recarga la mitad contraria automaticamente.
    'inicio' marca el comienzo del lexema actual.
    """
    TAM = 64   # caracteres por mitad del buffer

    def __init__(self, texto):
        self._texto     = texto
        self._pos_texto = 0
        self._buf       = ['\0'] * (self.TAM * 2 + 2)
        self.inicio     = 0
        self.adelante   = 0
        self._cargar_mitad(0)
        self._cargar_mitad(1)

    def _cargar_mitad(self, mitad):
        """Carga TAM caracteres en la mitad indicada (0 o 1)."""
        base = mitad * (self.TAM + 1)
        for i in range(self.TAM):
            if self._pos_texto < len(self._texto):
                self._buf[base + i] = self._texto[self._pos_texto]
                self._pos_texto += 1
            else:
                self._buf[base + i] = '\0'
        self._buf[base + self.TAM] = '\0'

    def siguiente(self):
        """
        Lee y avanza el puntero 'adelante'.
        Si toca centinela recarga la mitad contraria.
        Retorna '\\0' al llegar al fin del texto.
        """
        char = self._buf[self.adelante]

        if char == '\0':
            if self.adelante == self.TAM:
                self._cargar_mitad(0)
                self.adelante = 0
            elif self.adelante == self.TAM * 2 + 1:
                self._cargar_mitad(1)
                self.adelante = self.TAM + 1
            else:
                return '\0'
            char = self._buf[self.adelante]

        self.adelante += 1
        return char

    def retroceder(self):
        """Devuelve el puntero adelante un caracter."""
        if self.adelante > 0:
            self.adelante -= 1

    def lexema_actual(self):
        """Retorna el string acumulado entre inicio y adelante."""
        resultado = []
        i = self.inicio
        while i != self.adelante:
            resultado.append(self._buf[i % len(self._buf)])
            i += 1
        return ''.join(resultado)

    def aceptar(self):
        """Confirma el lexema: mueve inicio hasta adelante."""
        self.inicio = self.adelante

    def reiniciar(self, texto):
        """Reinicia el buffer con un nuevo texto fuente."""
        self.__init__(texto)
