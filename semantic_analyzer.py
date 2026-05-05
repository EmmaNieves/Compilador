"""
semantic_analyzer.py - Analizador Semantico
Recorre el AST generado por AnalizadorSintactico y realiza:
  1. Construccion y gestion de la tabla de simbolos (con scopes anidados)
  2. Inferencia y validacion de tipos de datos
  3. Deteccion de errores semanticos:
       - Variables no declaradas
       - Variables re-declaradas en el mismo scope
       - Incompatibilidades de tipo en asignaciones y expresiones
       - Uso de identificadores como si fueran funciones sin ser declarados como tal
       - Retorno fuera de funcion
  4. Recorrido en PREORDEN para declaraciones y POSTORDEN para inferencia de tipos.

Compatibilidad: trabaja directamente con NodoAST de parser_ast.py.
No modifica ningun modulo existente.
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECCION 1 — TIPOS DEL SISTEMA
# ═══════════════════════════════════════════════════════════════════════════════

class TipoSemantico:
    """
    Representa el tipo inferido de una expresion o variable.

    El sistema de tipos maneja:
        INT, FLOAT, STRING, BOOL, NONE, LIST, DICT,
        FUNCION, DESCONOCIDO (no se puede inferir), ERROR (error ya reportado)
    """

    # Constantes de tipo
    INT         = 'int'
    FLOAT       = 'float'
    STRING      = 'string'
    BOOL        = 'bool'
    NONE        = 'None'
    LIST        = 'list'
    DICT        = 'dict'
    FUNCION     = 'funcion'
    DESCONOCIDO = 'desconocido'
    ERROR       = 'error'

    # Tipos numericos — permiten operaciones aritmeticas entre si
    _NUMERICOS = {INT, FLOAT}

    # Tabla de compatibilidad de tipos en operaciones aritmeticas:
    # (tipo_izq, tipo_der) -> tipo_resultado
    _TABLA_ARITMETICA = {
        (INT,    INT):    INT,
        (FLOAT,  FLOAT):  FLOAT,
        (INT,    FLOAT):  FLOAT,
        (FLOAT,  INT):    FLOAT,
        (STRING, INT):    STRING,   # 'hola' * 3  ->  string (solo para *)
        (INT,    STRING): STRING,
    }

    @classmethod
    def es_numerico(cls, tipo):
        return tipo in cls._NUMERICOS

    @classmethod
    def resultado_aritmetico(cls, tipo_izq, tipo_der, operador):
        """
        Retorna el tipo resultado de una operacion aritmetica.
        Retorna ERROR si la combinacion es invalida.
        """
        # Casos especiales: solo multiplicacion permite string * int
        if operador != '*' and (tipo_izq == cls.STRING or tipo_der == cls.STRING):
            return cls.ERROR

        par = (tipo_izq, tipo_der)
        if par in cls._TABLA_ARITMETICA:
            return cls._TABLA_ARITMETICA[par]

        # Tipos desconocidos o error previo: propagar sin nuevo error
        if cls.DESCONOCIDO in par or cls.ERROR in par:
            return cls.DESCONOCIDO

        return cls.ERROR

    @classmethod
    def desde_literal(cls, etiqueta):
        """
        Infiere el tipo de un nodo hoja a partir de su etiqueta textual.
        """
        # Cadenas de texto
        if etiqueta.startswith('"') or etiqueta.startswith("'"):
            return cls.STRING

        # Booleanos y None
        if etiqueta == 'True' or etiqueta == 'False':
            return cls.BOOL
        if etiqueta == 'None':
            return cls.NONE

        # Numeros
        try:
            int(etiqueta, 0)   # soporta 0x..., 0b..., 0o...
            return cls.INT
        except (ValueError, TypeError):
            pass
        try:
            float(etiqueta)
            return cls.FLOAT
        except (ValueError, TypeError):
            pass

        # Notacion cientifica (ej: 1e10, 2.5e-3)
        if 'e' in etiqueta.lower() and etiqueta.replace('.','').replace('-','').replace('+','').replace('e','').isdigit():
            return cls.FLOAT

        return cls.DESCONOCIDO


# ═══════════════════════════════════════════════════════════════════════════════
# SECCION 2 — TABLA DE SIMBOLOS
# ═══════════════════════════════════════════════════════════════════════════════

class Simbolo:
    """
    Entrada en la tabla de simbolos.

    Atributos:
        nombre     : str — nombre del identificador
        tipo       : str — tipo semantico (TipoSemantico.*)
        categoria  : str — 'variable' | 'funcion' | 'parametro'
        linea_decl : int | None — linea de declaracion (si se puede recuperar)
        alcance    : str — nombre del scope donde fue declarado
        num_params : int | None — solo para funciones
    """

    def __init__(self, nombre, tipo, categoria, alcance, linea_decl=None, num_params=None):
        self.nombre     = nombre
        self.tipo       = tipo
        self.categoria  = categoria
        self.alcance    = alcance
        self.linea_decl = linea_decl
        self.num_params = num_params

    def __repr__(self):
        return 'Simbolo(%s: %s [%s] scope=%s)' % (
            self.nombre, self.tipo, self.categoria, self.alcance)


class TabladeSimbolos:
    """
    Tabla de simbolos con alcances anidados (stack de scopes).

    Modelo: cada llamada a 'entrar_scope' apila un nuevo diccionario.
    La busqueda sube por la cadena de scopes hasta encontrar el simbolo
    o llegar al global sin resultado.

    Estructura interna:
        _pila  : lista de dicts {nombre -> Simbolo}  (indice 0 = global)
        _nombres: lista de str con el nombre de cada scope
    """

    def __init__(self):
        self._pila    = [{}]           # scope global
        self._nombres = ['global']

    # ── Gestion de scopes ─────────────────────────────────────────────────────

    def entrar_scope(self, nombre):
        """Crea y apila un nuevo scope."""
        self._pila.append({})
        self._nombres.append(nombre)

    def salir_scope(self):
        """Desapila el scope actual. No se puede salir del global."""
        if len(self._pila) > 1:
            self._pila.pop()
            self._nombres.pop()

    def scope_actual(self):
        return self._nombres[-1]

    def en_scope_global(self):
        return len(self._pila) == 1

    # ── Operaciones sobre simbolos ────────────────────────────────────────────

    def declarar(self, simbolo):
        """
        Declara un simbolo en el scope actual.
        Retorna True si es nueva declaracion, False si ya existia en este scope.
        """
        scope_dict = self._pila[-1]
        if simbolo.nombre in scope_dict:
            return False   # ya declarado en este scope exacto
        scope_dict[simbolo.nombre] = simbolo
        return True

    def buscar(self, nombre):
        """
        Busca el simbolo por nombre subiendo desde el scope actual hasta el global.
        Retorna el Simbolo o None.
        """
        for scope_dict in reversed(self._pila):
            if nombre in scope_dict:
                return scope_dict[nombre]
        return None

    def existe_en_scope_actual(self, nombre):
        return nombre in self._pila[-1]

    def actualizar_tipo(self, nombre, nuevo_tipo):
        """Actualiza el tipo de un simbolo ya declarado (reasignacion)."""
        for scope_dict in reversed(self._pila):
            if nombre in scope_dict:
                scope_dict[nombre].tipo = nuevo_tipo
                return True
        return False

    def obtener_todos(self):
        """
        Retorna lista plana de todos los simbolos de todos los scopes,
        ordenada global -> mas anidado.
        """
        resultado = []
        for scope_dict in self._pila:
            resultado.extend(scope_dict.values())
        return resultado

    def exportar_tabla(self):
        """
        Retorna lista de dicts lista para mostrar en GUI o PDF.
        Cada dict: {nombre, tipo, categoria, alcance, linea}
        """
        filas = []
        for simbolo in self.obtener_todos():
            filas.append({
                'nombre'    : simbolo.nombre,
                'tipo'      : simbolo.tipo,
                'categoria' : simbolo.categoria,
                'alcance'   : simbolo.alcance,
                'linea'     : str(simbolo.linea_decl) if simbolo.linea_decl else '—',
            })
        return filas


# ═══════════════════════════════════════════════════════════════════════════════
# SECCION 3 — ERROR SEMANTICO
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorSemantico:
    """
    Representa un error semantico detectado durante el analisis.

    Categorias definidas:
        VAR_NO_DECLARADA      — uso de variable antes de declarar
        VAR_DUPLICADA         — re-declaracion en el mismo scope
        TIPO_INCOMPATIBLE     — asignacion o operacion entre tipos incompatibles
        USO_INVALIDO          — llamada a algo que no es funcion, etc.
        RETORNO_FUERA_FUNC    — return fuera del cuerpo de una funcion
        ARIDAD_INCORRECTA     — llamada con numero incorrecto de argumentos
    """

    VAR_NO_DECLARADA   = 'Variable no declarada'
    VAR_DUPLICADA      = 'Variable duplicada'
    TIPO_INCOMPATIBLE  = 'Incompatibilidad de tipos'
    USO_INVALIDO       = 'Uso invalido de identificador'
    RETORNO_FUERA_FUNC = 'Return fuera de funcion'
    ARIDAD_INCORRECTA  = 'Numero incorrecto de argumentos'

    def __init__(self, categoria, mensaje, variable=None, linea=None):
        self.categoria = categoria
        self.mensaje   = mensaje
        self.variable  = variable     # identificador afectado (si aplica)
        self.linea     = linea        # numero de linea (si disponible)

    def __str__(self):
        partes = ['[%s]' % self.categoria]
        if self.variable:
            partes.append('"%s"' % self.variable)
        partes.append(self.mensaje)
        if self.linea:
            partes.append('(linea %s)' % self.linea)
        return ' — '.join(partes)

    def __repr__(self):
        return 'ErrorSemantico(%s)' % str(self)


# ═══════════════════════════════════════════════════════════════════════════════
# SECCION 4 — ANALIZADOR SEMANTICO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

# Operadores de asignacion compuesta: lhs op= rhs
_OPS_ASIG_COMPUESTA = {'+=', '-=', '*=', '/=', '//=', '**=', '%=', '&=', '|=', '^='}

# Operadores aritmeticos
_OPS_ARITMETICOS = {'+', '-', '*', '/', '//', '%', '**'}

# Operadores de comparacion — siempre retornan bool
_OPS_COMPARACION = {'==', '!=', '<', '>', '<=', '>=', 'in', 'is'}

# Operadores logicos — esperan bool o compatible, retornan bool
_OPS_LOGICOS = {'and', 'or', 'not'}

# Funciones builtin conocidas con sus tipos de retorno
_BUILTINS = {
    'print'  : TipoSemantico.NONE,
    'input'  : TipoSemantico.STRING,
    'len'    : TipoSemantico.INT,
    'range'  : TipoSemantico.LIST,
    'int'    : TipoSemantico.INT,
    'float'  : TipoSemantico.FLOAT,
    'str'    : TipoSemantico.STRING,
    'bool'   : TipoSemantico.BOOL,
    'list'   : TipoSemantico.LIST,
    'dict'   : TipoSemantico.DICT,
    'set'    : TipoSemantico.LIST,
    'tuple'  : TipoSemantico.LIST,
    'type'   : TipoSemantico.STRING,
    'abs'    : TipoSemantico.DESCONOCIDO,
    'max'    : TipoSemantico.DESCONOCIDO,
    'min'    : TipoSemantico.DESCONOCIDO,
    'sum'    : TipoSemantico.DESCONOCIDO,
    'sorted' : TipoSemantico.LIST,
    'open'   : TipoSemantico.DESCONOCIDO,
}


class AnalizadorSemantico:
    """
    Recorre el AST producido por AnalizadorSintactico y realiza el analisis
    semantico completo.

    Uso tipico:
        analizador = AnalizadorSemantico()
        errores, tabla = analizador.analizar(nodo_raiz_ast)

    El recorrido combina:
        - PREORDEN  para declarar funciones y variables (el nodo padre se procesa
          antes que sus hijos, lo que permite registrar el simbolo antes de
          evaluar el cuerpo de una funcion).
        - POSTORDEN para inferir tipos en expresiones (los hijos se evaluan
          primero para que el padre pueda combinar sus tipos).

    Esta estrategia mixta es estandar en compiladores de una pasada.
    """

    def __init__(self):
        self.tabla   = TabladeSimbolos()
        self.errores = []
        self._dentro_funcion = 0   # contador de niveles de anidacion en funciones

    # ── Punto de entrada ──────────────────────────────────────────────────────

    def analizar(self, nodo_raiz):
        """
        Inicia el analisis semantico sobre el AST.

        Parametros:
            nodo_raiz : NodoAST — raiz del arbol (etiqueta == 'Module')

        Retorna:
            (list[ErrorSemantico], TabladeSimbolos)
        """
        self.tabla   = TabladeSimbolos()
        self.errores = []
        self._dentro_funcion = 0

        self._visitar(nodo_raiz)

        return self.errores, self.tabla

    # ── Dispatcher principal ──────────────────────────────────────────────────

    def _visitar(self, nodo):
        """
        Despacha el nodo al metodo de visita correspondiente segun su etiqueta.
        Retorna el tipo inferido del nodo (TipoSemantico.*).
        """
        if nodo is None:
            return TipoSemantico.DESCONOCIDO

        et = nodo.etiqueta

        # ── Nodo raiz ─────────────────────────────────────────────────────────
        if et == 'Module':
            return self._visitar_modulo(nodo)

        # ── Bloque de sentencias ──────────────────────────────────────────────
        if et == 'bloque':
            return self._visitar_bloque(nodo)

        # ── Declaracion de funcion ────────────────────────────────────────────
        if et == 'def':
            return self._visitar_def(nodo)

        # ── Asignacion simple y compuesta ─────────────────────────────────────
        if et == '=' or et in _OPS_ASIG_COMPUESTA:
            return self._visitar_asignacion(nodo)

        # ── Control de flujo ──────────────────────────────────────────────────
        if et == 'if':
            return self._visitar_if(nodo)

        if et == 'while':
            return self._visitar_while(nodo)

        if et == 'for':
            return self._visitar_for(nodo)

        # ── Retorno ───────────────────────────────────────────────────────────
        if et == 'return':
            return self._visitar_return(nodo)

        # ── Operadores aritmeticos ────────────────────────────────────────────
        if et in _OPS_ARITMETICOS:
            return self._visitar_op_aritmetico(nodo)

        # ── Operadores de comparacion ─────────────────────────────────────────
        if et in _OPS_COMPARACION:
            self._visitar_hijos(nodo)
            return TipoSemantico.BOOL

        # ── Operadores logicos ────────────────────────────────────────────────
        if et in _OPS_LOGICOS:
            self._visitar_hijos(nodo)
            return TipoSemantico.BOOL

        # ── Llamada a funcion: etiqueta termina en '()' ────────────────────────
        if et.endswith('()'):
            return self._visitar_llamada(nodo)

        # ── Negacion unaria ───────────────────────────────────────────────────
        if et == 'neg':
            tipo_inner = self._visitar(nodo.hijos[0]) if nodo.hijos else TipoSemantico.DESCONOCIDO
            return tipo_inner if TipoSemantico.es_numerico(tipo_inner) else TipoSemantico.DESCONOCIDO

        # ── Estructuras de datos literales ────────────────────────────────────
        if et in ('lista', '[]'):
            self._visitar_hijos(nodo)
            return TipoSemantico.LIST

        if et == 'dict':
            self._visitar_hijos(nodo)
            return TipoSemantico.DICT

        if et == 'tupla':
            self._visitar_hijos(nodo)
            return TipoSemantico.LIST

        # ── Acceso a miembro: obj.attr ────────────────────────────────────────
        if et == '.':
            self._visitar_hijos(nodo)
            return TipoSemantico.DESCONOCIDO

        # ── Acceso a indice: lista[i] ─────────────────────────────────────────
        if et == '[]':
            self._visitar_hijos(nodo)
            return TipoSemantico.DESCONOCIDO

        # ── Hoja: literal o identificador ─────────────────────────────────────
        return self._visitar_hoja(nodo)

    # ── Visitores especificos ─────────────────────────────────────────────────

    def _visitar_modulo(self, nodo):
        """Visita todas las sentencias del modulo en orden."""
        for hijo in nodo.hijos:
            self._visitar(hijo)
        return TipoSemantico.NONE

    def _visitar_bloque(self, nodo):
        """Visita sentencias de un bloque (no crea scope propio; lo hace el padre)."""
        for hijo in nodo.hijos:
            self._visitar(hijo)
        return TipoSemantico.NONE

    def _visitar_def(self, nodo):
        """
        Procesamiento de declaracion de funcion.
        Estructura del nodo 'def' producida por el parser:
            hijos[0]  -> NodoAST con etiqueta = nombre de la funcion
            hijos[1]  -> NodoAST 'params' con los parametros como hijos
            hijos[2+] -> cuerpo (bloque)

        Estrategia PREORDEN: se registra la funcion en la tabla ANTES de
        procesar su cuerpo para permitir recursion.
        """
        if len(nodo.hijos) < 1:
            return TipoSemantico.NONE

        nombre_nodo = nodo.hijos[0]
        nombre_func = nombre_nodo.etiqueta

        # Contar parametros
        params_nodo = None
        num_params  = 0
        for hijo in nodo.hijos[1:]:
            if hijo.etiqueta == 'params':
                params_nodo = hijo
                num_params  = len(hijo.hijos)
                break

        # Registrar la funcion en la tabla (PREORDEN — antes del cuerpo)
        simbolo_func = Simbolo(
            nombre     = nombre_func,
            tipo       = TipoSemantico.FUNCION,
            categoria  = 'funcion',
            alcance    = self.tabla.scope_actual(),
            num_params = num_params,
        )
        declarada = self.tabla.declarar(simbolo_func)
        if not declarada:
            self.errores.append(ErrorSemantico(
                categoria = ErrorSemantico.VAR_DUPLICADA,
                mensaje   = 'La funcion "%s" ya fue declarada en este scope.' % nombre_func,
                variable  = nombre_func,
                linea     = nodo.linea,
            ))

        # Entrar al scope de la funcion
        self.tabla.entrar_scope(nombre_func)
        self._dentro_funcion += 1

        # Declarar parametros en el nuevo scope
        if params_nodo:
            for param in params_nodo.hijos:
                simbolo_param = Simbolo(
                    nombre    = param.etiqueta,
                    tipo      = TipoSemantico.DESCONOCIDO,
                    categoria = 'parametro',
                    alcance   = self.tabla.scope_actual(),
                )
                self.tabla.declarar(simbolo_param)

        # Visitar el cuerpo
        for hijo in nodo.hijos[1:]:
            if hijo.etiqueta != 'params':
                self._visitar(hijo)

        self._dentro_funcion -= 1
        self.tabla.salir_scope()

        return TipoSemantico.NONE

    def _visitar_asignacion(self, nodo):
        """
        Procesamiento de asignacion: lhs = rhs  /  lhs op= rhs

        Flujo:
            1. Evaluar el lado derecho (POSTORDEN sobre rhs).
            2. Si lhs es un identificador:
               a. Si no existe en la tabla: declararlo con el tipo de rhs.
               b. Si existe: validar compatibilidad de tipos.
            3. Para asignacion compuesta (+=, etc.): verificar que lhs
               ya este declarado (no puede declarar en +=).
        """
        if len(nodo.hijos) < 2:
            return TipoSemantico.DESCONOCIDO

        nodo_lhs = nodo.hijos[0]
        nodo_rhs = nodo.hijos[1]

        # Evaluar el lado derecho primero (postorden)
        tipo_rhs = self._visitar(nodo_rhs)

        operador = nodo.etiqueta

        # ── Asignacion compuesta: lhs debe ya existir ─────────────────────────
        if operador in _OPS_ASIG_COMPUESTA:
            simbolo = self.tabla.buscar(nodo_lhs.etiqueta)
            if simbolo is None:
                self.errores.append(ErrorSemantico(
                    categoria = ErrorSemantico.VAR_NO_DECLARADA,
                    mensaje   = 'La variable "%s" se usa en "%s" sin haber sido declarada.'
                                % (nodo_lhs.etiqueta, operador),
                    variable  = nodo_lhs.etiqueta,
                    linea     = nodo.linea,
                ))
            else:
                # Validar compatibilidad aritmetica
                op_base = operador[:-1]   # '+=' -> '+'
                resultado = TipoSemantico.resultado_aritmetico(
                    simbolo.tipo, tipo_rhs, op_base)
                if resultado == TipoSemantico.ERROR:
                    self.errores.append(ErrorSemantico(
                        categoria = ErrorSemantico.TIPO_INCOMPATIBLE,
                        mensaje   = 'Operacion "%s" incompatible entre tipos "%s" y "%s".'
                                    % (operador, simbolo.tipo, tipo_rhs),
                        variable  = nodo_lhs.etiqueta,
                        linea     = nodo.linea,
                    ))
            return tipo_rhs

        # ── Asignacion simple: declarar o actualizar tipo ─────────────────────
        nombre_lhs = nodo_lhs.etiqueta

        # El lhs puede ser una expresion compleja (ej: a[0] = ...) — solo
        # procesamos identificadores simples para la tabla de simbolos.
        if nodo_lhs.hijos:
            # Lhs con hijos: acceso indexado o de miembro, no declaramos
            self._visitar(nodo_lhs)
            return tipo_rhs

        simbolo_existente = self.tabla.buscar(nombre_lhs)

        if simbolo_existente is None:
            # Primera asignacion: declarar la variable
            nuevo_simbolo = Simbolo(
                nombre    = nombre_lhs,
                tipo      = tipo_rhs,
                categoria = 'variable',
                alcance   = self.tabla.scope_actual(),
            )
            self.tabla.declarar(nuevo_simbolo)
        else:
            # Variable ya declarada: actualizar tipo si es mas especifico
            # y reportar incompatibilidad si aplica
            tipo_prev = simbolo_existente.tipo

            # No reportar error si alguno de los tipos es DESCONOCIDO o ERROR
            # (error ya fue reportado mas abajo en el arbol)
            if (tipo_prev != TipoSemantico.DESCONOCIDO
                    and tipo_rhs != TipoSemantico.DESCONOCIDO
                    and tipo_prev != TipoSemantico.ERROR
                    and tipo_rhs  != TipoSemantico.ERROR):

                # Regla de compatibilidad:
                # int <- float y float <- int se permiten (Python es dinamico,
                # pero advertimos si es string <- int, etc.)
                incompatible = False
                if tipo_prev in (TipoSemantico.STRING,) and tipo_rhs not in (TipoSemantico.STRING, TipoSemantico.DESCONOCIDO):
                    incompatible = True
                elif tipo_rhs in (TipoSemantico.STRING,) and tipo_prev not in (TipoSemantico.STRING, TipoSemantico.DESCONOCIDO):
                    incompatible = True
                elif tipo_prev == TipoSemantico.BOOL and tipo_rhs not in (TipoSemantico.BOOL, TipoSemantico.INT, TipoSemantico.DESCONOCIDO):
                    incompatible = True

                if incompatible:
                    self.errores.append(ErrorSemantico(
                        categoria = ErrorSemantico.TIPO_INCOMPATIBLE,
                        mensaje   = 'La variable "%s" fue declarada como "%s" '
                                    'pero se le asigna un valor de tipo "%s".'
                                    % (nombre_lhs, tipo_prev, tipo_rhs),
                        variable  = nombre_lhs,
                        linea     = nodo.linea,
                    ))

            # Actualizar el tipo con el nuevo (permite reasignacion en Python)
            self.tabla.actualizar_tipo(nombre_lhs, tipo_rhs)

        return tipo_rhs

    def _visitar_if(self, nodo):
        """
        Estructura del nodo 'if':
            hijos[0] -> condicion (expresion)
            hijos[1] -> bloque then
            hijos[2] -> bloque else (opcional)
        """
        for hijo in nodo.hijos:
            self._visitar(hijo)
        return TipoSemantico.NONE

    def _visitar_while(self, nodo):
        """
        Estructura del nodo 'while':
            hijos[0] -> condicion
            hijos[1] -> bloque cuerpo
        """
        for hijo in nodo.hijos:
            self._visitar(hijo)
        return TipoSemantico.NONE

    def _visitar_for(self, nodo):
        """
        Estructura del nodo 'for':
            hijos[0] -> variable de iteracion (ID)
            hijos[1] -> expresion iterable
            hijos[2] -> bloque cuerpo
        """
        if not nodo.hijos:
            return TipoSemantico.NONE

        # Declarar la variable de iteracion
        var_iter = nodo.hijos[0]
        if not var_iter.hijos:   # es un identificador simple
            simbolo = self.tabla.buscar(var_iter.etiqueta)
            if simbolo is None:
                self.tabla.declarar(Simbolo(
                    nombre    = var_iter.etiqueta,
                    tipo      = TipoSemantico.DESCONOCIDO,
                    categoria = 'variable',
                    alcance   = self.tabla.scope_actual(),
                ))

        for hijo in nodo.hijos[1:]:
            self._visitar(hijo)

        return TipoSemantico.NONE

    def _visitar_return(self, nodo):
        """Verifica que 'return' este dentro de una funcion."""
        if self._dentro_funcion == 0:
            self.errores.append(ErrorSemantico(
                categoria = ErrorSemantico.RETORNO_FUERA_FUNC,
                mensaje   = 'Sentencia "return" encontrada fuera del cuerpo de una funcion.',
                linea     = nodo.linea,
            ))
        if nodo.hijos:
            return self._visitar(nodo.hijos[0])
        return TipoSemantico.NONE

    def _visitar_op_aritmetico(self, nodo):
        """
        Evalua una operacion aritmetica en POSTORDEN:
        primero los operandos, luego el operador.
        """
        if len(nodo.hijos) < 2:
            if nodo.hijos:
                return self._visitar(nodo.hijos[0])
            return TipoSemantico.DESCONOCIDO

        tipo_izq = self._visitar(nodo.hijos[0])
        tipo_der = self._visitar(nodo.hijos[1])
        operador = nodo.etiqueta

        resultado = TipoSemantico.resultado_aritmetico(tipo_izq, tipo_der, operador)

        if resultado == TipoSemantico.ERROR:
            self.errores.append(ErrorSemantico(
                categoria = ErrorSemantico.TIPO_INCOMPATIBLE,
                mensaje   = 'Operacion "%s" no es valida entre tipos "%s" y "%s".'
                            % (operador, tipo_izq, tipo_der),
                linea     = nodo.linea,
            ))
            return TipoSemantico.ERROR

        return resultado

    def _visitar_llamada(self, nodo):
        """
        Procesamiento de llamada a funcion.
        El nodo tiene etiqueta 'nombre()' y sus hijos son los argumentos.

        Pasos:
            1. Extraer el nombre de la funcion (quitar los '()')
            2. Buscar en builtins o en la tabla de simbolos
            3. Verificar aridad si es posible
            4. Visitar argumentos para propagar errores internos
        """
        # Extraer nombre: 'calcular()' -> 'calcular'
        nombre_raw = nodo.etiqueta
        nombre_func = nombre_raw[:-2] if nombre_raw.endswith('()') else nombre_raw

        # Visitar argumentos (postorden sobre los hijos)
        for hijo in nodo.hijos:
            self._visitar(hijo)

        # ── Buscar en builtins ────────────────────────────────────────────────
        if nombre_func in _BUILTINS:
            return _BUILTINS[nombre_func]

        # ── Buscar en tabla de simbolos ───────────────────────────────────────
        simbolo = self.tabla.buscar(nombre_func)

        if simbolo is None:
            # Puede ser un metodo de objeto (nombre con '.') — no reportar
            if '.' not in nombre_func:
                self.errores.append(ErrorSemantico(
                    categoria = ErrorSemantico.VAR_NO_DECLARADA,
                    mensaje   = 'La funcion "%s" se llama sin haber sido declarada.'
                                % nombre_func,
                    variable  = nombre_func,
                    linea     = nodo.linea,
                ))
            return TipoSemantico.DESCONOCIDO

        # Verificar que el simbolo sea efectivamente una funcion
        if simbolo.categoria not in ('funcion',):
            self.errores.append(ErrorSemantico(
                categoria = ErrorSemantico.USO_INVALIDO,
                mensaje   = '"%s" es una %s, no una funcion. No puede ser llamada.'
                            % (nombre_func, simbolo.categoria),
                variable  = nombre_func,
                linea     = nodo.linea,
            ))
            return TipoSemantico.ERROR

        # Verificar aridad
        if simbolo.num_params is not None:
            num_args = len(nodo.hijos)
            if num_args != simbolo.num_params:
                self.errores.append(ErrorSemantico(
                    categoria = ErrorSemantico.ARIDAD_INCORRECTA,
                    mensaje   = 'La funcion "%s" espera %d argumento(s) pero recibio %d.'
                                % (nombre_func, simbolo.num_params, num_args),
                    variable  = nombre_func,
                    linea     = nodo.linea,
                ))

        # Tipo de retorno desconocido (no tenemos anotaciones de tipo)
        return TipoSemantico.DESCONOCIDO

    def _visitar_hoja(self, nodo):
        """
        Procesamiento de nodo hoja: literal o identificador.
        Los nodos hoja no tienen hijos.
        """
        et = nodo.etiqueta

        # Intentar inferir como literal
        tipo_literal = TipoSemantico.desde_literal(et)
        if tipo_literal != TipoSemantico.DESCONOCIDO:
            return tipo_literal

        # Es un identificador: buscar en tabla de simbolos
        # Ignorar identificadores que son nombres de builtins conocidos
        if et in _BUILTINS:
            return _BUILTINS[et]

        # Ignorar tokens que no son identificadores de usuario
        # (operadores, delimitadores que lleguen como hojas)
        if not et.isidentifier():
            return TipoSemantico.DESCONOCIDO

        simbolo = self.tabla.buscar(et)
        if simbolo is None:
            self.errores.append(ErrorSemantico(
                categoria = ErrorSemantico.VAR_NO_DECLARADA,
                mensaje   = 'La variable "%s" se usa sin haber sido declarada previamente.' % et,
                variable  = et,
                linea     = nodo.linea,
            ))
            return TipoSemantico.ERROR

        return simbolo.tipo

    def _visitar_hijos(self, nodo):
        """Visita todos los hijos de un nodo sin procesar el nodo en si."""
        for hijo in nodo.hijos:
            self._visitar(hijo)

    # ── Reporte de resultados ─────────────────────────────────────────────────

    def reporte_texto(self):
        """
        Genera un reporte legible de errores y tabla de simbolos.
        Util para debug o exportacion a texto plano.
        """
        lineas = []
        lineas.append('=' * 60)
        lineas.append('  ANALISIS SEMANTICO — REPORTE')
        lineas.append('=' * 60)

        # Tabla de simbolos
        lineas.append('\nTABLA DE SIMBOLOS:')
        lineas.append('%-20s %-12s %-12s %-12s %s' % (
            'Nombre', 'Tipo', 'Categoria', 'Alcance', 'Linea'))
        lineas.append('-' * 70)
        for fila in self.tabla.exportar_tabla():
            lineas.append('%-20s %-12s %-12s %-12s %s' % (
                fila['nombre'], fila['tipo'],
                fila['categoria'], fila['alcance'], fila['linea']))

        # Errores
        lineas.append('\nERRORES SEMANTICOS (%d):' % len(self.errores))
        if not self.errores:
            lineas.append('  Ninguno.')
        else:
            for i, error in enumerate(self.errores, 1):
                lineas.append('  %d. %s' % (i, str(error)))

        lineas.append('=' * 60)
        return '\n'.join(lineas)
