"""
parser_ast.py - Analizador Sintactico + Generador de Arbol AST
Construye el AST usando descenso recursivo y genera imagen con graphviz.
Compatble con lexer.py modo Python-only.
"""

import os
import sys
import uuid


# ─── Configuracion automatica del PATH de graphviz en Windows ────────────────

def _buscar_graphviz():
    """
    Busca el ejecutable 'dot' de graphviz y configura el PATH.
    Retorna True si lo encuentra, False si no.
    """
    import shutil

    if shutil.which('dot'):
        return True

    rutas_windows = [
        r'C:\Program Files\Graphviz\bin',
        r'C:\Program Files (x86)\Graphviz\bin',
    ]
    for v in range(15, 7, -1):
        rutas_windows.append(r'C:\Program Files\Graphviz %d\bin' % v)
        rutas_windows.append(r'C:\Program Files (x86)\Graphviz %d\bin' % v)
        rutas_windows.append(r'C:\Program Files\Graphviz\%d\bin' % v)
    rutas_windows.append(os.path.expanduser(r'~\AppData\Local\Graphviz\bin'))
    rutas_windows.append(os.path.expanduser(r'~\AppData\Local\Programs\Graphviz\bin'))

    rutas_unix = [
        '/usr/bin',
        '/usr/local/bin',
        '/opt/homebrew/bin',
        '/opt/local/bin',
    ]

    rutas     = rutas_windows if sys.platform == 'win32' else rutas_unix
    nombre_exe = 'dot.exe'    if sys.platform == 'win32' else 'dot'

    for ruta in rutas:
        ejecutable = os.path.join(ruta, nombre_exe)
        if os.path.isfile(ejecutable):
            os.environ['PATH']         = ruta + os.pathsep + os.environ.get('PATH', '')
            os.environ['GRAPHVIZ_DOT'] = ejecutable
            print('[graphviz] Encontrado en: ' + ejecutable)
            return True

    print('[graphviz] No se encontro dot en rutas conocidas.')
    return False


_GRAPHVIZ_OK = _buscar_graphviz()
import graphviz


# ─── Nodo del AST ─────────────────────────────────────────────────────────────

class NodoAST:
    """
    Nodo del Arbol de Sintaxis Abstracta.

    Atributos:
        etiqueta : texto que muestra el nodo (ej: '=', 'x', '+')
        hijos    : lista de NodoAST hijos
        id_unico : ID unico para graphviz (evita confundir nodos con igual texto)
    """

    def __init__(self, etiqueta):
        self.etiqueta = str(etiqueta)
        self.hijos    = []
        self.id_unico = uuid.uuid4().hex[:12]

    def agregar_hijo(self, nodo):
        """Agrega un nodo hijo si no es None."""
        if nodo is not None:
            self.hijos.append(nodo)

    def __repr__(self):
        return 'NodoAST(%s, hijos=%d)' % (self.etiqueta, len(self.hijos))


# ─── Analizador Sintactico (Descenso Recursivo) ───────────────────────────────

