import time
import pandas as pd
import pandas_ta as ta
import requests
from pybit.unified_trading import HTTP

# ==========================================
# 1. CREDENCIALES Y CONFIGURACIÓN
# ==========================================
API_KEY = 'IokH48VokxgRPmcAQq'
SECRET_KEY = 'MyZFKwbP8HS9L9MiY6xfnk40SH03brax7TZc'

# Credenciales de Telegram
TELEGRAM_TOKEN = "8925880927:AAEuXnLMypu0CitJ5QQPcegBUVUXQxm0QwM"
TELEGRAM_CHAT_ID = "5410664432"

# Conexión al entorno Demo Trading de Bybit
session = HTTP(
    demo=True,
    api_key=API_KEY,
    api_secret=SECRET_KEY,
    recv_window=10000
)

SYMBOL = 'BTCUSDT'
LEVERAGE = '2'

# ==========================================
# 2. FUNCIÓN DE NOTIFICACIÓN TELEGRAM
# ==========================================
def enviar_alerta_telegram(mensaje):
    """Envía un mensaje a Telegram e imprime errores si las credenciales fallan."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload, timeout=5)
        if res.status_code != 200:
            print(f"⚠️ Error de Telegram ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"Error al enviar mensaje a Telegram: {e}")

# Ajustar apalancamiento a 2x
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
    # Velas de 1 hora (intervalo '60')
    response = session.get_kline(
        category="linear",
        symbol=SYMBOL,
        interval="60",
        limit=200
    )
    
    klines = response['result']['list']
    df = pd.DataFrame(klines, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'Turnover'])
    df = df.iloc[::-1].reset_index(drop=True)
    
    df['Close'] = df['Close'].astype(float)
    df['High']  = df['High'].astype(float)
    df['Low']   = df['Low'].astype(float)
    
    df['ma5']   = ta.sma(df['Close'], length=5)
    df['ma10']  = ta.sma(df['Close'], length=10)
    df['ma20']  = ta.sma(df['Close'], length=20)
    df['ma200'] = ta.sma(df['Close'], length=200)
    df['rsi']   = ta.rsi(df['Close'], length=14)
    
    dmi_df = ta.adx(df['High'], df['Low'], df['Close'], length=14)
    df['adx']      = dmi_df['ADX_14']
    df['plus_di']  = dmi_df['DMP_14']
    df['minus_di'] = dmi_df['DMN_14']
    
    return df

# ==========================================
# 4. BUCLE PRINCIPAL DE EJECUCIÓN
# ==========================================
def ejecutar_bot():
    print("Bot iniciado correctamente. Monitoreando Bybit Testnet...\n")
    
    # Notificación al arrancar el script
    enviar_alerta_telegram(
        f"🟢 *Bot de Trading Iniciado*\n"
        f"• *Entorno:* Bybit Demo / Testnet\n"
        f"• *Par:* {SYMBOL}\n"
        f"• *Temporalidad:* 1 Hora"
    )
    
    while True:
        try:
            df = obtener_datos_e_indicadores()
            
            price = df['Close'].iloc[-1]
            ma5 = df['ma5'].values
            ma10 = df['ma10'].values
            ma20 = df['ma20'].values
            ma200 = df['ma200'].values
            rsi = df['rsi'].values
            adx = df['adx'].values
            plus_di = df['plus_di'].values
            minus_di = df['minus_di'].values
            high = df['High'].values
            low = df['Low'].values

            cruce_bullish = (ma5[-2] < ma10[-2] and ma5[-1] > ma10[-1]) or \
                            (ma5[-2] < ma20[-2] and ma5[-1] > ma20[-1])
                            
            cruce_bearish = (ma5[-2] > ma10[-2] and ma5[-1] < ma10[-1]) or \
                            (ma5[-2] > ma20[-2] and ma5[-1] < ma20[-1])

            cond_long = (
                price > ma200[-1] and
                cruce_bullish and
                ma5[-1] > ma20[-1] and
                plus_di[-1] > minus_di[-1] and
                adx[-1] >= 30 and
                50 <= rsi[-1] <= 70 and
                price > ma20[-1] and
                price > high[-2]
            )

            cond_short = (
                price < ma200[-1] and
                cruce_bearish and
                ma5[-1] < ma20[-1] and
                minus_di[-1] > plus_di[-1] and
                adx[-1] >= 30 and
                30 <= rsi[-1] <= 50 and
                price < ma20[-1] and
                price < low[-2]
            )

            # Consultar posición activa
            positions = session.get_positions(category="linear", symbol=SYMBOL)
            pos_size = float(positions['result']['list'][0]['size'])

            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] BTC: ${price:,.2f} | Posición actual: {pos_size} BTC")

            if pos_size == 0:
                if cond_long:
                    print("--> Entrada LONG detectada. Enviando orden...")
                    
                    # 1. Enviar orden a la Demo
                    session.place_order(
                        category="linear", symbol=SYMBOL, side="Buy",
                        orderType="Market", qty="0.01"
                    )
                    
                    # 2. Notificación por Telegram
                    mensaje_long = (
                        f"🚨 *ENTRADA LONG DETECTADA (DEMO)* 🚨\n\n"
                        f"• *Par:* {SYMBOL}\n"
                        f"• *Precio:* ${price:,.2f}\n"
                        f"• *RSI:* {rsi[-1]:.2f} | *ADX:* {adx[-1]:.2f}\n"
                        f"• *Orden:* Buy Market (0.01 BTC)"
                    )
                    enviar_alerta_telegram(mensaje_long)

                elif cond_short:
                    print("--> Entrada SHORT detectada. Enviando orden...")
                    
                    # 1. Enviar orden a la Demo
                    session.place_order(
                        category="linear", symbol=SYMBOL, side="Sell",
                        orderType="Market", qty="0.01"
                    )
                    
                    # 2. Notificación por Telegram
                    mensaje_short = (
                        f"🚨 *ENTRADA SHORT DETECTADA (DEMO)* 🚨\n\n"
                        f"• *Par:* {SYMBOL}\n"
                        f"• *Precio:* ${price:,.2f}\n"
                        f"• *RSI:* {rsi[-1]:.2f} | *ADX:* {adx[-1]:.2f}\n"
                        f"• *Orden:* Sell Market (0.01 BTC)"
                    )
                    enviar_alerta_telegram(mensaje_short)

            # Revisa cada 15 minutos
            time.sleep(900)

        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error en ejecución: {e}. Reintentando en 15 segundos...")
            time.sleep(15)

if __name__ == '__main__':
    ejecutar_bot()