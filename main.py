import asyncio
import aiohttp
import time

# Sürekli açık tutulacak StreamElements overlay URL'leri
URL_LIST = [
    "https://streamelements.com/overlay/67f09ec1992fa6c9abcda18f/7v8OiWoMZYqPQz2ls0ST9M_tkAzULwUBpPlxhRV9nh5o9FGR",
    "https://streamelements.com/overlay/67f040c9051cb72361332329/nnF0dF3sMVnCWHAHCoC9IXVinvzNrL0rfGFRXwIdth8FKkny"
]

async def ping_urls():
    async with aiohttp.ClientSession() as session:
        while True:
            for url in URL_LIST:
                try:
                    async with session.get(url) as response:
                        print(f"[{time.strftime('%H:%M:%S')}] Pinged {url} - Status: {response.status}")
                except Exception as e:
                    print(f"[{time.strftime('%H:%M:%S')}] Error pinging {url}: {e}")
            await asyncio.sleep(300)  # 5 dakika (300 saniye) bekle

if __name__ == "__main__":
    asyncio.run(ping_urls())
