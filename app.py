# ============================================
# 🌱 Smart Farming - Backend Lokal (Flask + MQTT)
# Menggunakan broker publik:
#   broker.hivemq.com (tanpa TLS)
# ============================================

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import paho.mqtt.client as mqtt
import json
import threading
import sqlite3

app = Flask(__name__)
CORS(app)

# ============================================
# 📌 Inisialisasi Database SQLite
# ============================================

def init_db():
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS sensor_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT,
            hari TEXT,
            waktu TEXT,
            moisture REAL,
            soil_temp REAL,
            air_temp REAL,
            air_hum REAL,
            pump_state TEXT
        )
    """)
    conn.commit()
    conn.close()

# Buat tabel saat server start
init_db()

# ============================================
# ⚙️ Konfigurasi MQTT Lokal / Public
# ============================================

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883   # NON-TLS (public broker)
TOPIC_SENSOR = "irigasi/sensor"
TOPIC_POMPA = "irigasi/pompa"

# ============================================
# 🧪 Buffer Data Sensor (Realtime)
# ============================================

sensor_data = {
    "moisturePercent": 0,
    "soilTemperature": 0.0,
    "suhuUdara": 0.0,
    "kelembapanUdara": 0.0,
    "pumpState": "Mati",
    "tanggal": "-",
    "hari": "-",
    "waktu": "-"
}

# ============================================
# 🔄 CALLBACK MQTT
# ============================================

def on_connect(client, userdata, flags, rc):
    print("✅ MQTT Connected:", rc)
    client.subscribe(TOPIC_SENSOR)

def on_message(client, userdata, msg):
    global sensor_data
    try:
        if msg.topic == TOPIC_SENSOR:
            data = json.loads(msg.payload.decode())
            sensor_data.update(data)

            print("📥 Data diterima:", sensor_data)

            # ============================================
            # 💾 Simpan ke Database SQLite
            # ============================================
            conn = sqlite3.connect("data.db")
            c = conn.cursor()
            c.execute("""
                INSERT INTO sensor_log 
                (tanggal, hari, waktu, moisture, soil_temp, air_temp, air_hum, pump_state)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get("tanggal", "-"),
                data.get("hari", "-"),
                data.get("waktu", "-"),
                data.get("moisturePercent", 0),
                data.get("soilTemperature", 0.0),
                data.get("suhuUdara", 0.0),
                data.get("kelembapanUdara", 0.0),
                sensor_data.get("pumpState", "Mati")
            ))
            conn.commit()
            conn.close()

    except Exception as e:
        print("⚠️ Error parsing MQTT:", e)

# ============================================
# 🚀 MQTT CLIENT
# ============================================

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

mqtt_thread = threading.Thread(target=mqtt_client.loop_forever, daemon=True)
mqtt_thread.start()

# ============================================
# 🌐 ROUTES FLASK
# ============================================

@app.route("/")
def index():
    return render_template("index.html")  # pastikan index.html berada di folder /templates

@app.route("/get_data")
def get_data():
    return jsonify(sensor_data)

@app.route("/get_history")
def get_history():
    """ Mengambil data history dari database """
    conn = sqlite3.connect("data.db")
    c = conn.cursor()
    c.execute("SELECT * FROM sensor_log ORDER BY id DESC LIMIT 300")
    rows = c.fetchall()
    conn.close()
    return jsonify(rows)

@app.route("/pump/<action>", methods=["GET"])
def pump_control(action):
    """ Kontrol pompa ON/OFF dari dashboard """
    if action.lower() == "on":
        mqtt_client.publish(TOPIC_POMPA, "ON")
        sensor_data["pumpState"] = "MENYALA 💦"

    elif action.lower() == "off":
        mqtt_client.publish(TOPIC_POMPA, "OFF")
        sensor_data["pumpState"] = "MATI ✅"

    return jsonify(sensor_data)

# ============================================
# ▶️ MAIN
# ============================================

if __name__ == "__main__":
    print("🚀 Server berjalan di http://127.0.0.0:8000")
    app.run(host="0.0.0.0", port=8000, debug=True)
