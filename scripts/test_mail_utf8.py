import os
from dotenv import load_dotenv
from services.mail import send_mail_ex

load_dotenv()

def main() -> None:
    to = os.getenv("ADMIN_EMAIL", "")
    ok, err = send_mail_ex(
        to=to,
        subject="Тест кириллица",
        text="Привет! Это тест письма с кириллицей (без эмодзи).",
    )
    print("OK" if ok else f"FAIL: {err}")

if __name__ == "__main__":
    main()
