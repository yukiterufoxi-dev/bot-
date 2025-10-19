"""
Универсальный SMTP-слой.
По умолчанию: Timeweb 465/SSL. Читает настройки из .env.

Быстрый старт:
    from services.mail import send_mail
    send_mail("admin@example.com", "Тест", "Привет!")

Ключевые фичи:
- Валидация адресов (email-validator)
- cc / bcc / reply_to
- Вложения: (filename, bytes|str_path, mime)
- Повторы с бэкоффом
- DRY RUN через MAIL_DRY_RUN=1 (пишет в логи, но не шлёт)
"""

from __future__ import annotations

import os
import ssl
import time
import smtplib
import logging
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Iterable, Optional, Tuple, Union

try:
    from email_validator import validate_email, EmailNotValidError  # type: ignore
except Exception:  # пакет есть в requirements.txt; если вдруг нет — отправка без нормализации
    validate_email, EmailNotValidError = None, Exception  # type: ignore

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

Attachment = Tuple[str, Union[bytes, str], str]  # (filename, content_bytes | file_path, mime)


@dataclass(frozen=True)
class SMTPConfig:
    host: str = os.getenv("SMTP_HOST", "smtp.timeweb.ru")
    port: int = int(os.getenv("SMTP_PORT", "465"))
    user: str = os.getenv("SMTP_USER", "")
    password: str = os.getenv("SMTP_PASS", "")
    from_email: str = os.getenv("FROM_EMAIL", os.getenv("ADMIN_EMAIL", ""))
    timeout: float = float(os.getenv("SMTP_TIMEOUT", "10"))  # seconds
    retries: int = int(os.getenv("SMTP_RETRIES", "1"))
    dry_run: bool = os.getenv("MAIL_DRY_RUN", "0") in {"1", "true", "yes"}


def _as_list(x: Union[str, Iterable[str]]) -> list[str]:
    if isinstance(x, (list, tuple, set)):
        return [str(i) for i in x if str(i).strip()]
    return [str(x)] if str(x).strip() else []


def _normalize_address(addr: str) -> str:
    """Нормализуем адрес (если есть email-validator). Иначе возвращаем как есть."""
    if not addr:
        return addr
    if validate_email:
        try:
            return validate_email(addr, allow_smtputf8=True).email
        except EmailNotValidError as e:
            raise ValueError(f"Некорректный email '{addr}': {e}") from e
    return addr


def _normalize_many(addrs: Iterable[str]) -> list[str]:
    return [_normalize_address(a) for a in addrs if a]


def _build_message(
    to: Union[str, Iterable[str]],
    subject: str,
    text: str,
    *,
    html: Optional[str],
    from_email: str,
    reply_to: Optional[str],
    cc: Optional[Iterable[str]],
    bcc: Optional[Iterable[str]],
    attachments: Optional[Iterable[Attachment]],
) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email

    to_list = _normalize_many(_as_list(to))
    if not to_list:
        raise ValueError("Пустой список получателей (to).")

    cc_list = _normalize_many(_as_list(cc or []))
    bcc_list = _normalize_many(_as_list(bcc or []))

    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    if reply_to:
        msg["Reply-To"] = _normalize_address(reply_to)

    # Тело письма
    if html:
        msg.set_content(text or "")
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(text or "")

    # Вложения
    if attachments:
        for filename, content, mime in attachments:
            maintype, _, subtype = (mime.partition("/") if "/" in mime else (mime, "", "octet-stream"))
            if isinstance(content, str):  # это путь к файлу
                with open(content, "rb") as fh:
                    data = fh.read()
            else:
                data = content
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

    # EmailMessage не хранит Bcc — добавим как список возврата
    # Вернём расширенный список адресатов для отправки:
    msg._all_rcpt = to_list + cc_list + bcc_list  # type: ignore[attr-defined]
    return msg


def _send(msg: EmailMessage, cfg: SMTPConfig) -> None:
    """Непосредственная отправка (или dry run). Поднимает исключение при ошибке."""
    rcpts: list[str] = getattr(msg, "_all_rcpt", [])  # type: ignore[attr-defined]
    if cfg.dry_run:
        logger.info("[MAIL DRY RUN] to=%s subject=%s", rcpts, msg["Subject"])
        return

    context = ssl.create_default_context()
    attempt = 0
    delay = 1.5
    while True:
        try:
            with smtplib.SMTP_SSL(cfg.host, cfg.port, context=context, timeout=cfg.timeout) as smtp:
                if cfg.user and cfg.password:
                    smtp.login(cfg.user, cfg.password)
                smtp.send_message(msg, to_addrs=rcpts)
                logger.info("send_mail: письмо отправлено на %s", ", ".join(rcpts))
                return
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, TimeoutError) as e:
            attempt += 1
            if attempt > cfg.retries:
                raise
            logger.warning("send_mail: временная ошибка (%s), повтор через %.1fs (%d/%d)", e, delay, attempt, cfg.retries)
            time.sleep(delay)
            delay *= 2
        except Exception:
            # пробрасываем дальше — верхний уровень решит, что делать
            raise


def send_mail(
    to: Union[str, Iterable[str]],
    subject: str,
    text: str,
    *,
    html: Optional[str] = None,
    attachments: Optional[Iterable[Attachment]] = None,
    reply_to: Optional[str] = None,
    cc: Optional[Iterable[str]] = None,
    bcc: Optional[Iterable[str]] = None,
    cfg: Optional[SMTPConfig] = None,
) -> bool:
    """
    Отправка письма. Возвращает True/False, ошибки логируются.
    """
    ok, _ = send_mail_ex(
        to=to, subject=subject, text=text, html=html,
        attachments=attachments, reply_to=reply_to, cc=cc, bcc=bcc, cfg=cfg
    )
    return ok


def send_mail_ex(
    to: Union[str, Iterable[str]],
    subject: str,
    text: str,
    *,
    html: Optional[str] = None,
    attachments: Optional[Iterable[Attachment]] = None,
    reply_to: Optional[str] = None,
    cc: Optional[Iterable[str]] = None,
    bcc: Optional[Iterable[str]] = None,
    cfg: Optional[SMTPConfig] = None,
) -> tuple[bool, Optional[str]]:
    """
    Расширенная версия: возвращает (ok, error_message).
    Полезно в местах, где нужно показать пользователю понятную причину.
    """
    cfg = cfg or SMTPConfig()
    try:
        if not cfg.from_email:
            raise ValueError("FROM_EMAIL/ADMIN_EMAIL не указан в .env")
        msg = _build_message(
            to=to, subject=subject, text=text, html=html,
            from_email=_normalize_address(cfg.from_email),
            reply_to=reply_to, cc=cc, bcc=bcc, attachments=attachments,
        )
        _send(msg, cfg)
        return True, None
    except Exception as e:
        logger.error("send_mail: ошибка отправки: %s", e)
        return False, str(e)
