#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║   Ⓜ MATUGRAVITY v3.0.1 (UTF-8 Hotfix)                   ║
║                                                          ║
║   ▸ DeepSeekAPI    — api.deepseek.com                    ║
║   ▸ GrokAPI        — api.x.ai                            ║
║   ▸ ClaudeAPI      — api.anthropic.com                   ║
║   ▸ GeminiAPI      — generativelanguage.googleapis.com   ║
╚══════════════════════════════════════════════════════════╝
"""
import os, re, sys, json, subprocess, io
from pathlib import Path
from datetime import datetime
import requests

# ════════════════════════ KARAKTER SORUNU KÖKTEN ÇÖZÜM ════════════════════════
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass

# Python'un stdout akışını tamamen UTF-8'e kilitle (Ä±, Ã¼, Å bozulmalarını engeller)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
except Exception:
    pass


# ════════════════════════ RENKLER & BANNER ════════════════════════
class C:
    R="\033[0m"; B="\033[1m"; DIM="\033[2m"
    RED="\033[91m"; GRN="\033[92m"; YLW="\033[93m"
    BLU="\033[94m"; MAG="\033[95m"; CYN="\033[96m"

BANNER = f"""{C.CYN}{C.B}
  ███╗   ███╗ █████╗ ████████╗██╗   ██╗██╗   ██╗
  ████╗ ████║██╔══██╗╚══██╔══╝██║   ██║██║   ██║
  ██╔████╔██║███████║   ██║   ██║   ██║██║   ██║
  ██║╚██╔╝██║██╔══██║   ██║   ██║   ██║╚██╗ ██╔╝
  ██║ ╚═╝ ██║██║  ██║   ██║    ╚██████╔╝ ╚████╔╝
  ╚═╝     ╚═╝╚═╝  ╚═╝   ╚═╝     ╚═════╝   ╚═══╝{C.R}{C.B} G R A V I T Y{C.R}
  {C.DIM}─ v3.0.1 · UTF-8 Hotfix · 4 API · 4 Model Ailesi ─{C.R}"""

WORKSPACE = Path("./matu_workspace")
KEYS_FILE = Path("keys.json")
MAX_GECMIS = 24

# ════════════════════════ MODELLER ════════════════════════
MODELLER = {
    "deepseek": {
        "deepseek-chat":     {"max_out": 8192},
        "deepseek-reasoner": {"max_out": 65536},
    },
    "grok": {
        "grok-4":       {"max_out": 32768},
        "grok-3":       {"max_out": 16384},
        "grok-3-mini":  {"max_out": 16384},
    },
    "claude": {
        "claude-sonnet-4-20250514":  {"max_out": 64000},
        "claude-opus-4-20250514":    {"max_out": 32000},
        "claude-3-5-haiku-20241022": {"max_out": 8192},
    },
    "gemini": {
        "gemini-3.6-flash": {"max_out": 65536},
        "gemini-3.6-pro":   {"max_out": 65536},
        "gemini-2.5-flash": {"max_out": 65536},
        "gemini-2.5-pro":   {"max_out": 65536},
    },
}

ADLAR = {"deepseek":"DeepSeek","grok":"Grok",
         "claude":"Claude","gemini":"Gemini"}

ENV_KEYS = {"deepseek":"DEEPSEEK_API_KEY","grok":"XAI_API_KEY",
            "claude":"ANTHROPIC_API_KEY","gemini":"GEMINI_API_KEY"}

SYSTEM_PROMPT = """Sen MatuGravity adlı agentic kodlama asistanısın. DÜNYA SEVİYESİNDE yazılım mühendisisin.

