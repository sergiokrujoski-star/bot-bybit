import os
import threading
import time
from flask import Flask
import pandas as pd
import pandas_ta as ta
import requests
from pybit.unified_trading import HTTP

# ==========================================
# SERVIDOR FLASK (MANTENER RENDER ACTIVO)
# ==========================================
app = Flask(__name__)


@app.route("/")
def health_check():
    return "Bot de Trading Bybit activo 24/7", 200


# ==========================================
# 1. CREDENCIALES Y CONFIGURACIÓN
# ==========================================
API_KEY = os.getenv("BYBIT_API_KEY")
SECRET_KEY = os.getenv("BYBIT_SECRET_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SYMBOL = "BTCUSDT"
LEVERAGE = "2"

session = HTTP(
    demo=True, api_key=API_KEY, api_secret=SECRET_KEY, recv_window=10000
)


# ==========================================
# 2. FUNCIÓN DE NOTIFICACIÓN TELEGRAM
# ==========================================
def enviar_alerta_telegram(mensaje):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Faltan credenciales de Telegram.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown",
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code != 200:
            print(f"⚠️ Error de Telegram ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")


# Configurar apalancamiento al iniciar
try:
    session.set_leverage(
        category="linear",
        symbol=SYMBOL,
        buyLeverage=LEVERAGE,
        sellLeverage=LEVERAGE,
    )
    print(f"Apalancamiento ajustado a {LEVERAGE}x en Bybit Demo.")
except Exception as e:
    print(f"Aviso sobre apalancamiento: {e}")


# ==========================================
# 3. OBTENCIÓN DE DATOS E INDICADORES
# ==========================================
def obtener_datos_e_indicadores():
    response = session.get_kline(
        category="linear", symbol=SYMBOL, interval="60", limit=200
    )

    klines = response["result"]["list"]
    df = pd.DataFrame(
        klines,
        columns=[
            "timestamp",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
            "Turnover",
        ],
    )
    df = df.iloc[::-1].reset_index(drop=True)

    df["Close"] = df["Close"].astype(float)
    df["High"] = df["High"].astype(float)
    df["Low"] = df["Low"].astype(float)

    # Indicadores técnicos
    df["ma5"] = ta.sma(df["Close"], length=5)
    df["ma10"] = ta.sma(df["Close"], length=10)
    df["ma20"] = ta.sma(df["Close"], length=20)
    df["ma200"] = ta.sma(df["Close"], length=200)
    df["rsi"] = ta.rsi(df["Close"], length=14)

    dmi_df = ta.adx(df["High"], df["Low"], df["Close"], length=14)
    df["adx"] = dmi_df["ADX_14"]
    df["plus_di"] = dmi_df["DMP_14"]
    df["minus_di"] = dmi_df["DMN_14"]

    # Variación porcentual en las últimas 24 horas (24 velas de 1h)
    df["change_24h"] = df["Close"].pct_change(periods=24) * 100

    return df


# ==========================================
# 4. BUCLE PRINCIPAL DEL BOT
# ==========================================
def ejecutar_bot():
    print("Bot iniciado correctamente. Monitoreando Bybit Testnet...\n")

    enviar_alerta_telegram(
        f"🟢 *Bot de Trading Iniciado*\n"
        f"• *Entorno:* Bybit Demo / Testnet\n"
        f"• *Par:* {SYMBOL}\n"
        f"• *Temporalidad:* 1 Hora"
    )

    while True:
        try:
            df = obtener_datos_e_indicadores()

            # Datos de la última vela
            price = df["Close"].iloc[-1]
            ma5 = df["ma5"].values
            ma10 = df["ma10"].values
            ma20 = df["ma20"].values
            ma200 = df["ma200"].values
            rsi = df["rsi"].values
            adx = df["adx"].values
            plus_di = df["plus_di"].values
            minus_di = df["minus_di"].values
            change_24h = df["change_24h"].iloc[-1]

            # Verificación de cruces
            cruce_bullish = (
                ma5[-2] < ma10[-2] and ma5[-1] > ma10[-1]
            ) or (ma5[-2] < ma20[-2] and ma5[-1] > ma20[-1])

            cruce_bearish = (
                ma5[-2] > ma10[-2] and ma5[-1] < ma10[-1]
            ) or (ma5[-2] > ma20[-2] and ma5[-1] < ma20[-1])

            # Condición LONG (Permite cruce O variación >= 2.0%)
            cond_long = (
                price > ma200[-1]
                and (cruce_bullish or change_24h >= 2.0)
                and ma5[-1] > ma20[-1]
                and plus_di[-1] > minus_di[-1]
                and rsi[-1] >= 45
            )

            # Condición SHORT
            cond_short = (
                price < ma200[-1]
                and (cruce_bearish or change_24h <= -2.0)
                and ma5[-1] < ma20[-1]
                and minus_di[-1] > plus_di[-1]
                and rsi[-1] <= 55
            )

            # TABLERO DE DIAGNÓSTICO EN CONSOLA
            print("\n--------------------------------------------------")
            print(
                f"⏰ Hora: {time.strftime('%H:%M:%S')} | BTC: ${price:,.2f}"
            )
            print(
                f"📈 Var. 24h: {change_24h:.2f}% (¿>= 2%?: {change_24h >= 2.0})"
            )
            print(f"⚔️ Cruce Bullish: {cruce_bullish}")
            print(f"📊 RSI: {rsi[-1]:.1f} | ADX: {adx[-1]:.1f}")
            print(f"🎯 ¿Activa LONG?: {cond_long}")
            print("--------------------------------------------------\n")

            positions = session.get_positions(
                category="linear", symbol=SYMBOL
            )
            pos_size = float(positions["result"]["list"][0]["size"])

            if pos_size == 0:
                if cond_long:
                    print("🚀 Entrada LONG detectada. Enviando orden...")
                    session.place_order(
                        category="linear",
                        symbol=SYMBOL,
                        side="Buy",
                        orderType="Market",
                        qty="0.01",
                    )
                    mensaje_long = (
                        f"🚨 *ENTRADA LONG DETECTADA (DEMO)* 🚨\n\n"
                        f"• *Par:* {SYMBOL}\n"
                        f"• *Precio:* ${price:,.2f}\n"
                        f"• *Variación 24h:* {change_24h:.2f}%\n"
                        f"• *RSI:* {rsi[-1]:.2f} | *ADX:* {adx[-1]:.2f}\n"
                        f"• *Orden:* Buy Market (0.01 BTC)"
                    )
                    enviar_alerta_telegram(mensaje_long)

                elif cond_short:
                    print("🔻 Entrada SHORT detectada. Enviando orden...")
                    session.place_order(
                        category="linear",
                        symbol=SYMBOL,
                        side="Sell",
                        orderType="Market",
                        qty="0.01",
                    )
                    mensaje_short = (
                        f"🚨 *ENTRADA SHORT DETECTADA (DEMO)* 🚨\n\n"
                        f"• *Par:* {SYMBOL}\n"
                        f"• *Precio:* ${price:,.2f}\n"
                        f"• *Variación 24h:* {change_24h:.2f}%\n"
                        f"• *RSI:* {rsi[-1]:.2f} | *ADX:* {adx[-1]:.2f}\n"
                        f"• *Orden:* Sell Market (0.01 BTC)"
                    )
                    enviar_alerta_telegram(mensaje_short)

            # Espera 60 segundos entre consultas para evitar bloqueos
            time.sleep(60)

        except Exception as e:
            # Pausa de seguridad de 5 minutos si ocurre un error de red o límite de API
            print(
                f"❌ Error en ejecución: {e}. Esperando 5 minutos para liberar Rate Limit..."
            )
            time.sleep(300)


# ==========================================
# INICIO DE HILOS Y SERVIDOR
# ==========================================
if __name__ == "__main__":
    bot_thread = threading.Thread(target=ejecutar_bot)
    bot_thread.daemon = True
    bot_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
