"""Notificação visual no Windows (toast) para chamar a atenção do usuário logado.

Usada pelo `atualizar.py` quando a rodada agendada precisa de um login
interativo no navegador (renovação proativa ou token expirado). Falha em
silêncio: a notificação é conveniência, nunca condição para a rodada.
"""

from __future__ import annotations

import logging
import os
import subprocess

log = logging.getLogger(__name__)

# AppId do PowerShell: já registrado no Windows, então o toast aparece sem
# precisar cadastrar um aplicativo próprio.
_APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"

_SCRIPT = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$textos = $xml.GetElementsByTagName("text")
$textos.Item(0).AppendChild($xml.CreateTextNode($env:TOAST_TITULO)) | Out-Null
$textos.Item(1).AppendChild($xml.CreateTextNode($env:TOAST_MENSAGEM)) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:TOAST_APPID).Show($toast)
"""


def toast(titulo: str, mensagem: str) -> bool:
    """Exibe uma notificação do Windows. Retorna False se não conseguiu (sem exceção)."""
    env = dict(os.environ, TOAST_TITULO=titulo, TOAST_MENSAGEM=mensagem, TOAST_APPID=_APP_ID)
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT],
            env=env, capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.warning("Notificação não exibida: %s", exc)
        return False
    if r.returncode != 0:
        log.warning("Notificação não exibida: %s", (r.stderr or "").strip()[:300])
        return False
    return True