KURALLAR:
1. Kod yazarken HER zaman dil adından sonra hedef dosya adını yaz:
   ```python ana.py
   ```javascript server.js
   ```html index.html
2. Kodu ASLA yarım bırakma — dosyanın TAMAMINI üret.
3. Üretim kalitesi: tip ipuçları, hata yönetimi, temiz mimari, yorumlar.
4. Birden fazla dosya gerekiyorsa her birini ayrı bloklarda ver.
5. Kullanıcının dilinde konuş (Türkçe ise Türkçe).
6. Mimari kararı kendin ver, en iyi pratiği seç."""

EXT_MAP={"python":"py","py":"py","javascript":"js","js":"js","typescript":"ts",
 "html":"html","css":"css","json":"json","markdown":"md","md":"md","java":"java",
 "cpp":"cpp","c":"c","csharp":"cs","go":"go","rust":"rs","ruby":"rb","php":"php",
 "bash":"sh","shell":"sh","sql":"sql","yaml":"yaml","xml":"xml"}
CODE_RE = re.compile(r"```([\w+#.\-]*)[ \t]*([^\n]*)\n(.*?)```", re.S)


# ════════════════════════ ORTAK YARDIMCILAR ════════════════════════
def renk(s,c=""): print(f"{c}{s}{C.R}")

def gizle(metin,key):
    """Hatalarda anahtar sızdırma."""
    if not metin: return ""
    m=str(metin)
    if key: m=m.replace(key,"***ANAHTAR***")
    m=re.sub(r"key=[\w.\-]+","key=***",m)
    m=re.sub(r"(Bearer\s)[\w.\-]+",r"\1***",m)
    m=re.sub(r"(x-api-key[\"':=\s]+)[\w.\-]+",r"\1***",m)
    return m

def sse_akis(resp):
    """Server-Sent Events → JSON parçaları (Manuel UTF-8 Çözümleyici)"""
    for satir in resp.iter_lines():
        if not satir: continue
        
        # Requests'in otomatik charset çözümlemesine güvenmiyoruz,
        # doğrudan UTF-8 olarak decode ediyoruz (Bozuk harf sorununu çözer).
        try:
            satir = satir.decode('utf-8')
        except UnicodeDecodeError:
            continue
            
        if not satir.startswith("data:"): continue
        veri=satir[5:].strip()
        if veri=="[DONE]": return
        try: yield json.loads(veri)
        except json.JSONDecodeError: continue

def alternatif_bul(govde,mevcut):
    """Sunucu 'şu modeli kullan' dediyse onu yakala."""
    for pat in (r"use models/([\w.\-]+)",
                r"use\s+`?([\w.\-]+)`?\s+for"):
        m=re.search(pat,str(govde))
        if m and m.group(1)!=mevcut: return m.group(1)
    return None

def hata_goster(e,key="",govde=None):
    det=getattr(e,"response",None)
    raw=""
    if det is not None:
        try:
            raw = det.content.decode('utf-8', errors='replace')[:300]
        except Exception:
            raw = str(det.text[:300])
    elif govde:
        raw = govde
        
    renk(f"\n✖ API hatası: {gizle(str(e),key)}",C.RED)
    if raw: renk(gizle(raw,key),C.DIM)


# ════════════════════════════════════════════════════════════════════
#                        D E E P S E E K   A P I
# ════════════════════════════════════════════════════════════════════
class DeepSeekAPI:
    ad = "DeepSeek"
    URL = "https://api.deepseek.com/chat/completions"

    def __init__(self):
        self.key=""; self.yeni_model=None

    def akis(self,gecmis,model,mx,temp):
        self.yeni_model=None
        mesaj=[{"role":"system","content":SYSTEM_PROMPT}]+gecmis
        govde={"model":model,"messages":mesaj,
               "max_tokens":mx,"stream":True}
        if "reasoner" not in model:
            govde["temperature"]=temp
        try:
            r=requests.post(self.URL,stream=True,timeout=900,json=govde,
                headers={"Authorization":f"Bearer {self.key}",
                         "Content-Type":"application/json"})
            if r.status_code==404:
                alt=alternatif_bul(r.text,model)
                if alt:
                    renk(f"\n🔁 '{model}' yok → '{alt}' deneniyor…",C.YLW)
                    self.yeni_model=alt; model=alt
                    govde["model"]=alt
                    r=requests.post(self.URL,stream=True,timeout=900,json=govde,
                        headers={"Authorization":f"Bearer {self.key}",
                                 "Content-Type":"application/json"})
            r.raise_for_status()
            for j in sse_akis(r):
                ch=(j.get("choices") or [{}])[0]
                d=ch.get("delta") or {}
                if d.get("reasoning_content"):
                    yield("dusun",d["reasoning_content"])
                if d.get("content"):
                    yield("metin",d["content"])
                if ch.get("finish_reason"):
                    yield("bitti",ch["finish_reason"]); return
        except requests.RequestException as e: hata_goster(e,self.key)
        yield("bitti",None)


# ════════════════════════════════════════════════════════════════════
#                           G R O K   A P I
# ════════════════════════════════════════════════════════════════════
class GrokAPI:
    ad = "Grok"
    URL = "https://api.x.ai/v1/chat/completions"

    def __init__(self):
        self.key=""; self.yeni_model=None

    def akis(self,gecmis,model,mx,temp):
        self.yeni_model=None
        mesaj=[{"role":"system","content":SYSTEM_PROMPT}]+gecmis
        if model.startswith("grok-4"):
            st=""; kalan=[]
            for m in mesaj:
                if m["role"]=="system": st+=m["content"]+"\n"
                else: kalan.append(dict(m))
            for m in kalan:
                if m["role"]=="user":
                    m["content"]=st+m["content"]; break
            mesaj=kalan
        govde={"model":model,"messages":mesaj,"max_tokens":mx,"stream":True}
        try:
            r=requests.post(self.URL,stream=True,timeout=900,json=govde,
                headers={"Authorization":f"Bearer {self.key}",
                         "Content-Type":"application/json"})
            if r.status_code==404:
                alt=alternatif_bul(r.text,model)
                if alt:
                    renk(f"\n🔁 '{model}' yok → '{alt}' deneniyor…",C.YLW)
                    self.yeni_model=alt; model=alt; govde["model"]=alt
                    r=requests.post(self.URL,stream=True,timeout=900,json=govde,
                        headers={"Authorization":f"Bearer {self.key}",
                                 "Content-Type":"application/json"})
            r.raise_for_status()
            for j in sse_akis(r):
                ch=(j.get("choices") or [{}])[0]
                d=ch.get("delta") or {}
                if d.get("content"): yield("metin",d["content"])
                if ch.get("finish_reason"):
                    yield("bitti",ch["finish_reason"]); return
        except requests.RequestException as e: hata_goster(e,self.key)
        yield("bitti",None)


# ════════════════════════════════════════════════════════════════════
#                        C L A U D E   A P I
# ════════════════════════════════════════════════════════════════════
class ClaudeAPI:
    ad = "Claude"
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self):
        self.key=""; self.yeni_model=None

    def akis(self,gecmis,model,mx,temp):
        self.yeni_model=None
        govde={"model":model,"max_tokens":min(mx,64000),
               "temperature":temp,"system":SYSTEM_PROMPT,
               "stream":True,"messages":gecmis}
        baslik={"x-api-key":self.key,
                "anthropic-version":"2023-06-01",
                "Content-Type":"application/json"}
        try:
            r=requests.post(self.URL,stream=True,timeout=900,json=govde,headers=baslik)
            if r.status_code==404:
                alt=alternatif_bul(r.text,model)
                if alt:
                    renk(f"\n🔁 '{model}' yok → '{alt}' deneniyor…",C.YLW)
                    self.yeni_model=alt; model=alt; govde["model"]=alt
                    r=requests.post(self.URL,stream=True,timeout=900,
                                    json=govde,headers=baslik)
            r.raise_for_status()
            for j in sse_akis(r):
                tur=j.get("type")
                if tur=="content_block_delta":
                    t=j.get("delta",{}).get("text")
                    if t: yield("metin",t)
                elif tur=="message_delta":
                    sr=j.get("delta",{}).get("stop_reason")
                    if sr: yield("bitti",sr); return
        except requests.RequestException as e: hata_goster(e,self.key)
        yield("bitti",None)


# ════════════════════════════════════════════════════════════════════
#                        G E M I N I   A P I
# ════════════════════════════════════════════════════════════════════
class GeminiAPI:
    ad = "Gemini"
    BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self):
        self.key=""; self.yeni_model=None

    def canli_liste(self):
        try:
            r=requests.get(self.BASE,params={"key":self.key,"pageSize":200},timeout=30)
            r.raise_for_status()
            ad=[]
            for m in r.json().get("models",[]):
                if "generateContent" in m.get("supportedGenerationMethods",[]):
                    a=m["name"].rsplit("/",1)[-1]
                    if not any(x in a for x in
                               ("embedding","aqa","imagen","veo","tts","native-audio")):
                        ad.append(a)
            return sorted(set(ad))
        except Exception as h:
            renk(f"  ✖ Liste alınamadı: {h}",C.RED); return []

    def akis(self,gecmis,model,mx,temp):
        self.yeni_model=None
        icerik=[{"role":("model" if m["role"]=="assistant" else "user"),
                 "parts":[{"text":m["content"]}]} for m in gecmis]
        url=f"{self.BASE}/{model}:streamGenerateContent?alt=sse&key={self.key}"
        try:
            r=requests.post(url,stream=True,timeout=900,json={
                "systemInstruction":{"parts":[{"text":SYSTEM_PROMPT}]},
                "contents":icerik,
                "generationConfig":{"temperature":temp,"maxOutputTokens":mx}})
            if r.status_code==404:
                alt=alternatif_bul(r.text,model)
                if alt:
                    renk(f"\n🔁 '{model}' emekli → '{alt}' otomatik deneniyor…",C.YLW)
                    self.yeni_model=alt; model=alt
                    url=f"{self.BASE}/{alt}:streamGenerateContent?alt=sse&key={self.key}"
                    r=requests.post(url,stream=True,timeout=900,json={
                        "systemInstruction":{"parts":[{"text":SYSTEM_PROMPT}]},
                        "contents":icerik,
                        "generationConfig":{"temperature":temp,"maxOutputTokens":mx}})
            r.raise_for_status()
            for j in sse_akis(r):
                try:
                    cand=j["candidates"][0]
                    for p in cand.get("content",{}).get("parts",[]):
                        if p.get("text"): yield("metin",p["text"])
                    fr=cand.get("finishReason")
                    if fr and fr!="STOP": pass
                    if fr: yield("bitti",fr); return
                except (KeyError,IndexError): continue
        except requests.RequestException as e: hata_goster(e,self.key)
        yield("bitti",None)


