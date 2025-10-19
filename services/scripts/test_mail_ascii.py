import os
from dotenv import load_dotenv
from services.mail import send_mail_ex

# читаем переменные из /opt/karta-clean/.env или из ./.env при локальном запуске
load_dotenv()

def main() -> None:
    to = os.getenv("ADMIN_EMAIL", "")
    ok, err = send_mail_ex(
        to=to,
        subject="SMTP test",
        text="If you see this, SMTP works.",
    )
    print("OK" if ok else f"FAIL: {err}")

if __name__ == "__main__":
    main()
