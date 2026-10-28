"""
autotile.py - organiza as janelas sozinho no Windows (estilo Linux tiling).

Uso:   python autotile.py
Parar: Ctrl+C  (ou feche o terminal)
Sem terminal: pythonw autotile.py   (fecha pelo Gerenciador de Tarefas)

Sem dependências externas, só o Python 3 padrão no Windows.
"""
import ctypes
import math
import time
from ctypes import wintypes as w

# ---------------- configurações ----------------
GAP = 8              # espaço (px) entre janelas e bordas da tela
INTERVALO = 0.3      # de quanto em quanto tempo (s) checar janelas novas
# -----------------------------------------------

user32 = ctypes.WinDLL("user32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")
kernel32 = ctypes.WinDLL("kernel32")

# DPI: sem isso as coordenadas ficam erradas em telas com escala > 100%
try:
    ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
except Exception:
    user32.SetProcessDPIAware()

# ---- assinaturas (importante em Python 64 bits) ----
WNDENUMPROC = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, w.LPARAM]
for fn in ("IsWindowVisible", "IsIconic", "IsZoomed", "GetWindowTextLengthW"):
    getattr(user32, fn).argtypes = [w.HWND]
user32.GetWindowLongW.argtypes = [w.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindow.argtypes = [w.HWND, w.UINT]
user32.GetWindow.restype = w.HWND
user32.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
user32.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
user32.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, w.UINT]
user32.MonitorFromWindow.argtypes = [w.HWND, w.DWORD]
user32.MonitorFromWindow.restype = w.HANDLE
user32.GetMonitorInfoW.argtypes = [w.HANDLE, ctypes.c_void_p]
dwmapi.DwmGetWindowAttribute.argtypes = [w.HWND, w.DWORD, ctypes.c_void_p, w.DWORD]
kernel32.GetConsoleWindow.restype = w.HWND

GWL_STYLE, GWL_EXSTYLE = -16, -20
WS_THICKFRAME = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
GW_OWNER = 4
DWMWA_EXTENDED_FRAME_BOUNDS, DWMWA_CLOAKED = 9, 14
SWP_NOZORDER, SWP_NOACTIVATE = 0x0004, 0x0010
MONITOR_DEFAULTTONEAREST = 2

IGNORAR_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", w.DWORD), ("rcMonitor", w.RECT),
                ("rcWork", w.RECT), ("dwFlags", w.DWORD)]


def classe(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def deve_organizar(hwnd, meu_console):
    """Decide se a janela é uma janela 'normal' de aplicativo."""
    if hwnd == meu_console:
        return False
    if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd) or user32.IsZoomed(hwnd):
        return False
    if user32.GetWindowTextLengthW(hwnd) == 0:
        return False
    if user32.GetWindow(hwnd, GW_OWNER):           # diálogos/popup de outra janela
        return False
    estilo = user32.GetWindowLongW(hwnd, GWL_STYLE)
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if not (estilo & WS_THICKFRAME):               # não redimensionável (diálogos etc.)
        return False
    if ex & (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE):
        return False
    cloaked = ctypes.c_int(0)                      # janelas "fantasma" do UWP / outras áreas virtuais
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), 4)
    if cloaked.value:
        return False
    if classe(hwnd) in IGNORAR_CLASSES:
        return False
    return True


def listar_janelas():
    meu_console = kernel32.GetConsoleWindow()
    achadas = []

    @WNDENUMPROC
    def cb(hwnd, _):
        if deve_organizar(hwnd, meu_console):
            achadas.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return achadas


def area_util(hwnd):
    """Retorna (id_do_monitor, left, top, right, bottom) da área sem a barra de tarefas."""
    mon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(mon, ctypes.byref(info))
    r = info.rcWork
    return (mon, r.left, r.top, r.right, r.bottom)


def mover(hwnd, x, y, largura, altura):
    """Move a janela compensando as bordas invisíveis do Windows 10/11."""
    rect = w.RECT()
    frame = w.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    ok = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS,
                                      ctypes.byref(frame), ctypes.sizeof(frame))
    if ok == 0:
        esq = frame.left - rect.left
        topo = frame.top - rect.top
        dir_ = rect.right - frame.right
        base = rect.bottom - frame.bottom
    else:
        esq = topo = dir_ = base = 0
    user32.SetWindowPos(hwnd, None,
                        x - esq, y - topo,
                        largura + esq + dir_, altura + topo + base,
                        SWP_NOZORDER | SWP_NOACTIVATE)


def organizar(janelas, area):
    """Grade: calcula linhas/colunas; a última linha se estica pra preencher."""
    _, esq, topo, dir_, base = area
    n = len(janelas)
    if n == 0:
        return
    esq += GAP; topo += GAP; dir_ -= GAP; base -= GAP
    larg_total, alt_total = dir_ - esq, base - topo

    colunas = math.ceil(math.sqrt(n))
    linhas = math.ceil(n / colunas)
    i = 0
    for r in range(linhas):
        qtd = min(colunas, n - i)
        y0 = topo + r * alt_total // linhas
        y1 = topo + (r + 1) * alt_total // linhas
        for c in range(qtd):
            x0 = esq + c * larg_total // qtd
            x1 = esq + (c + 1) * larg_total // qtd
            mover(janelas[i], x0 + GAP // 2, y0 + GAP // 2,
                  (x1 - x0) - GAP, (y1 - y0) - GAP)
            i += 1


def main():
    print("Auto-tile rodando. Ctrl+C pra parar.")
    ordem = []          # mantém a ordem em que as janelas foram abertas
    assinatura = None   # (janela, monitor) -> só reorganiza quando isso muda

    while True:
        try:
            atuais = listar_janelas()
            conjunto = set(atuais)
            ordem = [h for h in ordem if h in conjunto]
            ordem += [h for h in reversed(atuais) if h not in ordem]

            areas = {h: area_util(h) for h in ordem}
            nova = tuple((h, areas[h][0]) for h in ordem)

            if nova != assinatura:
                assinatura = nova
                por_monitor = {}
                for h in ordem:
                    por_monitor.setdefault(areas[h], []).append(h)
                for area, jans in por_monitor.items():
                    organizar(jans, area)
        except Exception as e:  # nunca deixa o script morrer por causa de uma janela estranha
            print("erro:", e)
        time.sleep(INTERVALO)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nParado.")