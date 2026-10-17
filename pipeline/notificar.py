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
    """Dispara uma notificação do Windows sem esperar por ela.

    O PowerShell pode levar dezenas de segundos para carregar o WinRT (em
    17/10/2026 passou de 30 s e atrasou a rodada), então o processo roda solto:
    a rodada segue na hora e o aviso aparece quando o PowerShell terminar.
    Retorna False só se nem foi possível iniciar o PowerShell.
    """
    env = dict(os.environ, TOAST_TITULO=titulo, TOAST_MENSAGEM=mensagem, TOAST_APPID=_APP_ID)
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        log.warning("Notificação não exibida: %s", exc)
        return False
    return True
