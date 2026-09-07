"""Optional local Chrome visual check. Uses the devtools protocol, not production app code."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from urllib.request import urlopen
from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[1]


def main():
    browser = shutil.which("google-chrome") or shutil.which("chromium")
    if not browser:
        browser = str(Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe")
    profile = tempfile.mkdtemp(prefix="trendpulse-preview-")
    process = subprocess.Popen([browser, "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
        f"--user-data-dir={profile}", "--remote-debugging-port=0", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        endpoint = Path(profile) / "DevToolsActivePort"
        for _ in range(60):
            if endpoint.exists():
                break
            time.sleep(.25)
        port = endpoint.read_text().splitlines()[0]
        targets = json.load(urlopen(f"http://127.0.0.1:{port}/json/list"))
        target = next(t for t in targets if t["type"] == "page")
        with connect(target["webSocketDebuggerUrl"], max_size=30_000_000) as ws:
            counter = 0
            def call(method, params=None):
                nonlocal counter
                counter += 1
                ws.send(json.dumps({"id":counter, "method":method, "params":params or {}}))
                while True:
                    result = json.loads(ws.recv(timeout=30))
                    if result.get("id") == counter:
                        if "error" in result:
                            raise RuntimeError(result["error"])
                        return result.get("result", {})
            call("Page.enable")
            call("Emulation.setDeviceMetricsOverride", {"width":1536, "height":1100, "deviceScaleFactor":1, "mobile":False})
            call("Page.navigate", {"url":"http://127.0.0.1:8501"})
            for _ in range(60):
                result = call("Runtime.evaluate", {"expression":"!!document.querySelector('.topic-card')", "returnByValue":True})
                if result.get("result", {}).get("value"):
                    break
                time.sleep(.5)
            else:
                raise RuntimeError("Dashboard did not finish rendering.")
            time.sleep(2)
            images = call("Runtime.evaluate", {"expression":"[...document.querySelectorAll('img.spark')].filter(i=>i.complete && i.naturalWidth>0).length", "returnByValue":True})
            assert images["result"].get("value", 0) >= 3, "Sparkline images did not render"
            call("Emulation.setEmulatedMedia", {"features":[{"name":"prefers-reduced-motion", "value":"reduce"}]})
            motion = call("Runtime.evaluate", {"expression":"getComputedStyle(document.querySelector('.topic-card')).animationName", "returnByValue":True})
            assert motion["result"].get("value") == "none", "Reduced-motion preference was not respected"
            call("Emulation.setEmulatedMedia", {"features":[]})
            print("PASS: sparklines loaded and reduced-motion preference respected.")
            destination = ROOT / "docs/screenshots"
            destination.mkdir(parents=True, exist_ok=True)
            for name, width, height in [("overview",1536,1100), ("mobile",390,844)]:
                call("Emulation.setDeviceMetricsOverride", {"width":width, "height":height, "deviceScaleFactor":1, "mobile":False})
                time.sleep(1)
                capture = call("Page.captureScreenshot", {"format":"png", "captureBeyondViewport":False})
                (destination / f"{name}.png").write_bytes(base64.b64decode(capture["data"]))
                overflow = call("Runtime.evaluate", {"expression":"document.documentElement.scrollWidth > innerWidth", "returnByValue":True})
                print(f"{name}: captured; document overflow = {overflow['result'].get('value')}")
                if name == "mobile":
                    nav = call("Runtime.evaluate", {"expression":"document.querySelector('[data-testid=stExpandSidebarButton]')?.getBoundingClientRect().width > 0", "returnByValue":True})
                    assert nav["result"].get("value"), "Mobile navigation toggle is hidden"
                    call("Runtime.evaluate", {"expression":"document.querySelector('[data-testid=stExpandSidebarButton]').click()"})
                    time.sleep(.5)
                    expanded = call("Runtime.evaluate", {"expression":"document.querySelector('[data-testid=stSidebar]')?.getAttribute('aria-expanded')", "returnByValue":True})
                    assert expanded["result"].get("value") == "true", "Mobile navigation did not open"
                    print("PASS: mobile Menu button opens navigation.")
            call("Emulation.setDeviceMetricsOverride", {"width":1536, "height":1100, "deviceScaleFactor":1, "mobile":False})
            call("Runtime.evaluate", {"expression":"document.querySelector('.topic-card')?.scrollIntoView({block:'center'})"})
            time.sleep(1)
            capture = call("Page.captureScreenshot", {"format":"png"})
            (destination / "signals.png").write_bytes(base64.b64decode(capture["data"]))
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    main()
