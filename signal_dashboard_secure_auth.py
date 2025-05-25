import streamlit as st
import pandas as pd
import requests
import numpy as np
import time
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from datetime import datetime

# --- Auth ---
with open("config.yaml") as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"]
)

# LOGIN dans la sidebar
authenticator.login(location="sidebar", fields={"Form name": "Connexion"})

authentication_status = st.session_state.get("authentication_status")
name = st.session_state.get("name")
username = st.session_state.get("username")

if authentication_status:
    st.set_page_config(page_title="ALT vs BTC – Accès sécurisé", layout="wide")
    st.title("📊 ALT vs BTC – Dashboard sécurisé Long & Short")

    st.sidebar.success(f"Connecté en tant que {name}")
    authenticator.logout("Se déconnecter", "sidebar")

    def fetch_kline(symbol):
        try:
            end_time = int(time.time() * 1000)
            start_time = end_time - 48 * 3600 * 1000
            url = f"https://fapi.binance.com/fapi/v1/klines"
            params = {
                "symbol": symbol,
                "interval": "1h",
                "startTime": start_time,
                "endTime": end_time,
                "limit": 1000
            }
            r = requests.get(url, params=params)
            if r.status_code == 200 and isinstance(r.json(), list):
                data = r.json()
                if len(data) > 0 and isinstance(data[0], list):
                    df = pd.DataFrame(data, columns=[
                        "timestamp", "open", "high", "low", "close", "volume", "close_time",
                        "quote_asset_volume", "number_of_trades", "taker_buy_base_asset_volume",
                        "taker_buy_quote_asset_volume", "ignore"
                    ])
                    return df
        except:
            pass
        return None

    def compute_returns(prices):
        return prices.pct_change().fillna(0)

    def get_symbols():
        try:
            info = requests.get("https://fapi.binance.com/fapi/v1/exchangeInfo").json()
            return [s["symbol"] for s in info.get("symbols", []) if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT"]
        except:
            return []

    def analyze_behavior():
        st.markdown("### 🔐 Analyse ALT vs BTC – Signaux sécurisés")
        st.info(\"""
Détection de signaux LONG & SHORT stratégiques.
        """)

        symbols = get_symbols()
        btc_df = fetch_kline("BTCUSDT")

        if btc_df is None or btc_df.empty:
            st.error("Erreur chargement BTC.")
            return

        btc_df["close"] = btc_df["close"].astype(float)
        btc_df["returns"] = compute_returns(btc_df["close"])

        update_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        st.markdown(f"**🕒 Mise à jour :** `{update_time}`")

        longs = []
        shorts = []

        for symbol in symbols:
            if symbol == "BTCUSDT":
                continue
            df = fetch_kline(symbol)
            if df is None or df.empty:
                continue
            try:
                df["close"] = df["close"].astype(float)
                df["returns"] = compute_returns(df["close"])
                corr_now = df["returns"][-24:].corr(btc_df["returns"][-24:])
                corr_prev = df["returns"][-48:-24].corr(btc_df["returns"][-48:-24:])
                delta_corr = corr_now - corr_prev

                last_price = df["close"].iloc[-1]
                ret_24h = (last_price - df["close"].iloc[-25]) / df["close"].iloc[-25] * 100
                high_24h = df["high"].astype(float)[-24:].max()
                low_24h = df["low"].astype(float)[-24:].min()

                if delta_corr < -0.15 and ret_24h > 2:
                    longs.append({
                        "Token": symbol,
                        "Prix": round(last_price, 4),
                        "Rendement 24h (%)": round(ret_24h, 2),
                        "Δ Corrélation": round(delta_corr, 2),
                        "TP (haut)": round(high_24h, 4),
                        "SL (bas)": round(low_24h, 4)
                    })

                if delta_corr > 0.1 and ret_24h < -2:
                    shorts.append({
                        "Token": symbol,
                        "Prix": round(last_price, 4),
                        "Rendement 24h (%)": round(ret_24h, 2),
                        "Δ Corrélation": round(delta_corr, 2),
                        "TP (bas)": round(low_24h, 4),
                        "SL (haut)": round(high_24h, 4)
                    })
            except:
                continue
            time.sleep(0.05)

        if longs:
            st.subheader("🚀 Longs détectés")
            st.dataframe(pd.DataFrame(longs).sort_values(by="Δ Corrélation"))

        if shorts:
            st.subheader("📉 Shorts détectés")
            st.dataframe(pd.DataFrame(shorts).sort_values(by="Δ Corrélation", ascending=False))

        if not longs and not shorts:
            st.warning("Aucun signal détecté.")

    analyze_behavior()
