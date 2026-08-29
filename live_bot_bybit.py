import os
import time
import threading
import requests
from flask import Flask

# ==========================================
# 1. CONFIGURACIÓN Y SERVIDOR WEB FLASK
# ==========================================
app = Flask(__name__)

@app.route('/')
def health_check():
    # Responde a Render y cron-job.org con HTTP 200 OK
    return "Bot de Bybit activo y ejecutándose correctamente.", 200

def run_web_server():
    # Render asigna automáticamente un puerto con la variable de entorno PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Iniciar el servidor HTTP en un hilo secundario
threading.Thread(target=run_web_server, daemon=True).start()


# ==========================================
# 2. MÓDULO DE NOTIFICACIONES POR TELEGRAM
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def enviar_telegram(mensaje):
    """Envía un mensaje formateado en HTML a tu chat de Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram no configurado: faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code != 200:
            print(f"⚠️ Error enviando mensaje a Telegram: {response.text}")
    except Exception as e:
        print(f"⚠️ Excepción en envío de Telegram: {e}")


# ==========================================
# 3. LÓGICA PRINCIPAL DE TU BOT DE TRADING
# ==========================================
def main():
    print("🚀 Bot de trading iniciado en Render...")
    
    # Notificación de arranque
    enviar_telegram("🚀 <b>Bot de Bybit iniciado correctamente en Render.</b>\nMonitoreando el mercado...")
    
    # Carga de credenciales de Bybit
    api_key = os.environ.get("BYBIT_API_KEY", "")
    api_secret = os.environ.get("BYBIT_API_SECRET", "")
    
    if not api_key or not api_secret:
        print("⚠️ Advertencia: Faltan BYBIT_API_KEY o BYBIT_API_SECRET en las variables de entorno.")
    else:
        print("🔑 Claves API de Bybit cargadas correctamente.")

    # Bucle principal de mercado
    while True:
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Chequeando condiciones de mercado...")
            
            # ----------------------------------------------------
            # EJEMPLO DE CÓMO LLAMAR A LAS ALERTAS DE TELEGRAM:
            # 
            # Si tu estrategia decide abrir una orden LONG:
            # msg_long = (
            #     "🟢 <b>ORDEN EJECUTADA - COMPRA (LONG)</b>\n\n"
            #     "<b>Par:</b> BTCUSDT\n"
            #     "<b>Precio:</b> $64,250.00\n"
            #     "<b>Stop Loss:</b> $63,000.00\n"
            #     "<b>Take Profit:</b> $66,500.00"
            # )
            # enviar_telegram(msg_long)
            # ----------------------------------------------------

            # Tiempo de espera entre lecturas (ej. 60 segundos)
            time.sleep(60)
            
        except Exception as e:
            print(f"❌ Error en el bucle principal: {e}")
            enviar_telegram(f"⚠️ <b>Error en la ejecución del bot:</b>\n<code>{e}</code>")
            time.sleep(10)

if __name__ == "__main__":
    main()
