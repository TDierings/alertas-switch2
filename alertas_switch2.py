"""
Alertas de preço (Switch 2 e jogos) com notificação no telemóvel via ntfy.sh

Como usar:
  1. pip install requests
  2. Instala a app "ntfy" no telemóvel e subscreve o NTFY_TOPIC abaixo
  3. Preenche PRODUTOS com o link de cada produto em cada loja + o preço-alvo
  4. python alertas_switch2.py   (deixa a correr, ou agenda com cron / Agendador de Tarefas)
"""
import json
import os
import random
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

# ---------- CONFIGURAÇÃO ----------
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")  # vem do "Secret" do GitHub, nunca escrito aqui
INTERVALO_MIN = 20  # de quanto em quanto tempo verifica

PRODUTOS = [
    # Preços-alvo são exemplos: ajusta ao que queres pagar.
    {"nome": "Switch 2 - PCDiga", "url": "https://www.pcdiga.com/imagem-e-som/consolas/nintendo/consola-nintendo-switch-2-10015151-45496321444", "alvo": 450.0},
    {"nome": "Switch 2 - Worten", "url": "https://www.worten.pt/produtos/consola-nintendo-switch-2-8284633", "alvo": 450.0},
    # {"nome": "Switch 2 - Fnac", "url": "https://www.fnac.pt/Nintendo-Switch-2-Consola-Consola/a12728455", "alvo": 450.0},
    {"nome": "Switch 2 - Continente", "url": "https://www.continente.pt/produto/consola-nintendo-switch-2-nintendo-nintendo-8284633.html", "alvo": 450.0},
    # {"nome": "Switch 2 - PcComponentes", "url": "https://www.pccomponentes.pt/nintendo-switch-2-256gb-preto", "alvo": 450.0},
    {"nome": "Switch 2 - Chipman", "url": "https://chipman.pt/consolas-portateis/nintendo-consola-portatil-switch-2-10015151-256-preto", "alvo": 450.0},
    {"nome": "Switch 2 - On4tech", "url": "https://www.on4tech.pt/p3-p-468821-nintendo-consola-nintendo-switch-2-pt", "alvo": 450.0},
    {"nome": "Switch 2 - Auchan", "url": "https://www.auchan.pt/pt/tecnologia/gaming/consolas-e-jogos/nintendo/consolas-nintendo/consola-nintendo-switch-2/4070180.html", "alvo": 450.0},
    {"nome": "Switch 2 - Tradeinn", "url": "https://www.tradeinn.com/techinn/pt/nintendo-switch-2/142080233/p?id_producte=148012281", "alvo": 450.0},
    # {"nome": "Switch 2 - Castro Electronica", "url": "https://www.castroelectronica.pt/product/consola-portatil-switch-2--nintendo", "alvo": 450.0},
    {"nome": "Switch 2 - Kontrolsat", "url": "https://www.kontrolsat.com/pt/consolas-nintendo/consola-nintendo-switch-2-256gb-4k-hdr-120hz-16128.html", "alvo": 450.0},
    # {"nome": "Switch 2 + Mario Kart - Fnac", "url": "https://www.fnac.pt/Consola-Nintendo-Switch-2-Mario-Kart-World-Consola-Consola/a14737524", "alvo": 490.0},
    {"nome": "Switch 2 + Mario Kart - Continente", "url": "https://www.continente.pt/produto/consola-switch-2-jogo-mario-kart-world-nintendo-8284635.html", "alvo": 490.0},
]

# Filtro: ignora produtos cujo título indique o modelo com bateria amovível.
# (BTR é a sigla que a PcComponentes usa nesses modelos.)
EXCLUIR = [
    r"bateria (amovivel|extraivel|extraible|substituivel|removivel)",
    r"removable battery",
    r"\bbtr\b",
]
# -----------------------------------

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "pt-PT,pt;q=0.9",
}
ESTADO = Path("estado.json")


def para_float(valor):
    s = str(valor).strip().replace("€", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def procurar_preco(dados):
    """Procura recursivamente um preço em dados JSON-LD."""
    if isinstance(dados, dict):
        for chave in ("price", "lowPrice"):
            if chave in dados:
                p = para_float(dados[chave])
                if p:
                    return p
        for v in dados.values():
            p = procurar_preco(v)
            if p:
                return p
    elif isinstance(dados, list):
        for item in dados:
            p = procurar_preco(item)
            if p:
                return p
    return None


def achar_preco(html):
    # 1) dados estruturados (a maioria das lojas tem)
    for bloco in re.findall(
        r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S
    ):
        try:
            p = procurar_preco(json.loads(bloco))
        except ValueError:
            continue
        if p:
            return p
    # 2) meta tags
    m = re.search(
        r'(?:product:price:amount|itemprop=["\']price["\'])[^>]*?content=["\']([\d.,]+)["\']',
        html,
    )
    return para_float(m.group(1)) if m else None


def normalizar(texto):
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def achar_titulo(html):
    partes = re.findall(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    partes += re.findall(
        r'property=["\']og:title["\'][^>]*content=["\']([^"\']*)["\']', html, re.I
    )
    return " | ".join(p.strip() for p in partes)


def excluido(titulo):
    t = normalizar(titulo)
    return any(re.search(padrao, t) for padrao in EXCLUIR)


def notificar(titulo, texto, url):
    if not NTFY_TOPIC:
        print('[aviso] NTFY_TOPIC em falta: alerta nao enviado')
        return
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=texto.encode("utf-8"),
        headers={"Title": titulo, "Click": url, "Priority": "high"},
        timeout=15,
    )


def verificar():
    estado = json.loads(ESTADO.read_text()) if ESTADO.exists() else {}
    for p in PRODUTOS:
        try:
            r = requests.get(p["url"], headers=HEADERS, timeout=20)
            r.raise_for_status()
            preco = achar_preco(r.text)
            titulo = achar_titulo(r.text)
        except Exception as e:
            print(f"[erro] {p['nome']}: {e}")
            continue
        if excluido(titulo):
            print(f"[ignorado] {p['nome']}: modelo com bateria amovivel ({titulo[:60]})")
            continue
        if preco is None:
            print(f"[?] {p['nome']}: preço não encontrado (site pode precisar de outro método)")
            continue
        antes = estado.get(p["url"])
        print(f"[ok] {p['nome']}: {preco:.2f} EUR (antes: {antes}) | {titulo[:50]}")
        baixou = antes is None or preco < antes - 0.01
        if preco <= p["alvo"] and baixou:
            notificar(
                "Promocao encontrada",
                f"{p['nome']}: {preco:.2f} EUR (alvo {p['alvo']:.2f})",
                p["url"],
            )
        estado[p["url"]] = preco
        time.sleep(random.uniform(3, 8))  # evita pedidos em rajada
    ESTADO.write_text(json.dumps(estado))


if __name__ == "__main__":
    if "--uma-vez" in sys.argv:  # modo GitHub: verifica uma vez e termina
        verificar()
    else:
        while True:
            verificar()
            time.sleep(INTERVALO_MIN * 60)
