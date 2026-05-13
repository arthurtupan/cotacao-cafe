import json
import math
from datetime import datetime, timezone, timedelta

import yfinance as yf

MABREV = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

def safe_float(v, digits=2):
    try:
        f = float(v)
        return round(f, digits) if not math.isnan(f) else None
    except (TypeError, ValueError):
        return None

def venc_label(ticker_info):
    try:
        exp = ticker_info.get('expireDate')
        if exp:
            dt = datetime.fromtimestamp(exp)
            return f"{MABREV[dt.month-1]}/{str(dt.year)[2:]}"
    except Exception:
        pass
    return None

def scrape():
    # ── USD/BRL ──────────────────────────────────────────────
    brl_obj  = yf.Ticker("BRL=X")
    brl_hist = brl_obj.history(period="5d")

    usd_brl = usd_var = usd_min = usd_max = None
    usd_hora = datetime.now(tz=timezone(timedelta(hours=-3))).strftime("%d/%m/%Y")
    if not brl_hist.empty:
        last_brl = brl_hist.iloc[-1]
        usd_brl  = safe_float(last_brl['Close'], 4)
        usd_min  = safe_float(last_brl['Low'],  4)
        usd_max  = safe_float(last_brl['High'], 4)
        if len(brl_hist) >= 2:
            prev_brl = brl_hist.iloc[-2]['Close']
            usd_var  = safe_float(last_brl['Close'] - prev_brl, 4)

    # ── EUR/BRL ──────────────────────────────────────────────
    eur_obj  = yf.Ticker("EURBRL=X")
    eur_hist = eur_obj.history(period="5d")
    eur_brl = eur_var = None
    if not eur_hist.empty:
        last_eur = eur_hist.iloc[-1]
        eur_brl  = safe_float(last_eur['Close'], 4)
        if len(eur_hist) >= 2:
            eur_var = safe_float(last_eur['Close'] - eur_hist.iloc[-2]['Close'], 4)

    # ── ICE NY Coffee C (KC=F) ───────────────────────────────
    kc_obj  = yf.Ticker("KC=F")
    kc_info = kc_obj.info
    kc_hist = kc_obj.history(period="15d")

    ny = None
    if not kc_hist.empty:
        last_kc  = kc_hist.iloc[-1]
        preco_ny = safe_float(last_kc['Close'])
        abertura = safe_float(last_kc['Open'])
        maxima   = safe_float(last_kc['High'])
        minima   = safe_float(last_kc['Low'])
        volume   = int(last_kc['Volume']) if last_kc['Volume'] else 0
        var_dia  = var_pct = None
        if len(kc_hist) >= 2:
            prev_kc = safe_float(kc_hist.iloc[-2]['Close'])
            if prev_kc and preco_ny:
                var_dia = safe_float(preco_ny - prev_kc)
                var_pct = safe_float((preco_ny - prev_kc) / prev_kc * 100)
        venc_prox = venc_label(kc_info) or "—"
        ny_brl = safe_float(preco_ny * 132.277 / 100 * usd_brl, 0) if preco_ny and usd_brl else None
        ny = {
            "preco": preco_ny, "var_dia": var_dia, "var_pct": var_pct,
            "abertura": abertura, "maxima": maxima, "minima": minima,
            "volume": volume, "venc_prox": venc_prox, "ny_brl": ny_brl,
        }

    # ── Conilon: estimativa via KC + câmbio ──────────────────
    # Nota: não há fonte pública gratuita com API de conilon diário em R$/sc.
    # CEPEA bloqueado por Cloudflare; B3 exige renderização JS.
    # Estimativa: KC(US¢/lb) × 132,277lb/sc ÷ 100 × BRL × fator_conilon(0,60)
    b3 = None
    if ny and usd_brl:
        fator_conilon = 0.60
        lb_per_sc     = 132.277
        preco_est = safe_float(ny["preco"] * lb_per_sc / 100 * usd_brl * fator_conilon)
        b3 = {
            "preco": preco_est, "var_dia": None, "var_pct": ny.get("var_pct"),
            "abertura": None, "maxima": None, "minima": None,
            "volume": None, "venc_prox": None, "estimado": True,
        }

    # ── Histórico (últimos 7 pregões KC) ─────────────────────
    hist_labels, hist_ny, hist_b3 = [], [], []
    if not kc_hist.empty:
        for dt_idx, row in kc_hist.tail(7).iterrows():
            dt = dt_idx.to_pydatetime()
            hist_labels.append(f"{dt.day:02d}/{dt.month:02d}")
            hist_ny.append(safe_float(row['Close']))
        if usd_brl:
            fator_conilon, lb_per_sc = 0.60, 132.277
            hist_b3 = [
                safe_float(v * lb_per_sc / 100 * usd_brl * fator_conilon) if v else None
                for v in hist_ny
            ]

    # ── Contratos futuros ─────────────────────────────────────
    futuros = []
    try:
        for exp_str in (kc_obj.options or [])[:3]:
            dt_exp = datetime.strptime(exp_str, "%Y-%m-%d")
            venc   = f"{MABREV[dt_exp.month-1]}/{str(dt_exp.year)[2:]}"
            futuros.append({
                "bolsa": "ICE NY", "tag": "ny", "venc": venc,
                "preco":   ny["preco"]   if ny else None,
                "var_dia": ny["var_dia"] if ny else None,
                "var_pct": ny["var_pct"] if ny else None,
                "volume":  ny["volume"]  if ny else 0,
            })
    except Exception:
        if ny:
            futuros.append({
                "bolsa": "ICE NY", "tag": "ny",
                "venc": ny.get("venc_prox", "—"),
                "preco": ny["preco"], "var_dia": ny["var_dia"],
                "var_pct": ny["var_pct"], "volume": ny["volume"],
            })
    if b3:
        futuros.append({
            "bolsa": "Estimativa", "tag": "b3", "venc": "—",
            "preco": b3["preco"], "var_dia": None,
            "var_pct": b3["var_pct"], "volume": None,
        })

    agora = datetime.now(tz=timezone(timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M")
    return {
        "atualizado_em": agora,
        "fonte": "yfinance / ICE NY (KC=F) · USD/BRL (BRL=X) · EUR/BRL (EURBRL=X)",
        "usd_brl": usd_brl,
        "usd_var": usd_var,
        "usd_min": usd_min,
        "usd_max": usd_max,
        "usd_hora": usd_hora,
        "eur_brl": eur_brl,
        "eur_var": eur_var,
        "ny": ny,
        "b3": b3,
        "futuros": futuros,
        "hist_labels": hist_labels,
        "hist_ny": hist_ny,
        "hist_b3": hist_b3,
    }


if __name__ == "__main__":
    data = scrape()
    with open("bolsa.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"bolsa.json gerado: {data['atualizado_em']}")
    if data['ny']:
        pct = data['ny']['var_pct']
        print(f"  ICE NY:  {data['ny']['preco']} US¢/lb  ({pct:+.2f}%)")
    if data['b3']:
        pct_b3 = data['b3']['var_pct']
        pct_str = f"({pct_b3:+.2f}%)" if pct_b3 is not None else ""
        print(f"  Conilon: {data['b3']['preco']} R$/sc  {pct_str}  [estimativa]")
    print(f"  USD/BRL: {data['usd_brl']}")
    print(f"  EUR/BRL: {data['eur_brl']}")
    if data['ny'] and data['ny'].get('ny_brl'):
        print(f"  KC equiv BRL: R$ {data['ny']['ny_brl']}/sc")