API_SINIFLARI = {"deepseek":DeepSeekAPI,"grok":GrokAPI,
                 "claude":ClaudeAPI,"gemini":GeminiAPI}


# ════════════════════════ ANAHTAR YÖNETİMİ ════════════════════════
def anahtarlar_yukle():
    if KEYS_FILE.exists():
        try: return json.loads(KEYS_FILE.read_text(encoding="utf-8"))
        except Exception: pass
    return {}

def anahtar_kaydet(k):
    KEYS_FILE.write_text(json.dumps(k,indent=2,ensure_ascii=False),encoding="utf-8")

def kurulum(keys,zorla=False):
    if not zorla and any(keys.get(x) for x in ADLAR): return keys
    renk("\n🔑 API ANAHTAR KURULUMU  (Enter = boş geç)\n",C.MAG)
    for kod,ad in ADLAR.items():
        if keys.get(kod): continue
        v=os.environ.get(ENV_KEYS[kod])
        if v: keys[kod]=v; renk(f"  🌍 {ad}: ortam değişkeninden alındı.",C.DIM); continue
        try:
            i=input(f"  {ad} anahtarı: ").strip()
            if i: keys[kod]=i
        except EOFError: break
    anahtar_kaydet(keys)
    renk(f"  ✔ Kaydedildi → {KEYS_FILE.resolve()}",C.GRN)
    return keys


