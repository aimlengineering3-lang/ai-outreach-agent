import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.db.session import SessionLocal
from src.db.models import SenderAccount
from src.email.health_monitor import compute_capacity

session = SessionLocal()
try:
    accounts = session.query(SenderAccount).all()

    if not accounts:
        print("Koi sender account hi DB mein nahi hai!")
    else:
        for acc in accounts:
            # Sahi Call: session aur account dono pass kiye hain
            cap = compute_capacity(session, acc)
            session.commit()  # Daily reset changes ko save karne ke liye

            print(
                f"{acc.email:30} status={acc.status:10} "
                f"daily_limit={acc.daily_limit:4} sent_today={acc.sent_today:4} "
                f"bounce_7d={acc.bounce_count_7d:3} complaints_7d={acc.spam_complaint_count_7d:2} "
                f"=> available_capacity={cap.available_capacity:4} reason={cap.reason}"
            )
except Exception as e:
    session.rollback()
    raise e
finally:
    session.close()