import asyncio
import json
import os
import re
import datetime
import sys
from aiohttp import web

# Dosyaların bulunduğu dizini belirtin
base_path = r"C:\Users\iRony\Desktop\local"
os.chdir(base_path)

json_dosya = os.path.join(base_path, "bagislar.json")
log_dosya = os.path.join(base_path, "bagis_log.txt")

# Eğer bagislar.json dosyası varsa, geçmiş verileri yükleyelim.
bagislar = []
if os.path.exists(json_dosya):
    try:
        with open(json_dosya, "r", encoding="utf-8") as f:
            bagislar = json.load(f)
    except Exception as e:
        print("JSON dosyası yüklenirken hata:", e)
        sys.stdout.flush()

donation_hash_set = set()
active_channels = {}           # Örneğin: {"Kanal 1": "Bağlandı, süre: mm:ss", "Kanal 2": "Bağlandı, süre: mm:ss"}
connection_start_times = {}    # Her kanal için bağlantı başlangıç zamanını saklar
clients = set()                # Bağlı istemcileri tutan set

internet_status = "Internet: Çevrimiçi"  # Varsayılan internet durumu

# ANSI renk kodları
GREEN = "\033[92m"   # Yeşil
RED   = "\033[91m"   # Kırmızı
RESET = "\033[0m"    # Renk sıfırlama

def print_active_channels():
    output = ""
    for channel, status in active_channels.items():
        color = GREEN if "Bağlandı" in status else RED
        output += f"{channel}: {color}{status}{RESET} | "
    sys.stdout.write("\r" + output.rstrip(" | "))
    sys.stdout.flush()

async def status_updater():
    global internet_status
    while True:
        now = datetime.datetime.now()
        for channel in connection_start_times:
            elapsed = now - connection_start_times[channel]
            minutes = elapsed.seconds // 60
            seconds = elapsed.seconds % 60
            active_channels[channel] = f"Bağlandı, süre: {minutes}:{str(seconds).zfill(2)}"
        print_active_channels()
        await asyncio.sleep(1)

def bagis_ekle(mesaj):
    print(f"Yeni Bağış Geldi: {mesaj}")
    sys.stdout.flush()
    try:
        parcalar = mesaj.strip().split(" - ")
        if len(parcalar) < 5:
            raise ValueError("Mesaj beklenen formatta değil")
        kanal = parcalar[0].strip("[] ")
        name = parcalar[1].strip()
        amount_raw = parcalar[2].strip()
        donation_type = parcalar[3].strip()
        message_text = " - ".join(parcalar[4:]).strip()
        m = re.search(r"([\d\.,]+)", amount_raw)
        if not m:
            raise ValueError("Miktar bulunamadı")
        amount = float(m.group(1).replace(",", "."))
        if bagislar:
            last = bagislar[-1]
            diff = datetime.datetime.now() - datetime.datetime.strptime(last["tarih"], "%Y-%m-%d %H:%M:%S")
            if last["isim"] == name and last["miktar"] == amount and diff.total_seconds() < 60:
                return
        data = {
            "kanal": kanal,
            "isim": name,
            "miktar": amount,
            "turu": donation_type,
            "mesaj": message_text,
            "tarih": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        bagislar.append(data)
        with open(json_dosya, "w", encoding="utf-8") as f:
            json.dump(bagislar, f, ensure_ascii=False, indent=2)
        with open(log_dosya, "a", encoding="utf-8") as log:
            log.write(f'{data["tarih"]} - {name} - {amount} TL - {donation_type} - {message_text}\n')
    except Exception as e:
        print(f"HATA: Bağış ayrıştırılamadı: {e}")
        sys.stdout.flush()

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    clients.add(ws)
    print("✅ Yeni bağlantı kuruldu.")
    sys.stdout.flush()
    current_channel = None
    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            if msg.data.startswith("connection active") or msg.data.startswith("ping"):
                m = re.match(r"(?:connection active|ping)\s*\((.*?)\):", msg.data)
                if m:
                    channel = m.group(1).strip() if m.group(1).strip() else "Kanal 1"
                    current_channel = channel
                    if channel not in connection_start_times:
                        connection_start_times[channel] = datetime.datetime.now()
                    if channel not in active_channels:
                        active_channels[channel] = "Bağlandı, süre: 0:00"
            else:
                bagis_ekle(msg.data)
        elif msg.type == web.WSMsgType.ERROR:
            print(f"❌ WS bağlantı hatası: {ws.exception()}")
            sys.stdout.flush()
    clients.discard(ws)
    if current_channel:
        active_channels[current_channel] = "Sekme kapatıldı"
        if current_channel in connection_start_times:
            del connection_start_times[current_channel]
    print_active_channels()
    print("\n🔌 Bağlantı kapatıldı.")
    sys.stdout.flush()
    return ws

async def reset_handler(request):
    global bagislar, donation_hash_set
    bagislar.clear()
    donation_hash_set.clear()
    try:
        if os.path.exists(json_dosya):
            os.remove(json_dosya)
            print("♻️ bagislar.json dosyası silindi.")
        else:
            print("♻️ bagislar.json dosyası mevcut değil.")
        sys.stdout.flush()
    except Exception as e:
        print("JSON dosyası silinirken hata:", e)
        sys.stdout.flush()
    for client in list(clients):
        try:
            await client.send_str("reset")
        except Exception as e:
            print("Reset mesajı gönderilemedi:", e)
            sys.stdout.flush()
    return web.Response(
        text="Donations reset.",
        headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"}
    )

async def start_http_server():
    app = web.Application()
    app.add_routes([
        web.get("/ws", websocket_handler),
        web.get("/reset", reset_handler)
    ])
    port = int(os.environ.get("PORT", 5679))
    print(f"🚀 Sunucu başlatılıyor (port {port})...")
    sys.stdout.flush()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"HTTP server started at http://localhost:{port} (accessible locally)")
    sys.stdout.flush()
    asyncio.create_task(status_updater())
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(start_http_server())