# ════════════════════════ MENÜLER ════════════════════════
def menu_saglayici(keys):
    aktif=[k for k in ADLAR if keys.get(k)]
    while True:
        renk("\n📡 Sağlayıcı seç:",C.YLW)
        for i,(kod,ad) in enumerate(ADLAR.items(),1):
            print(f"   {i}) {'🟢' if kod in aktif else '🔴'} {ad}")
        s=input("  № (veya kod yaz / anahtar eklemek için isim): ").strip().lower()
        if s.isdigit() and 1<=int(s)<=len(ADLAR):
            kod=list(ADLAR)[int(s)-1]
        elif s in ADLAR: kod=s
        else: renk("  Geçersiz.",C.RED); continue
        if kod in aktif: return kod
        v=input(f"  {ADLAR[kod]} anahtarı (boş=vazgeç): ").strip()
        if v: keys[kod]=v; anahtar_kaydet(keys); return kod

def menu_model(kod,api):
    ml=MODELLER[kod]
    renk(f"\n🧠 {ADLAR[kod]} modelleri:",C.YLW)
    for i,(a,o) in enumerate(ml.items(),1):
        print(f"   {i}) {a:32s} max: {o['max_out']}")
    if kod=="gemini": print("   L) 🔄 Sunucudan canlı model listesi çek")
    print("   💡 Model adını elle de yazabilirsin · Enter=en üstteki")
    while True:
        s=input("  № / L / model-adı: ").strip()
        ad=list(ml)
        if not s: return ad[0],ml[ad[0]]["max_out"]
        if s.lower()=="l" and kod=="gemini":
            canli=api.canli_liste()
            for i,a in enumerate(canli,1): print(f"   • {a}")
            sec=input("  Bu listeden bir tane yaz (boş=vazgeç): ").strip()
            if sec in canli:
                ml[sec]={"max_out":65536}
                return sec,65536
            continue
        if s.isdigit() and 1<=int(s)<=len(ad):
            a=ad[int(s)-1]; return a,ml[a]["max_out"]
        if s in ml: return s,ml[s]["max_out"]
        if re.fullmatch(r"[A-Za-z0-9._\-]+",s):
            ml[s]={"max_out":65536}
            renk(f"  ✔ Özel model eklendi: {s}",C.GRN); return s,65536
        renk("  Geçersiz.",C.RED)


