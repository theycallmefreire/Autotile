"""
autotile_tray.py - Auto-Tile em segundo plano, com ícone na bandeja do sistema.

Clique esquerdo no ícone: liga/desliga o auto-tile.
Clique direito: menu (Ativo, Reorganizar agora, Sair).
Precisa do autotile.py na mesma pasta (o PyInstaller embute tudo no .exe).
"""
import ctypes
import sys
import threading
import time

import pystray
from PIL import Image, ImageDraw

import autotile as at

# ---------- só permite uma cópia rodando ----------
_mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "AutoTileSingleInstance")
if ctypes.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    sys.exit(0)

estado = {"ativo": True, "forcar": False, "rodando": True}


def loop_principal():
    ordem = []
    assinatura = None
    while estado["rodando"]:
        if estado["ativo"]:
            try:
                atuais = at.listar_janelas()
                conjunto = set(atuais)
                ordem = [h for h in ordem if h in conjunto]
                ordem += [h for h in reversed(atuais) if h not in ordem]

                areas = {h: at.area_util(h) for h in ordem}
                nova = tuple((h, areas[h][0]) for h in ordem)

                if estado["forcar"] or nova != assinatura:
                    estado["forcar"] = False
                    assinatura = nova
                    por_monitor = {}
                    for h in ordem:
                        por_monitor.setdefault(areas[h], []).append(h)
                    for area, jans in por_monitor.items():
                        at.organizar(jans, area)
            except Exception:
                pass  # janela estranha não pode derrubar o programa
        time.sleep(at.INTERVALO)


def criar_icone(ativo=True):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fundo = (37, 99, 235, 255) if ativo else (113, 113, 122, 255)
    d.rounded_rectangle((2, 2, 62, 62), radius=10, fill=fundo)
    d.rectangle((10, 10, 29, 29), fill="white")
    d.rectangle((35, 10, 54, 29), fill="white")
    d.rectangle((10, 35, 54, 54), fill="white")
    return img


def alternar(icon, item):
    estado["ativo"] = not estado["ativo"]
    if estado["ativo"]:
        estado["forcar"] = True
    icon.icon = criar_icone(estado["ativo"])


def reorganizar(icon, item):
    estado["forcar"] = True


def sair(icon, item):
    estado["rodando"] = False
    icon.stop()


def main():
    threading.Thread(target=loop_principal, daemon=True).start()
    menu = pystray.Menu(
        pystray.MenuItem("Auto-Tile ativo", alternar,
                         checked=lambda item: estado["ativo"], default=True),
        pystray.MenuItem("Reorganizar agora", reorganizar),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", sair),
    )
    pystray.Icon("AutoTile", criar_icone(True), "Auto-Tile", menu).run()


if __name__ == "__main__":
    main()