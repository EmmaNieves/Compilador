"""
lexer.py - Analizador Lexico
Divide el codigo fuente en tokens y detecta errores lexicos.
Soporta: Python, C, C++, Java, JavaScript y ensamblador basico.
"""

import re

# ─── Definicion de tokens ─────────────────────────────────────────────────────
# REGLA DE ORO: los patrones MAS LARGOS y ESPECIFICOS siempre primero.
# Si ++ va despues de +, el regex captura dos + por separado. Jamas al reves.

TOKEN_DEFINICIONES = [

    # ── 1. Comentarios (antes que operadores / y #) ───────────────────────────
    ('COMENTARIO_BLOQUE',   r'/\*[\s\S]*?\*/'),       # /* bloque */
    ('COMENTARIO_LINEA',    r'//[^\n]*'),              # // linea C/C++/Java
    ('COMENTARIO_PYTHON',   r'#[^\n]*'),               # # linea Python

    # ── 2. Strings (antes que cualquier otro simbolo) ─────────────────────────
    # Triple-comilla ANTES que comilla simple, para que """ no se parta en 3 "
    ('CADENA_TRIPLE_DOBLE', r'"""[\s\S]*?"""'),        # """multilinea"""
    ('CADENA_TRIPLE_SIMPLE',r"'''[\s\S]*?'''"),        # '''multilinea'''
    ('CADENA',              r'"[^"\\]*(?:\\.[^"\\]*)*"'),   # "normal"
    ('CADENA_SIMPLE',       r"'[^'\\]*(?:\\.[^'\\]*)*'"),   # 'normal'

    # ── 3. Numeros (especificos primero) ──────────────────────────────────────
    # Notacion cientifica: 1e10, 2.5e-3, 3E+8  (antes que float e int simples)
    ('NUMERO_CIENTIFICO',   r'\b\d+(\.\d+)?[eE][+-]?\d+\b'),
    # Hexadecimal C/Java: 0xFF, 0XA3
    ('NUMERO_HEX',          r'\b0[xX][0-9A-Fa-f]+\b'),
    # Hexadecimal ensamblador: 21H, 0FFH
    ('NUMERO_HEX_ASM',      r'\b[0-9][0-9A-Fa-f]*[Hh]\b'),
    # Octal: 0o77 (Python)
    ('NUMERO_OCTAL',        r'\b0[oO][0-7]+\b'),
    # Binario: 0b1010 (Python/C++)
    ('NUMERO_BINARIO',      r'\b0[bB][01]+\b'),
    # Float normal: 3.14  (antes que int para capturar el punto)
    ('NUMERO_FLOAT',        r'\b\d+\.\d+\b'),
    # Entero normal: 42
    ('NUMERO_INT',          r'\b\d+\b'),

    # ── 4. Palabras reservadas (antes que IDENTIFICADOR) ──────────────────────
    # Python
    ('PR_IF',       r'\bif\b'),       ('PR_ELSE',     r'\belse\b'),
    ('PR_ELIF',     r'\belif\b'),     ('PR_WHILE',    r'\bwhile\b'),
    ('PR_FOR',      r'\bfor\b'),      ('PR_RETURN',   r'\breturn\b'),
    ('PR_DEF',      r'\bdef\b'),      ('PR_CLASS',    r'\bclass\b'),
    ('PR_IMPORT',   r'\bimport\b'),   ('PR_FROM',     r'\bfrom\b'),
    ('PR_AS',       r'\bas\b'),       ('PR_WITH',     r'\bwith\b'),
    ('PR_TRY',      r'\btry\b'),      ('PR_EXCEPT',   r'\bexcept\b'),
    ('PR_FINALLY',  r'\bfinally\b'),  ('PR_RAISE',    r'\braise\b'),
    ('PR_LAMBDA',   r'\blambda\b'),   ('PR_YIELD',    r'\byield\b'),
    ('PR_ASYNC',    r'\basync\b'),    ('PR_AWAIT',    r'\bawait\b'),
    ('PR_AND',      r'\band\b'),      ('PR_OR',       r'\bor\b'),
    ('PR_NOT',      r'\bnot\b'),      ('PR_IN',       r'\bin\b'),
    ('PR_IS',       r'\bis\b'),       ('PR_PASS',     r'\bpass\b'),
    ('PR_BREAK',    r'\bbreak\b'),    ('PR_CONTINUE', r'\bcontinue\b'),
    ('PR_NONE',     r'\bNone\b'),     ('PR_TRUE',     r'\bTrue\b'),
    ('PR_FALSE',    r'\bFalse\b'),    ('PR_PRINT',    r'\bprint\b'),
    ('PR_INPUT',    r'\binput\b'),    ('PR_DEL',      r'\bdel\b'),
    ('PR_GLOBAL',   r'\bglobal\b'),   ('PR_NONLOCAL', r'\bnonlocal\b'),
    # C / C++ / Java / JS
    ('PR_INT',      r'\bint\b'),      ('PR_FLOAT_KW', r'\bfloat\b'),
    ('PR_DOUBLE',   r'\bdouble\b'),   ('PR_CHAR',     r'\bchar\b'),
    ('PR_LONG',     r'\blong\b'),     ('PR_SHORT',    r'\bshort\b'),
    ('PR_UNSIGNED', r'\bunsigned\b'), ('PR_SIGNED',   r'\bsigned\b'),
    ('PR_VOID',     r'\bvoid\b'),     ('PR_BOOL',     r'\bbool\b'),
    ('PR_STRING',   r'\bstring\b'),   ('PR_VAR',      r'\bvar\b'),
    ('PR_LET',      r'\blet\b'),      ('PR_CONST',    r'\bconst\b'),
    ('PR_STATIC',   r'\bstatic\b'),   ('PR_PUBLIC',   r'\bpublic\b'),
    ('PR_PRIVATE',  r'\bprivate\b'),  ('PR_PROTECTED',r'\bprotected\b'),
    ('PR_NEW',      r'\bnew\b'),      ('PR_DELETE',   r'\bdelete\b'),
    ('PR_THIS',     r'\bthis\b'),     ('PR_SUPER',    r'\bsuper\b'),
    ('PR_EXTENDS',  r'\bextends\b'),  ('PR_IMPLEMENTS',r'\bimplements\b'),
    ('PR_INTERFACE',r'\binterface\b'),('PR_ENUM',     r'\benum\b'),
    ('PR_SWITCH',   r'\bswitch\b'),   ('PR_CASE',     r'\bcase\b'),
    ('PR_DEFAULT',  r'\bdefault\b'),  ('PR_DO',       r'\bdo\b'),
    ('PR_GOTO',     r'\bgoto\b'),     ('PR_SIZEOF',   r'\bsizeof\b'),
    ('PR_TYPEDEF',  r'\btypedef\b'),  ('PR_STRUCT',   r'\bstruct\b'),
    ('PR_UNION',    r'\bunion\b'),     ('PR_EXTERN',   r'\bextern\b'),
    ('PR_INCLUDE',  r'\b#include\b'), ('PR_DEFINE',   r'\b#define\b'),
    ('PR_NULL',     r'\bNULL\b'),     ('PR_TRUE_C',   r'\btrue\b'),
    ('PR_FALSE_C',  r'\bfalse\b'),    ('PR_NULL_JS',  r'\bnull\b'),
    ('PR_UNDEFINED',r'\bundefined\b'),('PR_TYPEOF',   r'\btypeof\b'),
    ('PR_INSTANCEOF',r'\binstanceof\b'),
    ('PR_FUNCTION', r'\bfunction\b'), ('PR_RETURN_JS',r'\breturn\b'),
    ('PR_THROW',    r'\bthrow\b'),    ('PR_CATCH',    r'\bcatch\b'),
    ('PR_FINAL',    r'\bfinal\b'),    ('PR_ABSTRACT', r'\babstract\b'),

    # ── 5. Identificadores ────────────────────────────────────────────────────
    ('IDENTIFICADOR', r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'),

    # ── 6. Operadores (SIEMPRE los mas largos primero) ────────────────────────

    # Operadores de 3 caracteres
    ('OP_DESPLAZ_IZQ_IGUAL', r'<<='),
    ('OP_DESPLAZ_DER_IGUAL', r'>>='),
    ('OP_FLECHA_DOBLE',      r'=>'),

    # Operadores de 2 caracteres — aritmeticos/logicos compuestos
    ('OP_INCREMENTO',   r'\+\+'),     # ++
    ('OP_DECREMENTO',   r'--'),       # --
    ('OP_POTENCIA',     r'\*\*'),     # **  Python
    ('OP_DIV_ENTERA',   r'//'),       # //  Python (ya cubierto por comentario, aqui no aplica)
    ('OP_FLECHA',       r'->'),       # ->  C/C++
    ('OP_DOBLE_DOS',    r'::'),       # ::  C++ scope
    # Operadores logicos estilo C
    ('OP_AND_LOGICO',   r'&&'),       # &&
    ('OP_OR_LOGICO',    r'\|\|'),     # ||
    # Desplazamiento de bits
    ('OP_DESPLAZ_IZQ',  r'<<'),       # 
    ('OP_DESPLAZ_DER',  r'>>'),       # >>
    # Comparacion
    ('OP_IGUAL_IGUAL',  r'=='),
    ('OP_DIFERENTE',    r'!='),
    ('OP_MAYOR_IGUAL',  r'>='),
    ('OP_MENOR_IGUAL',  r'<='),
    # Asignacion compuesta
    ('OP_MAS_IGUAL',    r'\+='),
    ('OP_MENOS_IGUAL',  r'-='),
    ('OP_MULT_IGUAL',   r'\*='),
    ('OP_DIV_IGUAL',    r'/='),
    ('OP_MOD_IGUAL',    r'%='),
    ('OP_AND_IGUAL',    r'&='),
    ('OP_OR_IGUAL',     r'\|='),
    ('OP_XOR_IGUAL',    r'\^='),

    # Operadores de 1 caracter
    ('OP_ASIGNACION',   r'='),
    ('OP_MAS',          r'\+'),
    ('OP_MENOS',        r'-'),
    ('OP_MULT',         r'\*'),
    ('OP_DIV',          r'/'),
    ('OP_MODULO',       r'%'),
    ('OP_MAYOR',        r'>'),
    ('OP_MENOR',        r'<'),
    ('OP_AND_BIT',      r'&'),        # &  bit a bit
    ('OP_OR_BIT',       r'\|'),       # |  bit a bit
    ('OP_XOR',          r'\^'),       # ^  XOR
    ('OP_NEGACION_BIT', r'~'),        # ~  complemento
    ('OP_PUNTO_PUNTO',  r'\.\.'),     # .. rango
    ('OP_TERNARIO',     r'\?'),       # ?  ternario

    # ── 7. Delimitadores ──────────────────────────────────────────────────────
    ('PAREN_ABRE',      r'\('),   ('PAREN_CIERRA',    r'\)'),
    ('LLAVE_ABRE',      r'\{'),   ('LLAVE_CIERRA',    r'\}'),
    ('CORCHETE_ABRE',   r'\['),   ('CORCHETE_CIERRA', r'\]'),
    ('PUNTO_COMA',      r';'),    ('DOS_PUNTOS',      r':'),
    ('COMA',            r','),    ('PUNTO',           r'\.'),
    ('ARROBA',          r'@'),    # @ decoradores Python / matrices NumPy
    ('SIGNO_DOLAR',     r'\$'),   # $ variables PHP / JS template strings
    ('BACKTICK',        r'`'),    # ` template literals JS
    ('HASH',            r'#'),    # # directiva suelta (sin espacio)
    ('BACKSLASH',       r'\\\\'), # \ escape suelto
    ('PUNTO_COMA_DOBLE',r';;'),   # ;; ensamblador

    # ── 8. Espacios y saltos de linea (se ignoran en la tabla) ───────────────
    ('NUEVA_LINEA',     r'\n'),
    ('ESPACIO',         r'[ \t\r]+'),
]

PATRON_MAESTRO = re.compile(
    '|'.join('(?P<%s>%s)' % (n, p) for n, p in TOKEN_DEFINICIONES)
)

TIPOS_IGNORADOS = {'ESPACIO', 'NUEVA_LINEA'}

# ─── Categorias amigables para la tabla ──────────────────────────────────────
def _cat(tipo):
    """Retorna la categoria legible de un tipo de token."""
    t = tipo
    if t.startswith('PR_'):                         return 'Palabra Reservada'
    if t in ('NUMERO_INT', 'NUMERO_FLOAT'):         return 'Numero'
    if t == 'NUMERO_HEX':                           return 'Numero Hexadecimal'
    if t == 'NUMERO_HEX_ASM':                       return 'Numero Hex (ASM)'
    if t == 'NUMERO_OCTAL':                         return 'Numero Octal'
    if t == 'NUMERO_BINARIO':                       return 'Numero Binario'
    if t == 'NUMERO_CIENTIFICO':                    return 'Numero Cientifico'
    if t == 'IDENTIFICADOR':                        return 'Identificador'
    if t in ('CADENA', 'CADENA_SIMPLE',
             'CADENA_TRIPLE_DOBLE', 'CADENA_TRIPLE_SIMPLE'): return 'Cadena de Texto'
    if t in ('COMENTARIO_LINEA', 'COMENTARIO_BLOQUE',
             'COMENTARIO_PYTHON'):                  return 'Comentario'
    if t == 'OP_ASIGNACION':                        return 'Operador Asignacion'
    if t in ('OP_IGUAL_IGUAL', 'OP_DIFERENTE',
             'OP_MAYOR', 'OP_MENOR',
             'OP_MAYOR_IGUAL', 'OP_MENOR_IGUAL'):   return 'Operador Comparacion'
    if t in ('OP_MAS', 'OP_MENOS', 'OP_MULT',
             'OP_DIV', 'OP_MODULO', 'OP_POTENCIA',
             'OP_INCREMENTO', 'OP_DECREMENTO',
             'OP_DIV_ENTERA'):                      return 'Operador Aritmetico'
    if t in ('OP_MAS_IGUAL', 'OP_MENOS_IGUAL',
             'OP_MULT_IGUAL', 'OP_DIV_IGUAL',
             'OP_MOD_IGUAL'):                       return 'Operador Compuesto'
    if t in ('OP_AND_LOGICO', 'OP_OR_LOGICO',
             'OP_AND_BIT', 'OP_OR_BIT', 'OP_XOR',
             'OP_NEGACION_BIT'):                    return 'Operador Logico/Bit'
    if t in ('OP_DESPLAZ_IZQ', 'OP_DESPLAZ_DER',
             'OP_DESPLAZ_IZQ_IGUAL',
             'OP_DESPLAZ_DER_IGUAL'):               return 'Operador Desplazamiento'
    if t in ('OP_FLECHA', 'OP_FLECHA_DOBLE',
             'OP_DOBLE_DOS', 'OP_TERNARIO'):        return 'Operador Especial'
    if t in ('PAREN_ABRE', 'PAREN_CIERRA',
             'LLAVE_ABRE', 'LLAVE_CIERRA',
             'CORCHETE_ABRE', 'CORCHETE_CIERRA',
             'PUNTO_COMA', 'DOS_PUNTOS', 'COMA',
             'PUNTO', 'PUNTO_COMA_DOBLE',
             'OP_PUNTO_PUNTO'):                     return 'Delimitador'
    if t in ('ARROBA', 'SIGNO_DOLAR', 'BACKTICK',
             'HASH', 'BACKSLASH'):                  return 'Simbolo Especial'
    if t == 'ERROR':                                return 'Error Lexico'
    return tipo


class Token:
    """Un token individual del codigo fuente."""
    def __init__(self, tipo, valor, linea, columna):
        self.tipo = tipo
        self.valor = valor
        self.linea = linea
        self.columna = columna
        self.categoria = _cat(tipo)
    def __repr__(self):
        return 'Token(%s, %r, L%d:C%d)' % (self.tipo, self.valor, self.linea, self.columna)


class AnalizadorLexico:
    """
    Analizador Lexico principal.
    Recorre el codigo fuente y produce una lista de Token.
    """
    def __init__(self):
        self.tokens = []
        self.errores = []
        self.codigo = ""

    def analizar(self, codigo):
        """
        Analiza el codigo fuente y retorna (tokens, errores).
        
        Parametros:
            codigo: string con el codigo a analizar
        Retorna:
            (list[Token], list[dict])
        """
        self.tokens = []
        self.errores = []
        self.codigo = codigo

        linea_actual = 1
        inicio_linea = 0

        for coincidencia in PATRON_MAESTRO.finditer(codigo):
            tipo = coincidencia.lastgroup
            valor = coincidencia.group()
            inicio = coincidencia.start()
            columna = inicio - inicio_linea + 1

            if tipo == 'NUEVA_LINEA':
                linea_actual += 1
                inicio_linea = coincidencia.end()
                continue

            if tipo == 'ESPACIO':
                continue

            token = Token(tipo, valor, linea_actual, columna)
            self.tokens.append(token)

        # Detectar caracteres no reconocidos (errores lexicos)
        posiciones_cubiertas = set()
        for m in PATRON_MAESTRO.finditer(codigo):
            posiciones_cubiertas.update(range(m.start(), m.end()))

        linea_err = 1
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
                    'linea': linea_err,
                    'columna': col_err,
                    'mensaje': "Caracter no reconocido '%s' en linea %d, columna %d" % (char, linea_err, col_err)
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
    Buffer de doble centinela para lectura carácter a carácter.
    Simula el mecanismo clásico de compiladores:
      [ bloque A \0 ][ bloque B \0 ]
    El puntero 'adelante' avanza leyendo caracteres. Cuando toca
    un centinela (\0), carga el siguiente bloque automáticamente.
    'inicio' marca el comienzo del lexema actual.
    """
    TAM = 64  # tamaño de cada mitad del buffer

    def __init__(self, texto):
        self._texto = texto
        self._pos_texto = 0      # posición en el texto fuente
        self._buf = ['\0'] * (self.TAM * 2 + 2)  # buffer doble + centinelas
        self.inicio = 0          # inicio del lexema actual
        self.adelante = 0        # puntero de lectura
        self._cargar_mitad(0)    # carga primera mitad
        self._cargar_mitad(1)    # carga segunda mitad

    def _cargar_mitad(self, mitad):
        """Carga TAM caracteres del texto en la mitad indicada (0 o 1)."""
        base = mitad * (self.TAM + 1)
        for i in range(self.TAM):
            if self._pos_texto < len(self._texto):
                self._buf[base + i] = self._texto[self._pos_texto]
                self._pos_texto += 1
            else:
                self._buf[base + i] = '\0'  # rellena con centinela si se acabó
        self._buf[base + self.TAM] = '\0'   # centinela al final de la mitad

    def siguiente(self):
        """
        Avanza el puntero 'adelante' y retorna el carácter.
        Si toca centinela, recarga la mitad contraria.
        """
        char = self._buf[self.adelante]

        if char == '\0':
            # Determinar en qué mitad estamos
            if self.adelante == self.TAM:
                # Centinela al final de la primera mitad → recargar mitad 0
                self._cargar_mitad(0)
                self.adelante = 0
            elif self.adelante == self.TAM * 2 + 1:
                # Centinela al final de la segunda mitad → recargar mitad 1
                self._cargar_mitad(1)
                self.adelante = self.TAM + 1
            else:
                # Centinela de fin de texto real
                return '\0'
            char = self._buf[self.adelante]

        self.adelante += 1
        return char

    def retroceder(self):
        """Retrocede el puntero adelante un carácter (para devolver lookahead)."""
        if self.adelante > 0:
            self.adelante -= 1

    def lexema_actual(self):
        """Retorna el string del lexema entre inicio y adelante."""
        resultado = []
        i = self.inicio
        while i != self.adelante:
            resultado.append(self._buf[i % len(self._buf)])
            i += 1
        return ''.join(resultado)

    def aceptar(self):
        """Mueve inicio hasta adelante (acepta el lexema actual)."""
        self.inicio = self.adelante

    def reiniciar(self, texto):
        """Reinicia el buffer con nuevo texto."""
        self.__init__(texto)