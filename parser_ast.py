"""
parser_ast.py - Analizador Sintactico + Generador de Arbol AST
Construye el AST usando descenso recursivo y genera imagen con graphviz.
"""

import os
import sys
import uuid


# ─── Configuracion automatica del PATH de graphviz en Windows ────────────────
# Problema: despues de instalar graphviz, Windows no actualiza el PATH de los
# procesos que ya estaban corriendo (como VS Code). Este codigo busca
# automaticamente el ejecutable 'dot.exe' en las rutas de instalacion tipicas
# y lo agrega al PATH del proceso actual.

def _buscar_graphviz():
    """
    Busca el ejecutable 'dot' de graphviz y configura el PATH.
    Retorna True si lo encuentra, False si no.
    """
    import shutil

    # Si ya esta en el PATH del sistema, perfecto
    if shutil.which('dot'):
        return True

    # Rutas tipicas donde graphviz se instala en Windows
    rutas_windows = [
        r'C:\Program Files\Graphviz\bin',
        r'C:\Program Files (x86)\Graphviz\bin',
    ]
    # Agregar versiones numeradas (14, 13, 12, 11, 10, 9, 8)
    for v in range(15, 7, -1):
        rutas_windows.append(r'C:\Program Files\Graphviz %d\bin' % v)
        rutas_windows.append(r'C:\Program Files (x86)\Graphviz %d\bin' % v)
        rutas_windows.append(r'C:\Program Files\Graphviz\%d\bin' % v)
    # Instalacion por usuario
    rutas_windows.append(os.path.expanduser(r'~\AppData\Local\Graphviz\bin'))
    rutas_windows.append(os.path.expanduser(r'~\AppData\Local\Programs\Graphviz\bin'))

    # Rutas tipicas en Linux/Mac
    rutas_unix = [
        '/usr/bin',
        '/usr/local/bin',
        '/opt/homebrew/bin',
        '/opt/local/bin',
    ]

    rutas = rutas_windows if sys.platform == 'win32' else rutas_unix
    nombre_exe = 'dot.exe' if sys.platform == 'win32' else 'dot'

    for ruta in rutas:
        ejecutable = os.path.join(ruta, nombre_exe)
        if os.path.isfile(ejecutable):
            # Agregar al PATH del proceso actual
            os.environ['PATH'] = ruta + os.pathsep + os.environ.get('PATH', '')
            os.environ['GRAPHVIZ_DOT'] = ejecutable
            print('[graphviz] Encontrado en: ' + ejecutable)
            return True

    print('[graphviz] No se encontro dot en rutas conocidas.')
    return False


# Ejecutar busqueda al importar el modulo
_GRAPHVIZ_OK = _buscar_graphviz()

# Importar graphviz despues de configurar el PATH
import graphviz


# ─── Nodo del AST ─────────────────────────────────────────────────────────────

