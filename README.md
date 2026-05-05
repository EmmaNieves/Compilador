# Analizador Lexico, Sintactico y Semantico
## Compiladores — Python 3 + Tkinter

### Estructura del proyecto

```
COMPILADOR-FIXED/
├── main.py              # Punto de entrada
├── lexer.py             # Analizador lexico + Buffer de entrada
├── parser_ast.py        # Analizador sintactico (descenso recursivo) + Generador AST
├── semantic_analyzer.py # Analizador semantico (NUEVO)
├── pdf_exporter.py      # Exportacion PDF (ReportLab)
├── gui.py               # Interfaz grafica (Tkinter)
└── requirements.txt     # Dependencias
```

### Instalacion de dependencias

```bash
pip install -r requirements.txt
```

Tambien necesitas **Graphviz** instalado en el sistema:
- Windows: https://graphviz.org/download/ — marca "Add to PATH"
- Linux: `sudo apt install graphviz`
- Mac: `brew install graphviz`

### Ejecucion

```bash
python main.py
```

---

### Fases del compilador implementadas

#### 1. Analisis Lexico (`lexer.py`)
- Tokenizacion completa de Python 3
- Deteccion de caracteres no reconocidos
- Buffer de doble centinela para lectura eficiente

#### 2. Analisis Sintactico (`parser_ast.py`)
- Parser de descenso recursivo
- Construccion del AST con `NodoAST`
- Visualizacion del arbol con Graphviz

#### 3. Analisis Semantico (`semantic_analyzer.py`)

**Tabla de Simbolos** con scopes anidados:
- Variables, funciones y parametros
- Tipo de dato inferido por cada simbolo
- Alcance (scope global vs. scope de funcion)

**Inferencia de tipos**:
- `int`, `float`, `string`, `bool`, `None`, `list`, `dict`, `funcion`, `desconocido`
- Propagacion de tipos en expresiones aritmeticas

**Errores detectados**:
| Categoria | Descripcion |
|---|---|
| Variable no declarada | Uso de variable antes de asignarla |
| Variable duplicada | Funcion declarada dos veces en el mismo scope |
| Incompatibilidad de tipos | `string = int`, `string + int`, etc. |
| Uso invalido de identificador | Llamar a una variable como si fuera funcion |
| Return fuera de funcion | `return` en el cuerpo del modulo |
| Numero incorrecto de argumentos | Llamada con aridad incorrecta |

**Estrategia de recorrido del AST**:
- **Preorden** para declaraciones: la funcion se registra en la tabla *antes* de recorrer su cuerpo (permite recursion).
- **Postorden** para expresiones: los operandos se evaluan antes que el operador para propagar tipos hacia arriba.

---

### Exportacion PDF
- PDF Lexico: tabla de tokens
- PDF Sintactico: imagen del arbol AST
- PDF Semantico: tabla de simbolos + errores semanticos
- PDF Completo: todo en un documento