# ════════════════════════ DOSYA MOTORU ════════════════════════
def guvenli_yol(isim):
    isim=isim.replace("\\","/").strip("/ ")
    p=Path(isim)
    if ".." in p.parts or p.is_absolute(): return None
    return WORKSPACE/p

def dosyalari_isle(metin,kayitlar):
    bloklar=CODE_RE.findall(metin)
    if not bloklar:
        renk("  ℹ Kaydedilebilir kod bloğu yok.",C.DIM); return
    renk(f"\n📁 {len(bloklar)} kod bloğu bulundu:",C.CYN)
    WORKSPACE.mkdir(exist_ok=True)
    for i,(dil,satir,kod) in enumerate(bloklar,1):
        ad=satir.strip().split()[0] if satir.strip() else ""
        y=guvenli_yol(ad) if re.fullmatch(r"[\w\-. /]+\.[A-Za-z0-9]{1,6}",ad) else None
        if y is None:
            y=guvenli_yol(f"kod_{i}.{EXT_MAP.get(dil.lower(),'txt')}")
        try:
            c=input(f"  💾 {y.name} oluşturulsun mu? [Enter=E/h/yol]: ").strip().lower()
        except EOFError: return
        if c.startswith("h"): renk("     ↷ atlandı.",C.DIM); continue
        if c and not c.startswith("e"):
            ny=guvenli_yol(c)
            if ny is None: renk("     ✖ geçersiz yol.",C.RED); continue
            y=ny
        y.parent.mkdir(parents=True,exist_ok=True)
        y.write_text(kod.rstrip()+"\n",encoding="utf-8")
        renk(f"     ✔ {y.resolve()} ({y.stat().st_size:,} bayt)",C.GRN)
        kayitlar.append(str(y))

