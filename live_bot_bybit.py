import os
import time
import ccxt
import pandas as pd
import numpy as np
import ta
from datetime import datetime, timezone

# ------------------------------------------------------------------
# CONFIGURACIÓN DE PARÁMETROS Y CLAVES (Variables de Entorno)
# ------------------------------------------------------------------
API_KEY = os.getenv('BYBIT_API_KEY', '')
API_SECRET = os.getenv('BYBIT_API_SECRET', '')

# Inicializar Exchange (Bybit Demo / Testnet)
exchange = ccxt.bybit({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

# Activa modo Testnet (Demo)
exchange.set_sandbox_mode(True)

SYMBOL = 'BTC/USDT:USDT'
TIMEFRAME = '15m'
LEVERAGE = 1
MONTO_USDT = 50.0  # Tamaño de posición en USDT

TP_PCT = 0.018  # Take Profit 1.8%
SL_PCT = 0.010  # Stop Loss 1.0%

# ------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ------------------------------------------------------------------
def obtener_datos_mercado():
    """Descarga las últimas velas e ingresa los indicadores técnicos."""
    try:
        ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        for col in ['open', 'high', 'low', 'close']:
            df[col] = df[col].astype(float)
            
        # Indicadores usando la librería 'ta'
        df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=9)
        df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=21)
        df['rsi'] = ta.momentum.rsi(df['close'], window=14)
        df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14)
        
        # Variación de 1h (4 velas de 15m)
        df['var_1h'] = ((df['close'] - df['close'].shift(4)) / df['close'].shift(4)) * 100
        
        return df
    except Exception as e:
        print(f"⚠️ Error obteniendo datos de mercado: {e}")
        return None

def verificar_posicion_abierta():
    """Consulta si actualmente hay una posición LONG activa."""
    try:
        positions = exchange.fetch_positions([SYMBOL])
        for pos in positions:
            if float(pos['contracts']) > 0 and pos['side'].lower() == 'long':
                return True
        return False
    except Exception as e:
        print(f"⚠️ Error consultando posiciones: {e}")
        return True

def ejecutar_orden_long(precio_actual):
    """Ejecuta una orden de entrada en LONG con TP y SL adjuntos."""
    try:
        cantidad_btc = round(MONTO_USDT / precio_actual, 3)
        tp_price = round(precio_actual * (1 + TP_PCT), 2)
        sl_price = round(precio_actual * (1 - SL_PCT), 2)
        
        print(f"🚀 Ejecutando LONG: {cantidad_btc} BTC | Entrada: {precio_actual} | TP: {tp_price} | SL: {sl_price}")
        
        try:
            exchange.set_leverage(LEVERAGE, SYMBOL)
        except Exception:
            pass

        params = {
            'takeProfit': str(tp_price),
            'stopLoss': str(sl_price)
        }
        
        order = exchange.create_market_buy_order(SYMBOL, cantidad_btc, params)
        print(f"✅ Orden ejecutada con éxito. ID: {order['id']}")
    except Exception as e:
        print(f"❌ Error al ejecutar la orden: {e}")

# ------------------------------------------------------------------
# BUCLE PRINCIPAL DE EJECUCIÓN (24/7)
# ------------------------------------------------------------------
def ejecutar_bot():
    print("🤖 Bot de Trading activado en Render. Esperando condiciones de entrada...")
    
    while True:
        try:
            ahora = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
            df = obtener_datos_mercado()
            
            if df is not None and len(df) > 0:
                ultima = df.iloc[-1]
                
                # Evaluación de condiciones LONG
                long_signal = (
                    (ultima['var_1h'] >= 1.0) and 
                    (ultima['ema_fast'] > ultima['ema_slow']) and 
                    (ultima['rsi'] > 50) and 
                    (ultima['adx'] > 15)
                )
                
                posicion_activa = verificar_posicion_abierta()
                
                print(f"[{ahora}] Precio: {ultima['close']} | Var 1h: {ultima['var_1h']:.2f}% | RSI: {ultima['rsi']:.1f} | ADX: {ultima['adx']:.1f} | Posición Activa: {posicion_activa}")
                
                if long_signal and not posicion_activa:
                    print("🎯 Señal detectada. Preparando orden...")
                    ejecutar_orden_long(ultima['close'])
                
            time.sleep(60)
            
        except Exception as e:
            print(f"⚠️ Error general en el bucle: {e}")
            time.sleep(30)

if __name__ == '__main__':
    ejecutar_bot()