class AnalizadorSintactico:
    """
    Parser de descenso recursivo para Python 3.
    Cada metodo corresponde a una regla de la gramatica.

    Gramatica soportada:
        programa       -> sentencia*
        sentencia      -> asignacion | si | mientras | para | retorno
                          | definicion_func | print | bloque | expr_stmt
        asignacion     -> ID op_asig expresion
        si             -> 'if' '(' expresion ')' bloque ('else' bloque)?
        mientras       -> 'while' '(' expresion ')' bloque
        para           -> 'for' ID 'in' expresion ':' bloque
        expresion      -> comparacion
        comparacion    -> suma (op_cmp suma)*
        suma           -> multiplicacion (('+' | '-') multiplicacion)*
        multiplicacion -> primario (('*' | '/' | '//' | '%' | '**') primario)*
        primario       -> NUM | STR | ID | '(' expresion ')' | llamada | lista
    """

    # Tipos de token de comentario en el nuevo lexer (solo uno)
    _COMENTARIOS = ('COMENTARIO',)

    # Tipos de token de cadena en el nuevo lexer
    _CADENAS = ('CADENA_DOBLE', 'CADENA_SIMPLE',
                'CADENA_TRIPLE_DOBLE', 'CADENA_TRIPLE_SIMPLE')

    # Literales booleanos/nulos de Python
    _LITERALES = ('PR_TRUE', 'PR_FALSE', 'PR_NONE')

    # Tipos de numero
    _NUMEROS = ('NUMERO_INT', 'NUMERO_FLOAT', 'NUMERO_CIENTIFICO',
                'NUMERO_HEX', 'NUMERO_OCTAL', 'NUMERO_BINARIO')

    def __init__(self, tokens):
        # Filtrar comentarios y docstrings (cadenas triple comilla sueltas)
        self.tokens = [t for t in tokens
                    if t.tipo not in ('COMENTARIO',
                                        'CADENA_TRIPLE_DOBLE',
                                        'CADENA_TRIPLE_SIMPLE')]
        self.pos     = 0
        self.errores = []

    # ── Metodos auxiliares ────────────────────────────────────────────────────

    def token_actual(self):
        """Retorna el token actual sin avanzar."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def ver(self, offset=0):
        """Mira el token en pos+offset sin consumirlo (lookahead)."""
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return None

    def avanzar(self):
        """Consume y retorna el token actual."""
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def es_tipo(self, *tipos):
        """Retorna True si el token actual es alguno de los tipos dados."""
        t = self.token_actual()
        return t is not None and t.tipo in tipos

    def consumir_si(self, *tipos):
        """Consume el token si coincide — opcional, sin registrar error."""
        if self.es_tipo(*tipos):
            return self.avanzar()
        return None

    def coincidir(self, *tipos):
        """Consume el token esperado — obligatorio; registra error si no coincide."""
        t = self.token_actual()
        if t and t.tipo in tipos:
            return self.avanzar()
        esperado = ' o '.join(tipos)
        actual   = t.valor if t else 'EOF'
        linea    = t.linea if t else '?'
        self.errores.append(
            'Error sintactico linea %s: se esperaba [%s], se encontro "%s"'
            % (linea, esperado, actual)
        )
        return None

    # ── Reglas de la gramatica ────────────────────────────────────────────────

    def analizar(self):
        """Punto de entrada: analiza el programa completo."""
        raiz = NodoAST('Module')
        intentos_sin_avance = 0

        while self.pos < len(self.tokens):
            pos_antes = self.pos
            nodo = self.parsear_sentencia()
            if nodo:
                raiz.agregar_hijo(nodo)

            # Mecanismo de recuperacion de errores:
            # si nadie movio el cursor, forzar avance para evitar bucle infinito
            if self.pos == pos_antes:
                self.pos += 1
                intentos_sin_avance += 1
            else:
                intentos_sin_avance = 0

            if intentos_sin_avance > 20:
                break

        return raiz

    def parsear_sentencia(self):
        """
        Despachador: decide que regla aplicar segun el token actual.
        El orden importa — los casos mas especificos van primero.
        """
        t = self.token_actual()
        if t is None:
            return None

        if t.tipo == 'PR_DEF':
            return self.parsear_funcion()
        if t.tipo == 'PR_IF':
            return self.parsear_si()
        if t.tipo == 'PR_WHILE':
            return self.parsear_mientras()
        if t.tipo == 'PR_FOR':
            return self.parsear_para()
        if t.tipo == 'PR_RETURN':
            return self.parsear_retorno()
        if t.tipo == 'PR_PRINT':
            return self.parsear_print()
        if t.tipo == 'LLAVE_ABRE':
            return self.parsear_bloque()

        # Asignacion: ID seguido de operador de asignacion
        if t.tipo == 'IDENTIFICADOR' and self.ver(1) and self.ver(1).tipo in (
                'OP_ASIGNACION', 'OP_MAS_IGUAL', 'OP_MENOS_IGUAL',
                'OP_MULT_IGUAL', 'OP_DIV_IGUAL', 'OP_MOD_IGUAL',
                'OP_POTENCIA_IGUAL', 'OP_DIV_ENTERA_IGUAL',
                'OP_AND_IGUAL', 'OP_OR_IGUAL', 'OP_XOR_IGUAL',
                'OP_WALRUS'):
            return self.parsear_asignacion()

        return self.parsear_expresion_sentencia()

    def parsear_asignacion(self):
        """
        Parsea: ID op_asig expresion
        El operador es la raiz del subárbol:
            posicion = inicial + velocidad * 60
                =
               / \\
        posicion   +
                  / \\
              inicial  *
                      / \\
               velocidad  60
        """
        id_token = self.avanzar()   # identificador
        op_token = self.avanzar()   # operador (=, +=, //=, etc.)

        nodo = NodoAST(op_token.valor)
        nodo.agregar_hijo(NodoAST(id_token.valor))
        nodo.agregar_hijo(self.parsear_expresion())
        self.consumir_si('PUNTO_COMA')
        return nodo

    def parsear_si(self):
        """Parsea: if (condicion) bloque [else bloque]"""
        self.avanzar()   # Consume 'if'
        nodo = NodoAST('if')
        self.coincidir('PAREN_ABRE')
        nodo.agregar_hijo(self.parsear_expresion())
        self.coincidir('PAREN_CIERRA')
        nodo.agregar_hijo(self.parsear_bloque())
        if self.es_tipo('PR_ELSE'):
            self.avanzar()
            nodo_else = NodoAST('else')
            nodo_else.agregar_hijo(self.parsear_bloque())
            nodo.agregar_hijo(nodo_else)
        elif self.es_tipo('PR_ELIF'):
            # elif se trata como else-if anidado
            nodo.agregar_hijo(self.parsear_si())
        return nodo

    def parsear_mientras(self):
        """Parsea: while (condicion) bloque"""
        self.avanzar()   # Consume 'while'
        nodo = NodoAST('while')
        self.coincidir('PAREN_ABRE')
        nodo.agregar_hijo(self.parsear_expresion())
        self.coincidir('PAREN_CIERRA')
        nodo.agregar_hijo(self.parsear_bloque())
        return nodo

    def parsear_para(self):
        """
        Parsea dos formas:
          Python:  for x in iterable:
          Clasico: for (init; cond; step)
        """
        self.avanzar()   # Consume 'for'
        nodo = NodoAST('for')

        if self.es_tipo('IDENTIFICADOR') and self.ver(1) and self.ver(1).tipo == 'PR_IN':
            # Estilo Python: for x in iterable:
            nodo.agregar_hijo(NodoAST(self.avanzar().valor))   # variable
            self.avanzar()                                      # consume 'in'
            nodo.agregar_hijo(self.parsear_expresion())        # iterable
            self.consumir_si('DOS_PUNTOS')
        else:
            # Estilo clasico: for (init; cond; step)
            self.consumir_si('PAREN_ABRE')
            if self.es_tipo('IDENTIFICADOR'):
                nodo.agregar_hijo(self.parsear_asignacion())
            nodo.agregar_hijo(self.parsear_expresion())
            self.consumir_si('PUNTO_COMA')
            nodo.agregar_hijo(self.parsear_expresion())
            self.consumir_si('PAREN_CIERRA')

        nodo.agregar_hijo(self.parsear_bloque())
        return nodo

    def parsear_retorno(self):
        """Parsea: return [expresion]"""
        self.avanzar()   # Consume 'return'
        nodo = NodoAST('return')
        if not self.es_tipo('PUNTO_COMA', 'LLAVE_CIERRA') and self.token_actual():
            nodo.agregar_hijo(self.parsear_expresion())
        self.consumir_si('PUNTO_COMA')
        return nodo

    def parsear_print(self):
        """Parsea: print(args)"""
        self.avanzar()   # Consume 'print'
        nodo = NodoAST('print')
        self.consumir_si('PAREN_ABRE')
        while not self.es_tipo('PAREN_CIERRA') and self.token_actual():
            nodo.agregar_hijo(self.parsear_expresion())
            self.consumir_si('COMA')
        self.consumir_si('PAREN_CIERRA')
        self.consumir_si('PUNTO_COMA')
        return nodo

    def parsear_funcion(self):
        """Parsea: def nombre(params): bloque"""
        self.avanzar()   # Consume 'def'
        nodo = NodoAST('def')
        if self.es_tipo('IDENTIFICADOR'):
            nodo.agregar_hijo(NodoAST(self.avanzar().valor))
        self.consumir_si('PAREN_ABRE')
        nodo_params = NodoAST('params')
        while not self.es_tipo('PAREN_CIERRA') and self.token_actual():
            if self.es_tipo('IDENTIFICADOR'):
                nodo_params.agregar_hijo(NodoAST(self.avanzar().valor))
            self.consumir_si('COMA')
        nodo.agregar_hijo(nodo_params)
        self.consumir_si('PAREN_CIERRA')
        self.consumir_si('DOS_PUNTOS')
        nodo.agregar_hijo(self.parsear_bloque())
        return nodo

    def parsear_bloque(self):
        """
        Parsea un bloque de sentencias.
        Acepta dos formas:
          { sentencias }   — estilo C/Java
          : sentencia      — estilo Python una linea
        """
        nodo = NodoAST('bloque')
        if self.es_tipo('LLAVE_ABRE'):
            self.avanzar()
            while not self.es_tipo('LLAVE_CIERRA') and self.token_actual():
                hijo = self.parsear_sentencia()
                if hijo:
                    nodo.agregar_hijo(hijo)
                elif self.token_actual():
                    self.pos += 1
            self.consumir_si('LLAVE_CIERRA')
        elif self.es_tipo('DOS_PUNTOS'):
            self.avanzar()
            hijo = self.parsear_sentencia()
            if hijo:
                nodo.agregar_hijo(hijo)
        else:
            hijo = self.parsear_sentencia()
            if hijo:
                nodo.agregar_hijo(hijo)
        return nodo

    def parsear_expresion_sentencia(self):
        """Parsea una expresion usada como sentencia."""
        nodo = self.parsear_expresion()
        self.consumir_si('PUNTO_COMA')
        return nodo

    # ── Jerarquia de expresiones (precedencia de operadores) ─────────────────
    #
    # Nivel mas bajo (menor precedencia) al mas alto:
    #   comparacion → suma → multiplicacion → primario
    #
    # Esto garantiza que * ata mas que + sin logica extra.

    def parsear_expresion(self):
        return self.parsear_comparacion()

    def parsear_comparacion(self):
        """Parsea: suma (op_cmp suma)*"""
        nodo = self.parsear_suma()
        while self.es_tipo('OP_IGUAL_IGUAL', 'OP_DIFERENTE',
                            'OP_MAYOR', 'OP_MENOR',
                            'OP_MAYOR_IGUAL', 'OP_MENOR_IGUAL',
                            'PR_AND', 'PR_OR', 'PR_IN', 'PR_NOT', 'PR_IS'):
            op = self.avanzar()
            nodo_op = NodoAST(op.valor)
            nodo_op.agregar_hijo(nodo)
            nodo_op.agregar_hijo(self.parsear_suma())
            nodo = nodo_op
        return nodo

    def parsear_suma(self):
        """
        Parsea: multiplicacion (('+' | '-') multiplicacion)*

        Ejemplo: a + b * c
              +
             / \\
            a   *
               / \\
              b   c
        """
        nodo = self.parsear_multiplicacion()
        while self.es_tipo('OP_MAS', 'OP_MENOS'):
            op = self.avanzar()
            nodo_op = NodoAST(op.valor)
            nodo_op.agregar_hijo(nodo)
            nodo_op.agregar_hijo(self.parsear_multiplicacion())
            nodo = nodo_op
        return nodo

    def parsear_multiplicacion(self):
        """Parsea: primario (('*'|'/'|'//'|'%'|'**') primario)*"""
        nodo = self.parsear_primario()
        while self.es_tipo('OP_MULT', 'OP_DIV', 'OP_MODULO',
                            'OP_POTENCIA', 'OP_DIV_ENTERA', 'OP_ARROBA'):
            op = self.avanzar()
            nodo_op = NodoAST(op.valor)
            nodo_op.agregar_hijo(nodo)
            nodo_op.agregar_hijo(self.parsear_primario())
            nodo = nodo_op
        return nodo

    def parsear_primario(self):
        """
        Parsea las unidades basicas de una expresion:
        numeros, cadenas, literales, identificadores, llamadas,
        accesos a atributos, indexacion, listas, tuplas y parentesis.
        """
        t = self.token_actual()
        if t is None:
            return NodoAST('EOF')

        # ── Numeros ───────────────────────────────────────────────────────────
        if t.tipo in self._NUMEROS:
            self.avanzar()
            return NodoAST(t.valor)

        # ── Cadenas ───────────────────────────────────────────────────────────
        if t.tipo in self._CADENAS:
            self.avanzar()
            return NodoAST(t.valor)

        # ── Literales Python: True, False, None ───────────────────────────────
        if t.tipo in self._LITERALES:
            self.avanzar()
            return NodoAST(t.valor)

        # ── Identificador, llamada, acceso encadenado ─────────────────────────
        if t.tipo == 'IDENTIFICADOR':
            self.avanzar()
            nodo = NodoAST(t.valor)

            # Loop: obj.met(args)[idx].otro() ...
            while self.token_actual() is not None:
                if self.es_tipo('PAREN_ABRE'):
                    nodo = self._parsear_llamada_nodo(nodo)

                elif self.es_tipo('PUNTO'):
                    self.avanzar()
                    if self.es_tipo('IDENTIFICADOR'):
                        attr = self.avanzar()
                        nodo_punto = NodoAST('.')
                        nodo_punto.agregar_hijo(nodo)
                        nodo_punto.agregar_hijo(NodoAST(attr.valor))
                        nodo = nodo_punto
                    else:
                        break

                elif self.es_tipo('CORCHETE_ABRE'):
                    self.avanzar()
                    nodo_idx = NodoAST('[]')
                    nodo_idx.agregar_hijo(nodo)
                    if not self.es_tipo('CORCHETE_CIERRA'):
                        nodo_idx.agregar_hijo(self.parsear_expresion())
                        # Slice: arr[1:3]
                        if self.es_tipo('DOS_PUNTOS'):
                            self.avanzar()
                            if not self.es_tipo('CORCHETE_CIERRA'):
                                nodo_idx.agregar_hijo(self.parsear_expresion())
                    self.consumir_si('CORCHETE_CIERRA')
                    nodo = nodo_idx

                else:
                    break

            return nodo

        # ── Palabras clave usadas en expresiones ──────────────────────────────
        # Builtins como len(), range(), int(), etc. se tratan igual que ID
        if t.tipo.startswith('PR_') and t.tipo not in (
                'PR_IF', 'PR_ELSE', 'PR_ELIF', 'PR_WHILE', 'PR_FOR',
                'PR_DEF', 'PR_CLASS', 'PR_RETURN', 'PR_IMPORT', 'PR_FROM',
                'PR_GLOBAL', 'PR_NONLOCAL', 'PR_DEL', 'PR_PASS',
                'PR_BREAK', 'PR_CONTINUE', 'PR_WITH', 'PR_AS',
                'PR_TRY', 'PR_EXCEPT', 'PR_FINALLY', 'PR_RAISE',
                'PR_LAMBDA', 'PR_YIELD', 'PR_ASYNC', 'PR_AWAIT'):
            self.avanzar()
            nodo = NodoAST(t.valor)
            # Puede ser una llamada: print(...), len(...), etc.
            if self.es_tipo('PAREN_ABRE'):
                nodo = self._parsear_llamada_nodo(nodo)
            return nodo

        # ── Expresion entre parentesis o tupla ────────────────────────────────
        if t.tipo == 'PAREN_ABRE':
            self.avanzar()
            if self.es_tipo('PAREN_CIERRA'):
                self.avanzar()
                return NodoAST('()')
            nodo = self.parsear_expresion()
            if self.es_tipo('COMA'):
                nodo_tupla = NodoAST('tupla')
                nodo_tupla.agregar_hijo(nodo)
                while self.es_tipo('COMA'):
                    self.avanzar()
                    if not self.es_tipo('PAREN_CIERRA'):
                        nodo_tupla.agregar_hijo(self.parsear_expresion())
                self.consumir_si('PAREN_CIERRA')
                return nodo_tupla
            self.consumir_si('PAREN_CIERRA')
            return nodo

        # ── Lista: [a, b, c] ──────────────────────────────────────────────────
        if t.tipo == 'CORCHETE_ABRE':
            self.avanzar()
            nodo_lista = NodoAST('lista')
            while not self.es_tipo('CORCHETE_CIERRA') and self.token_actual():
                nodo_lista.agregar_hijo(self.parsear_expresion())
                self.consumir_si('COMA')
            self.consumir_si('CORCHETE_CIERRA')
            return nodo_lista

        # ── Diccionario: {k: v, ...} ──────────────────────────────────────────
        if t.tipo == 'LLAVE_ABRE':
            self.avanzar()
            nodo_dict = NodoAST('dict')
            while not self.es_tipo('LLAVE_CIERRA') and self.token_actual():
                nodo_dict.agregar_hijo(self.parsear_expresion())
                self.consumir_si('DOS_PUNTOS')
                nodo_dict.agregar_hijo(self.parsear_expresion())
                self.consumir_si('COMA')
            self.consumir_si('LLAVE_CIERRA')
            return nodo_dict

        # ── Negacion aritmetica: -x ───────────────────────────────────────────
        if t.tipo == 'OP_MENOS':
            self.avanzar()
            nodo_neg = NodoAST('neg')
            nodo_neg.agregar_hijo(self.parsear_primario())
            return nodo_neg

        # ── Not logico / negacion bit ─────────────────────────────────────────
        if t.tipo in ('PR_NOT', 'OP_NEGACION_BIT'):
            self.avanzar()
            nodo_not = NodoAST(t.valor)
            nodo_not.agregar_hijo(self.parsear_expresion())
            return nodo_not

        # ── Lambda ────────────────────────────────────────────────────────────
        if t.tipo == 'PR_LAMBDA':
            self.avanzar()
            nodo_lam = NodoAST('lambda')
            while not self.es_tipo('DOS_PUNTOS') and self.token_actual():
                if self.es_tipo('IDENTIFICADOR'):
                    nodo_lam.agregar_hijo(NodoAST(self.avanzar().valor))
                self.consumir_si('COMA')
            self.consumir_si('DOS_PUNTOS')
            nodo_lam.agregar_hijo(self.parsear_expresion())
            return nodo_lam

        # ── Token no reconocido: hoja y avanzar (evita bucle infinito) ────────
        self.avanzar()
        return NodoAST(t.valor)

    def _parsear_llamada_nodo(self, nodo_func):
        """
        Parsea los argumentos de una llamada cuando ya tenemos el nodo
        de la funcion. Soporta: func(a, b), obj.met(a), lista[i].met()
        """
        etiqueta = nodo_func.etiqueta + '()'
        nodo = NodoAST(etiqueta)
        self.avanzar()   # Consume '('
        while not self.es_tipo('PAREN_CIERRA') and self.token_actual():
            nodo.agregar_hijo(self.parsear_expresion())
            self.consumir_si('COMA')
        self.consumir_si('PAREN_CIERRA')
        return nodo

    def parsear_llamada(self, nombre):
        """Version simple de parsear llamada — mantenida por compatibilidad."""
        nodo = NodoAST(nombre + '()')
        self.avanzar()   # Consume '('
        while not self.es_tipo('PAREN_CIERRA') and self.token_actual():
            nodo.agregar_hijo(self.parsear_expresion())
            self.consumir_si('COMA')
        self.consumir_si('PAREN_CIERRA')
        return nodo


# ─── Generador del Arbol Visual ───────────────────────────────────────────────

class GeneradorArbol:
    """
    Convierte un NodoAST en una imagen PNG usando graphviz.
    Nodos ovales con flechas, colores segun tipo de nodo.
    """

    def generar(self, nodo_raiz, ruta_salida):
        """
        Genera la imagen del arbol AST.

        Parametros:
            nodo_raiz   : NodoAST raiz del arbol
            ruta_salida : ruta sin extension (se agrega .png automaticamente)
        Retorna:
            str : ruta completa del .png generado
        """
        import shutil
        _buscar_graphviz()

        if not shutil.which('dot'):
            raise Exception(
                'graphviz no encontrado. '
                'Descargalo desde graphviz.org/download y marca: '
                'Add Graphviz to the system PATH for all users. '
                'Luego CIERRA y VUELVE A ABRIR VS Code.'
            )

        dot = graphviz.Digraph(name='AST', format='png')
        dot.attr(
            rankdir='TB',
            bgcolor='white',
            fontname='Helvetica',
            nodesep='0.5',
            ranksep='0.6',
        )
        dot.attr('node',
            shape='ellipse',
            style='filled',
            fillcolor='white',
            color='#555555',
            fontname='Helvetica',
            fontsize='12',
            margin='0.2,0.1',
        )
        dot.attr('edge',
            color='#666666',
            arrowsize='0.7',
            arrowhead='vee',
        )

        self._agregar_nodo(dot, nodo_raiz)
        dot.render(ruta_salida, cleanup=True)
        return ruta_salida + '.png'

    def _agregar_nodo(self, dot, nodo):
        """Agrega recursivamente el nodo y sus hijos al grafo."""
        nid   = nodo.id_unico
        color = self._color(nodo.etiqueta)
        dot.node(nid, label=nodo.etiqueta, fillcolor=color)
        for hijo in nodo.hijos:
            dot.edge(nid, hijo.id_unico)
            self._agregar_nodo(dot, hijo)

    def _color(self, etiqueta):
        """Asigna color de relleno segun el tipo de nodo."""
        # Asignaciones
        if etiqueta in ('=', '+=', '-=', '*=', '/=', '//=', '**=',
                        '%=', '&=', '|=', '^=', ':='):
            return '#E8F4FD'   # azul claro
        # Aritmeticos
        if etiqueta in ('+', '-', '*', '/', '//', '%', '**', '@'):
            return '#FEF9E7'   # amarillo claro
        # Comparacion
        if etiqueta in ('==', '!=', '<', '>', '<=', '>=',
                        'and', 'or', 'not', 'in', 'is'):
            return '#FDF2F8'   # rosa
        # Control de flujo y estructuras
        if etiqueta in ('if', 'else', 'elif', 'while', 'for',
                        'return', 'def', 'class', 'print', 'not',
                        'lambda', 'yield', 'with', 'try', 'except',
                        'finally', 'raise', 'pass', 'break', 'continue'):
            return '#E8F8F5'   # verde claro
        # Nodos estructurales del AST
        if etiqueta in ('Module', 'bloque', 'params', 'tupla',
                        'lista', 'dict', '()', '[]', '.', 'neg'):
            return '#F0F0F0'   # gris
        # Numeros
        try:
            float(etiqueta)
            return '#FFF3CD'   # naranja claro
        except ValueError:
            pass
        # Cadenas
        if etiqueta.startswith('"') or etiqueta.startswith("'"):
            return '#F8D7DA'   # rojo claro
        # Literales
        if etiqueta in ('True', 'False', 'None'):
            return '#E8F4FD'   # azul claro (mismo que asignacion)
        # Identificadores y demas
        return 'white'