def calistir(arg):
    yol=Path(arg)
    if not yol.exists():
        c=WORKSPACE/arg
        yol=c if c.exists() else yol
    if not yol.exists(): renk(f"  ✖ Bulunamadı: {arg}",C.RED); return
    if yol.suffix!=".py":
        renk("  ⚠ Güvenlik: sadece .py çalıştırılır.",C.YLW); return
    if not input(f"  ⚡ {yol.name} çalıştırılsın mı? [E/h]: ").lower().startswith("e"): return
    print(C.DIM+"─"*54+C.R)
    r=subprocess.run([sys.executable,str(yol)])
    print(C.DIM+"─"*54+C.R)
    renk(f"  ↩ çıkış kodu: {r.returncode}",C.DIM)


# ════════════════════════ SOHBET ════════════════════════
def yanit_al(api,gecmis,model,mx,temp):
    print(f"\n{C.GRN}{C.B}🛰 {api.ad}·{model}{C.R}"
          f"{C.DIM}  (temp {temp} · {mx:,} token)…"+C.R)
    parc=[]; acik=False
    for tur,veri in api.akis(gecmis,model,mx,temp):
        if tur=="dusun":
            if veri.strip():
                if not acik: sys.stdout.write(C.DIM+"💭 "); acik=True
                sys.stdout.write(veri); sys.stdout.flush()
        elif tur=="metin":
            if acik: print(C.R,end=""); acik=False
            sys.stdout.write(veri); sys.stdout.flush(); parc.append(veri)
        elif tur=="bitti":
            if acik: print(C.R,end="")
            return "".join(parc),veri
    if acik: print(C.R,end="")
    return "".join(parc),None

YARDIM=f"""{C.CYN}╭─ Komutlar{'─'*44}╮{C.R}
  {C.B}/saglayici{C.R}     sağlayıcı/model değiş      {C.B}/model{C.R}       sadece model değiş
  {C.B}/token N{C.R}       maks çıktı token           {C.B}/sicaklik X{C.R}  0.0-2.0
  {C.B}/anahtar kod key{C.R}  anahtar güncelle        {C.B}/kurulum{C.R}     sihirbaz
  {C.B}/dosyalar{C.R}      oluşturulan dosyalar       {C.B}/calistir f.py{C.R}  çalıştır
  {C.B}/kaydet{C.R}        yanıtı .md kaydet          {C.B}/calisma{C.R}     dizin göster
  {C.B}/yeni{C.R}          sohbet sıfırla             {C.B}/yardim{C.R}       bu menü
  {C.B}/cikis{C.R}         çıkış
{C.CYN}╰{'─'*59}╯{C.R}"""


