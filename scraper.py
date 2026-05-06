"""
Scraper de cotações do café - CCCV
Gera cotacoes.json com os dados do mês corrente
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

URL = "https://www.cccv.org.br/cotacao/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def parse_brl(text):
    """Converte string de valor brasileiro para float."""
    if not text:
        return None
    clean = text.strip().replace(".", "").replace(",", ".")
    try:
        return float(clean)
    except ValueError:
        return None

def scrape():
    print(f"[{datetime.now().isoformat()}] Buscando cotações em {URL}")
    resp = requests.get(URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Detecta mês/ano do título
    mes_ano_str = ""
    mes_num = datetime.now().month
    ano_num = datetime.now().year

    for tag in soup.find_all(["h1","h2","h3","h4","h5","h6","p","strong","b"]):
        txt = tag.get_text(strip=True)
        m = re.search(r"(\w+)\s+de\s+(\d{4})", txt, re.IGNORECASE)
        if m:
            mes_ano_str = f"{m.group(1)} {m.group(2)}"
            ano_num = int(m.group(2))
            meses_map = {
                "janeiro":1,"fevereiro":2,"março":3,"marco":3,
                "abril":4,"maio":5,"junho":6,"julho":7,"agosto":8,
                "setembro":9,"outubro":10,"novembro":11,"dezembro":12
            }
            mes_num = meses_map.get(m.group(1).lower(), mes_num)
            break

    # Extrai tabela de cotações
    cotacoes = []
    media_dura = None
    media_rio = None
    media_conilon = None

    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 4:
                continue

            # Linha de média
            if "média" in cells[0].lower():
                media_dura    = parse_brl(cells[1])
                media_rio     = parse_brl(cells[2])
                media_conilon = parse_brl(cells[3])
                continue

            # Linha de dia
            try:
                dia = int(cells[0])
            except ValueError:
                continue

            if dia < 1 or dia > 31:
                continue

            dura    = parse_brl(cells[1])
            rio     = parse_brl(cells[2])
            conilon = parse_brl(cells[3])

            if dura is None and rio is None and conilon is None:
                continue

            cotacoes.append({
                "dia":     dia,
                "dura":    dura,
                "rio":     rio,
                "conilon": conilon
            })

    # Calcula médias se não vieram da tabela
    def calc_media(campo):
        vals = [c[campo] for c in cotacoes if c[campo] is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    if media_dura    is None: media_dura    = calc_media("dura")
    if media_rio     is None: media_rio     = calc_media("rio")
    if media_conilon is None: media_conilon = calc_media("conilon")

    resultado = {
        "atualizado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "mes":           mes_ano_str or f"{mes_num:02d}/{ano_num}",
        "mes_num":       mes_num,
        "ano":           ano_num,
        "media_dura":    media_dura,
        "media_rio":     media_rio,
        "media_conilon": media_conilon,
        "cotacoes":      sorted(cotacoes, key=lambda x: x["dia"])
    }

    print(f"  → {len(cotacoes)} dias coletados")
    print(f"  → Média Arábica Dura: {media_dura}")
    print(f"  → Média Arábica Rio:  {media_rio}")
    print(f"  → Média Conilon:      {media_conilon}")

    with open("cotacoes.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(f"  → cotacoes.json salvo com sucesso!")
    return resultado

if __name__ == "__main__":
    scrape()
