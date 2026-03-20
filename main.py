"""
errores sintacticos
comentarios
main.py - Punto de entrada de la aplicacion
Ejecutar: python main.py
"""

import sys
import os


def verificar_dependencias():
    """Verifica que las librerias necesarias esten instaladas."""
    faltantes = []
    try:
        import reportlab
    except ImportError:
        faltantes.append('reportlab')
    try:
        from PIL import Image
    except ImportError:
        faltantes.append('Pillow')
    try:
        import graphviz
    except ImportError:
        faltantes.append('graphviz')

    if faltantes:
        print('Faltan dependencias. Instalalas con:')
        print('  pip install ' + ' '.join(faltantes))
        sys.exit(1)

    # Advertencia si graphviz no esta en el PATH del sistema
    # (el modulo parser_ast lo buscara automaticamente)
    import shutil
    if not shutil.which('dot'):
        print('')
        print('ADVERTENCIA: graphviz no esta en el PATH del sistema.')
        print('El codigo intentara encontrarlo automaticamente.')
        print('Si el arbol no se genera, reinstala graphviz desde:')
        print('  https://graphviz.org/download/')
        print('y marca: Add Graphviz to the system PATH for all users')
        print('Luego cierra y vuelve a abrir VS Code.')
        print('')

    print('Dependencias OK.')


def main():
    print('=' * 60)
    print('  Analizador Lexico y Sintactico')
    print('  Compiladores - Python + Tkinter')
    print('=' * 60)

    verificar_dependencias()

    import tkinter as tk
    from gui import AplicacionCompilador

    root = tk.Tk()

    try:
        root.iconbitmap('icon.ico')
    except Exception:
        pass

    app = AplicacionCompilador(root)

    # Centrar la ventana
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry('+%d+%d' % ((sw - w) // 2, (sh - h) // 2))

    print('Interfaz iniciada. Cierra la ventana para terminar.')
    root.mainloop()
    print('Aplicacion cerrada.')


if __name__ == '__main__':
    main()
