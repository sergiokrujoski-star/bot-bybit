import os
import time
import threading
import requests
import pandas as pd
import pandas_ta as ta
from flask import Flask
from pybit.unified_trading import HTTP

# ==================================================
# 1. SERVIDOR FLASK (PARA RENDER Y CRON JOB)
# ==================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot de Trading activo y respondiendo.", 200

# ==================================================
# 2. CONFIGURACIÓN DE APIS Y VARIABLES DE ENTORNO
# ==================================================
API_KEY = os.environ.get("BYBIT_API_KEY", "")
SECRET_KEY = os.environ.get("BYBIT_SECRET_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Inicialización de cliente Bybit (Mainnet)
session = HTTP(
    testnet=False,
    api_key=API_KEY,
    api_secret=SECRET_KEY
)

def enviar_telegram(mensaje):
    """Envía alertas a tu chat de Telegram."""
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje}
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"Error enviando mensaje a Telegram: {e}")

# ==================================================
# 3. LÓGICA DE INDICADORES Y MERCADO (PÚBLICA)
# ==================================================
def obtener_datos_mercado(symbol="BTCUSDT"):
    """
    Obtiene Velas de 15m y Ticker de 24h usando endpoints públicos.
    Evita bloqueos de IP/Autenticación.
    """
    try:
        # Obtener Velas (Klines)
        klines = session.get_kline(category="linear", symbol=symbol, interval="15", limit=100)
        list_klines = klines['result']['list']
        
        df = pd.DataFrame(list_klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
        df = df.iloc[::-1].reset_index(drop=True)
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        
        # Calcular EMA 9 y EMA 21
        df['ema_fast'] = ta.ema(df['close'], length=9)
        df['ema_slow'] = ta.ema(df['close'], length=21)
        
        # Calcular RSI
        df['rsi'] = ta.rsi(df['close'], length=14)
        
        # Calcular ADX
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        df['adx'] = adx_df['ADX_14']
        
        # Obtener Ticker de 24 horas (Para precio actual y variación %)
        ticker = session.get_tickers(category="linear", symbol=symbol)
        ticker_data = ticker['result']['list'][0]
        
        precio_actual = float(ticker_data['lastPrice'])
        price_24h_pcnt = float(ticker_data['price24hPcnt']) * 100 # Convertir a Porcentaje
        
        return df, precio_actual, price_24h_pcnt
    except Exception as e:
        print(f"Error al obtener datos del mercado: {e}")
        return None, None, None

# ==================================================
# 4. BUCLE PRINCIPAL DE TRADING EN SEGUNDO PLANO
# ==================================================
def ejecutar_bot():
    print("🤖 Iniciando hilo de ejecución del Bot...")
    enviar_telegram("🚀 Bot de Trading en vivo iniciado correctamente.")
    
    while True:
        try:
            df, precio_actual, var_24h = obtener_datos_mercado("BTCUSDT")
            
            if df is not None and not df.empty:
                # Últimos valores calculados
                cruz_ema_fast = df['ema_fast'].iloc[-1]
                cruz_ema_slow = df['ema_slow'].iloc[-1]
                cruz_ema_fast_prev = df['ema_fast'].iloc[-2]
                cruz_ema_slow_prev = df['ema_slow'].iloc[-2]
                
                rsi_actual = df['rsi'].iloc[-1]
                adx_actual = df['adx'].iloc[-1]
                
                # Condición de Cruce Alcista (EMA 9 cruza hacia arriba EMA 21)
                cruce_bullish = (cruz_ema_fast_prev <= cruz_ema_slow_prev) and (cruz_ema_fast > cruz_ema_slow)
                
                # Condición de Variación >= 2%
                cumple_variacion = var_24h >= 2.0
                
                # Evaluación general de entrada LONG
                activa_long = cumple_variacion and cruce_bullish and (rsi_actual > 50) and (adx_actual > 20)
                
                # TABLERO DE CONTROL EN CONSOLA (Render Logs)
                hora_actual = time.strftime("%H:%M:%S", time.localtime())
                print("\n--------------------------------------------------")
                print(f"⏰ Hora: {hora_actual} | BTC: ${precio_actual:,.2f}")
                print(f"📈 Var. 24h: {var_24h:.2f}% (¿>= 2%?: {cumple_variacion})")
                print(f"⚔️ Cruce Bullish: {cruce_bullish}")
                print(f"📊 RSI: {rsi_actual:.1f} | ADX: {adx_actual:.1f}")
                print(f"🎯 ¿Activa LONG?: {activa_long}")
                print("--------------------------------------------------")
                
                # Ejecución de orden (Si cumple las condiciones)
                if activa_long:
                    msg = f"🔥 ¡SEÑAL LONG DETECTADA!\nBTC: ${precio_actual}\nVar 24h: {var_24h:.2f}%\nRSI: {rsi_actual:.1f} | ADX: {adx_actual:.1f}"
                    print(msg)
                    enviar_telegram(msg)
                    # Aquí va la ejecución de la orden con Bybit si aplica
                    
        except Exception as e:
            print(f"Error en el bucle principal: {e}")
            
        time.sleep(60) # Consulta cada 60 segundos

# ==================================================
# 5. INICIALIZACIÓN DE HILO Y SERVIDOR
# ==================================================
# Iniciar el bot en un hilo separado
thread = threading.Thread(target=ejecutar_bot, daemon=True)
thread.start()

if __name__ == "__main__":
    # Toma el puerto asignado por Render dinámicamente
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
