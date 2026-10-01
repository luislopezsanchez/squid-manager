"""Neutraliza «inyección de fórmulas» en las exportaciones CSV/XLSX.

Una celda que empieza por `=`, `+`, `-` o `@` la interpreta Excel/LibreOffice como una fórmula:
un usuario, un dominio o una URL con ese comienzo (los controla quien navega) ejecutaría la
fórmula al abrir la exportación. Se antepone una comilla simple, que la hoja de cálculo no muestra.
"""

_PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")


def celda(valor):
    if isinstance(valor, str) and len(valor) > 1 and valor[0] in _PELIGROSOS:
        return "'" + valor
    return valor


def fila(valores):
    return [celda(v) for v in valores]