class NodoAST:
    """
    Nodo del Arbol de Sintaxis Abstracta.
    
    Atributos:
        etiqueta : texto que muestra el nodo (ej: '=', 'posicion', '+')
        hijos    : lista de NodoAST hijos
        id_unico : ID unico para graphviz (evita confundir nodos con igual texto)
    """
    def __init__(self, etiqueta):
        self.etiqueta = str(etiqueta)
        self.hijos = []
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
    Parser de descenso recursivo.
    Cada metodo corresponde a una regla de la gramatica.
    
    Gramatica soportada:
        programa       -> sentencia*
        sentencia      -> asignacion | si | mientras | para | retorno
                          | definicion_func | print | bloque | expr_stmt
        asignacion     -> ID op_asig expresion ';'?
        si             -> 'if' '(' expresion ')' bloque ('else' bloque)?
        mientras       -> 'while' '(' expresion ')' bloque
        para           -> 'for' ... bloque
        expresion      -> comparacion
        comparacion    -> suma (op_cmp suma)*
        suma           -> multiplicacion (('+' | '-') multiplicacion)*
        multiplicacion -> primario (('*' | '/') primario)*
        primario       -> NUM | STR | ID | '(' expresion ')' | llamada
    """

    def __init__(self, tokens):
        # Filtrar comentarios que no aportan a la sintaxis, El estado interno del parser
        self.tokens = [t for t in tokens
               if t.tipo not in ('COMENTARIO_LINEA', 'COMENTARIO_BLOQUE', 'COMENTARIO_PYTHON')]
        self.pos = 0
        self.errores = []

    # ── Metodos auxiliares, vocabulario del parser 
    def token_actual(self):
        """Retorna el token actual sin avanzar."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def ver(self, offset=0):
        """Mira el token en pos+offset sin consumirlo."""
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
        """Consume el token si es del tipo esperado, no obligatorio, si no lo ignora."""
        if self.es_tipo(*tipos):
            return self.avanzar()
        return None

    def coincidir(self, *tipos):
        """Consume el token esperado, obligatorio o registra un error."""
        t = self.token_actual()
        if t and t.tipo in tipos:
            return self.avanzar()
        esperado = ' o '.join(tipos)
        actual = t.valor if t else 'EOF'
        linea = t.linea if t else '?'
        self.errores.append(
            'Error sintactico linea %s: se esperaba [%s], se encontro "%s"' % (linea, esperado, actual)
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
            # post antes es el mecanismo de recuperación de errores
            # Si la posicion no avanzo nada (ni parsear_sentencia ni nadie movio pos)
            # forzamos avance para evitar bucle infinito garantizado
            if self.pos == pos_antes:
                self.pos += 1
                intentos_sin_avance += 1
            else:
                intentos_sin_avance = 0
            # Seguro extra: si llevamos demasiados saltos forzados seguidos, salir
            if intentos_sin_avance > 20:
                break
        return raiz

    def parsear_sentencia(self):
        """Decide que regla aplicar segun el token actual.
        El orden importa: los casos más específicos van primero."""
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
        if t.tipo == 'IDENTIFICADOR' and self.ver(1) and self.ver(1).tipo in (
                'OP_ASIGNACION', 'OP_MAS_IGUAL', 'OP_MENOS_IGUAL',
                'OP_MULT_IGUAL', 'OP_DIV_IGUAL'):
            return self.parsear_asignacion()

        return self.parsear_expresion_sentencia()

    def parsear_asignacion(self):
        """
        Parsea: IDENTIFICADOR = expresion
        Genera nodo '=' con dos hijos: identificador y expresion.
        Ejemplo del profe: posicion = inicial + velocidad * 60
            genera el arbol con '=' en la raiz.
        """
        id_token = self.avanzar()    # Consume el identificador
        op_token = self.avanzar()    # Consume el operador (=, +=, etc.)

        nodo = NodoAST(op_token.valor)       # Nodo raiz es el operador
        nodo.agregar_hijo(NodoAST(id_token.valor))  # Hijo izq: identificador
        nodo.agregar_hijo(self.parsear_expresion()) # Hijo der: expresion
        self.consumir_si('PUNTO_COMA')
        return nodo

    def parsear_si(self):
        self.avanzar()  # Consume 'if'
        nodo = NodoAST('if')
        self.coincidir('PAREN_ABRE')                    # registra error si falta (
        nodo.agregar_hijo(self.parsear_expresion())
        self.coincidir('PAREN_CIERRA')                  # registra error si falta )
        nodo.agregar_hijo(self.parsear_bloque())
        if self.es_tipo('PR_ELSE'):
            self.avanzar()
            nodo_else = NodoAST('else')
            nodo_else.agregar_hijo(self.parsear_bloque())
            nodo.agregar_hijo(nodo_else)
        return nodo

    def parsear_mientras(self):
        self.avanzar()
        nodo = NodoAST('while')
        self.coincidir('PAREN_ABRE')         # era consumir_si
        nodo.agregar_hijo(self.parsear_expresion())
        self.coincidir('PAREN_CIERRA')       # era consumir_si
        nodo.agregar_hijo(self.parsear_bloque())
        return nodo

    def parsear_para(self):
        """Parsea: for ... bloque"""
        self.avanzar()  # Consume 'for'
        nodo = NodoAST('for')
        if self.es_tipo('IDENTIFICADOR') and self.ver(1) and self.ver(1).tipo == 'PR_IN':
            nodo.agregar_hijo(NodoAST(self.avanzar().valor))
            self.avanzar()  # Consume 'in'
            nodo.agregar_hijo(self.parsear_expresion())
            self.consumir_si('DOS_PUNTOS')
        else:
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
        self.avanzar()  # Consume 'return'
        nodo = NodoAST('return')
        if not self.es_tipo('PUNTO_COMA', 'LLAVE_CIERRA') and self.token_actual():
            nodo.agregar_hijo(self.parsear_expresion())
        self.consumir_si('PUNTO_COMA')
        return nodo

    def parsear_print(self):
        """Parsea: print(args)"""
        self.avanzar()  # Consume 'print'
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
        self.avanzar()  # Consume 'def'
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
        """Parsea un bloque de sentencias { ... } o : sentencia"""
        nodo = NodoAST('bloque')
        if self.es_tipo('LLAVE_ABRE'):
            self.avanzar()  # Consume '{'
            while not self.es_tipo('LLAVE_CIERRA') and self.token_actual():
                hijo = self.parsear_sentencia()
                if hijo:
                    nodo.agregar_hijo(hijo)
                elif self.token_actual():
                    self.pos += 1
            self.consumir_si('LLAVE_CIERRA')
        elif self.es_tipo('DOS_PUNTOS'):
            self.avanzar()  # Consume ':'
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

    def parsear_expresion(self):
        """Nivel mas alto de expresion."""
        return self.parsear_comparacion()

    def parsear_comparacion(self):
        """Parsea: suma (op_comparacion suma)*"""
        nodo = self.parsear_suma()
        while self.es_tipo('OP_IGUAL_IGUAL', 'OP_DIFERENTE', 'OP_MAYOR',
                            'OP_MENOR', 'OP_MAYOR_IGUAL', 'OP_MENOR_IGUAL',
                            'PR_AND', 'PR_OR'):
            op = self.avanzar()
            nodo_op = NodoAST(op.valor)
            nodo_op.agregar_hijo(nodo)
            nodo_op.agregar_hijo(self.parsear_suma())
            nodo = nodo_op
        return nodo

    def parsear_suma(self):
        """
        Parsea: multiplicacion (('+' | '-') multiplicacion)*
        Crea el arbol con operadores como nodos internos.
        Ejemplo: inicial + velocidad * 60
            +
           / \\
        inicial  *
                / \\
          velocidad 60
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
        """Parsea: primario (('*' | '/') primario)*"""
        nodo = self.parsear_primario()
        while self.es_tipo('OP_MULT', 'OP_DIV', 'OP_MODULO'):
            op = self.avanzar()
            nodo_op = NodoAST(op.valor)
            nodo_op.agregar_hijo(nodo)
            nodo_op.agregar_hijo(self.parsear_primario())
            nodo = nodo_op
        return nodo

    def parsear_primario(self):
        """
        Parsea unidades basicas.
        Cubre todos los tipos de tokens que pueden aparecer en expresiones,
        incluyendo los nuevos: hex, cientifico, cadenas triples, accesos
        encadenados (obj.met1().met2()), indexacion (arr[i]), etc.
        """
        t = self.token_actual()
        if t is None:
            return NodoAST('EOF')

        # ── Todos los tipos de numeros ─────────────────────────────────────────
        if t.tipo in ('NUMERO_INT', 'NUMERO_FLOAT', 'NUMERO_CIENTIFICO',
                      'NUMERO_HEX', 'NUMERO_HEX_ASM', 'NUMERO_OCTAL',
                      'NUMERO_BINARIO'):
            self.avanzar()
            return NodoAST(t.valor)

        # ── Todos los tipos de cadenas ─────────────────────────────────────────
        if t.tipo in ('CADENA', 'CADENA_SIMPLE',
                      'CADENA_TRIPLE_DOBLE', 'CADENA_TRIPLE_SIMPLE'):
            self.avanzar()
            return NodoAST(t.valor)

        # ── Literales booleanos y nulos ────────────────────────────────────────
        if t.tipo in ('PR_TRUE', 'PR_FALSE', 'PR_NONE',
                      'PR_TRUE_C', 'PR_FALSE_C', 'PR_NULL', 'PR_NULL_JS',
                      'PR_UNDEFINED'):
            self.avanzar()
            return NodoAST(t.valor)

        # ── Identificador: variable, llamada, acceso encadenado ───────────────
        if t.tipo == 'IDENTIFICADOR':
            self.avanzar()
            nodo = NodoAST(t.valor)

            # Loop para manejar cadenas: obj.met(args)[idx].otro(args)...
            while self.token_actual() is not None:
                # Llamada a funcion: nombre(args)
                if self.es_tipo('PAREN_ABRE'):
                    nodo = self._parsear_llamada_nodo(nodo)

                # Acceso a atributo: objeto.atributo
                elif self.es_tipo('PUNTO'):
                    self.avanzar()  # Consume '.'
                    if self.es_tipo('IDENTIFICADOR'):
                        attr = self.avanzar()
                        nodo_punto = NodoAST('.')
                        nodo_punto.agregar_hijo(nodo)
                        nodo_punto.agregar_hijo(NodoAST(attr.valor))
                        nodo = nodo_punto
                    else:
                        break

                # Indexacion: array[indice]
                elif self.es_tipo('CORCHETE_ABRE'):
                    self.avanzar()  # Consume '['
                    nodo_idx = NodoAST('[]')
                    nodo_idx.agregar_hijo(nodo)
                    # Parsear el indice (puede ser : para slices)
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

        # ── Expresion entre parentesis: (expr) ────────────────────────────────
        if t.tipo == 'PAREN_ABRE':
            self.avanzar()
            # Parentesis vacio ()
            if self.es_tipo('PAREN_CIERRA'):
                self.avanzar()
                return NodoAST('()')
            nodo = self.parsear_expresion()
            # Tupla: (a, b, c)
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

        # ── Negacion aritmetica: -x ────────────────────────────────────────────
        if t.tipo == 'OP_MENOS':
            self.avanzar()
            nodo_neg = NodoAST('neg')
            nodo_neg.agregar_hijo(self.parsear_primario())
            return nodo_neg

        # ── Not logico ────────────────────────────────────────────────────────
        if t.tipo in ('PR_NOT', 'OP_NEGACION_BIT'):
            self.avanzar()
            nodo_not = NodoAST(t.valor)
            nodo_not.agregar_hijo(self.parsear_expresion())
            return nodo_not

        # ── Operadores unarios de C: ++x, --x ─────────────────────────────────
        if t.tipo in ('OP_INCREMENTO', 'OP_DECREMENTO'):
            self.avanzar()
            nodo_u = NodoAST(t.valor)
            nodo_u.agregar_hijo(self.parsear_primario())
            return nodo_u

        # ── Cualquier token no reconocido: crear nodo hoja y avanzar ──────────
        # Esto evita el bucle infinito: en vez de retornar None y no avanzar,
        # consumimos el token y lo representamos como hoja en el arbol.
        self.avanzar()
        return NodoAST(t.valor)

    def parsear_llamada(self, nombre):
        """Parsea nombre(arg1, arg2, ...) — version simple para compatibilidad."""
        nodo = NodoAST(nombre + '()')
        self.avanzar()  # Consume '('
        while not self.es_tipo('PAREN_CIERRA') and self.token_actual():
            nodo.agregar_hijo(self.parsear_expresion())
            self.consumir_si('COMA')
        self.consumir_si('PAREN_CIERRA')
        return nodo

    def _parsear_llamada_nodo(self, nodo_func):
        """
        Parsea argumentos de llamada cuando ya tenemos el nodo de la funcion.
        Usado por parsear_primario para cadenas como obj.met(args).
        """
        etiqueta = nodo_func.etiqueta + '()'
        nodo = NodoAST(etiqueta)
        self.avanzar()  # Consume '('
        while not self.es_tipo('PAREN_CIERRA') and self.token_actual():
            nodo.agregar_hijo(self.parsear_expresion())
            self.consumir_si('COMA')
        self.consumir_si('PAREN_CIERRA')
        return nodo


# ─── Generador del Arbol Visual ───────────────────────────────────────────────

class GeneradorArbol:
    """
    Convierte un NodoAST en una imagen PNG usando graphviz.
    Estilo visual con nodos ovales con flechas.
    """

    def generar(self, nodo_raiz, ruta_salida):
        """
        Genera la imagen del arbol AST.
        
        Parametros:
            nodo_raiz   : NodoAST raiz
            ruta_salida : ruta sin extension (se genera .png)
        Retorna:
            str: ruta completa del .png generado
        """
        import shutil

        # Reintentar buscar graphviz por si se instalo despues de iniciar
        _buscar_graphviz()

        # Verificar que 'dot' sea accesible
        if not shutil.which('dot'):
            raise Exception(
                'graphviz no encontrado. '
                'Descargalo desde graphviz.org/download y marca: '
                'Add Graphviz to the system PATH for all users. '
                'Luego CIERRA y VUELVE A ABRIR VS Code.'
            )

        # Crear el grafo dirigido, Configurar el grafo 
        
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

        # Construir el grafo recursivamente, 
        self._agregar_nodo(dot, nodo_raiz)

        # Renderizar y guardar
        dot.render(ruta_salida, cleanup=True)
        return ruta_salida + '.png'
    # Poblar el grafo 
    def _agregar_nodo(self, dot, nodo):
        """Agrega recursivamente el nodo y sus hijos al grafo."""
        nid = nodo.id_unico
        color = self._color(nodo.etiqueta)
        dot.node(nid, label=nodo.etiqueta, fillcolor=color)
        for hijo in nodo.hijos:
            dot.edge(nid, hijo.id_unico)
            self._agregar_nodo(dot, hijo)

    def _color(self, etiqueta):
        """Asigna color de relleno segun el tipo de nodo."""
        if etiqueta in ('=', '+=', '-=', '*=', '/='):
            return '#E8F4FD'   # Azul claro: asignaciones
        if etiqueta in ('+', '-', '*', '/', '%'):
            return '#FEF9E7'   # Amarillo claro: aritmeticos
        if etiqueta in ('==', '!=', '<', '>', '<=', '>='):
            return '#FDF2F8'   # Rosa: comparaciones
        if etiqueta in ('if', 'else', 'while', 'for', 'return', 'def', 'print', 'not'):
            return '#E8F8F5'   # Verde claro: control de flujo
        if etiqueta in ('Module', 'bloque', 'params'):
            return '#F0F0F0'   # Gris: estructurales
        try:
            float(etiqueta)
            return '#FFF3CD'   # Naranja claro: numeros
        except ValueError:
            pass
        if etiqueta.startswith('"') or etiqueta.startswith("'"):
            return '#F8D7DA'   # Rojo claro: cadenas
        return 'white'         # Blanco: identificadores
