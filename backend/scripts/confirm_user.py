import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from firebase_admin import auth

from services.firebase_client import get_firebase_app

email = sys.argv[1]
get_firebase_app()

user = auth.get_user_by_email(email)
auth.update_user(user.uid, email_verified=True)
print(f"Marked {email} as verified")