def ana():
    print(BANNER)
    keys=kurulum(anahtarlar_yukle())
    if not any(keys.get(k) for k in ADLAR):
        renk("Hiç anahtar yok — çıkılıyor.",C.RED); return

    kod=menu_saglayici(keys)
    api=API_SINIFLARI[kod](); api.key=keys[kod]
    model,mx=menu_model(kod,api)
    dur={"kod":kod,"model":model,"mx":mx,"temp":0.7,
         "gecmis":[],"kayitlar":[],"son":""}

    print(YARDIM)
    renk(f"\n▸ Aktif: {ADLAR[kod]}·{dur['model']} │ dizin: {WORKSPACE.resolve()}\n",C.BLU)

    while True:
        try: soru=input(f"{C.CYN}{C.B}◆ sen ▸ {C.R}").strip()
        except (KeyboardInterrupt,EOFError):
            renk("\n👋 MatuGravity kapatıldı.",C.MAG); return
        if not soru: continue

        if soru.startswith("/"):
            cmd,*rest=soru.split(maxsplit=1); arg=rest[0].strip() if rest else ""
            if cmd in("/cikis","/exit"): renk("👋 Görüşürüz!",C.MAG); return
            elif cmd=="/yardim": print(YARDIM)
            elif cmd=="/yeni": dur["gecmis"].clear(); renk("✨ Bağlam sıfırlandı.",C.GRN)
            elif cmd=="/saglayici":
                nk=menu_saglayici(keys)
                napi=API_SINIFLARI[nk](); napi.key=keys[nk]
                nm,nmx=menu_model(nk,napi)
                dur.update(kod=nk,model=nm,mx=nmx); api=napi
                renk(f"✔ Artık: {ADLAR[nk]}·{nm} (sohbet korundu)",C.GRN)
            elif cmd=="/model":
                nm,nmx=menu_model(dur["kod"],api)
                dur.update(model=nm,mx=nmx); renk(f"✔ Model: {nm}",C.GRN)
            elif cmd=="/token":
                try: dur["mx"]=max(256,int(arg)); renk(f"✔ {dur['mx']:,}",C.GRN)
                except ValueError: renk("Örn: /token 65536",C.RED)
            elif cmd=="/sicaklik":
                try: dur["temp"]=round(min(2,max(0,float(arg))),2); renk(f"✔ {dur['temp']}",C.GRN)
                except ValueError: renk("Örn: /sicaklik 0.3",C.RED)
            elif cmd=="/anahtar":
                try:
                    k,v=arg.split(maxsplit=1)
                    if k in ADLAR:
                        keys[k]=v.strip(); anahtar_kaydet(keys)
                        renk(f"✔ {ADLAR[k]} anahtarı güncellendi.",C.GRN)
                    else: renk("Kodlar: deepseek|grok|claude|gemini",C.RED)
                except ValueError: renk("Örn: /anahtar gemini AIza...",C.RED)
            elif cmd=="/kurulum": kurulum(keys,zorla=True)
            elif cmd=="/dosyalar":
                for f in dur["kayitlar"]: renk(f"  📄 {f}",C.CYN)
                if not dur["kayitlar"]: renk("  Henüz dosya yok.",C.DIM)
            elif cmd=="/calisma": renk(f"  {WORKSPACE.resolve()}",C.CYN)
            elif cmd=="/calistir": calistir(arg)
            elif cmd=="/kaydet":
                WORKSPACE.mkdir(exist_ok=True)
                f=WORKSPACE/f"yanit_{datetime.now():%H%M%S}.md"
                f.write_text(dur["son"],encoding="utf-8"); renk(f"✔ {f.resolve()}",C.GRN)
            else: renk("Bilinmeyen komut → /yardim",C.RED)
            continue

        dur["gecmis"].append({"role":"user","content":soru})
        while dur["gecmis"] and dur["gecmis"][0]["role"]!="user": dur["gecmis"].pop(0)
        if len(dur["gecmis"])>MAX_GECMIS: dur["gecmis"]=dur["gecmis"][-MAX_GECMIS:]
        try:
            yanit,bitis=yanit_al(api,dur["gecmis"],dur["model"],dur["mx"],dur["temp"])
        except KeyboardInterrupt:
            renk("\n⏹ İptal.",C.YLW); dur["gecmis"].pop(); continue
        if getattr(api,"yeni_model",None):
            dur["model"]=api.yeni_model
            renk(f"📌 Aktif model: {dur['model']}",C.BLU)
        if bitis in ("length","max_tokens","MAX_TOKENS"):
            renk("\n⚠ Limit! '/token 65536' + 'devam et'",C.YLW)
        dur["son"]=yanit
        if yanit:
            dur["gecmis"].append({"role":"assistant","content":yanit})
            dosyalari_isle(yanit,dur["kayitlar"])

if __name__=="__main__":
    try: ana()
    except KeyboardInterrupt: renk("\n⛔ Kesildi.",C.RED)
