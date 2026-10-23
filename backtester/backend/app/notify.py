"""Canaux de notification : toast Windows natif et Telegram (optionnel).

- Toast Windows : via PowerShell et l'API WinRT, sans dépendance à installer.
  Sur un autre système, le canal se déclare indisponible (pas d'erreur).
- Telegram : nécessite un jeton de bot (clé « telegram » page Configuration,
  obtenu auprès de @BotFather) et un chat_id (paramètre notifications).
"""
from __future__ import annotations

import logging
import platform
import subprocess
from xml.sax.saxutils import escape

import httpx

from .config import get_api_key, load_settings
from .engine.scoring import BIAS_LABELS_FR

log = logging.getLogger("backtester.notify")

_TOAST_PS = r"""
$null = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
$null = [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime]
$null = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml(@'
<toast scenario="reminder"><visual><binding template="ToastGeneric"><text>__TITLE__</text><text>__BODY__</text></binding></visual></toast>
'@)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("S&P 500 Backtester").Show($toast)
"""


def send_windows_toast(title: str, body: str) -> tuple[bool, str]:
    if platform.system() != "Windows":
        return False, "Toast disponible uniquement sous Windows (canal ignoré ici)."
    script = _TOAST_PS.replace("__TITLE__", escape(title)).replace("__BODY__", escape(body))
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=30)
        if proc.returncode != 0:
            return False, f"PowerShell: {proc.stderr.strip()[:200]}"
        return True, "Toast Windows envoyé."
    except Exception as e:  # noqa: BLE001
        return False, f"Toast impossible: {e}"


def send_telegram(text: str) -> tuple[bool, str]:
    token = get_api_key("telegram")
    chat_id = load_settings().get("notifications", {}).get("telegram_chat_id", "")
    if not token:
        return False, "Jeton de bot Telegram non configuré."
    if not chat_id:
        return False, "telegram_chat_id non renseigné (paramètres de notification)."
    try:
        r = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                       json={"chat_id": chat_id, "text": text}, timeout=20)
        if r.status_code != 200:
            return False, f"Telegram HTTP {r.status_code}: {r.text[:150]}"
        return True, "Message Telegram envoyé."
    except httpx.HTTPError as e:
        return False, f"Telegram injoignable: {e}"


def build_verdict_message(session: dict) -> tuple[str, str]:
    """(titre, corps) du message de notification pour un verdict live."""
    label = BIAS_LABELS_FR.get(session["predicted"], session["predicted"])
    if session.get("insufficient"):
        label = "NEUTRE — données insuffisantes"
    title = f"S&P 500 {session['date']} : {label}"
    n_factors = sum(1 for f in session.get("factors", []) if f.get("available"))
    status = "provisoire" if session.get("provisional") else "figé 15h29 Paris"
    body = (f"Score {session['score']:+.0f}, confiance {session['confidence']}/100 "
            f"({status}). {n_factors}/11 facteurs, "
            f"{len(session.get('news', []))} actualités. "
            f"Mesure 9h30 NY → minuit Paris.")
    return title, body


def notify_verdict(session: dict) -> dict:
    """Envoie le verdict sur tous les canaux actifs ; renvoie le détail."""
    title, body = build_verdict_message(session)
    results = {"toast": None, "telegram": None}
    ok_t, msg_t = send_windows_toast(title, body)
    results["toast"] = {"ok": ok_t, "message": msg_t}
    if get_api_key("telegram"):
        ok_g, msg_g = send_telegram(f"{title}\n{body}")
        results["telegram"] = {"ok": ok_g, "message": msg_g}
    log.info("notification verdict: %s | toast=%s telegram=%s", title,
             results["toast"], results["telegram"])
    return {"title": title, "body": body, "channels": results}
