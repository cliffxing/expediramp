# backend/scripts/confirm_user.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from services.supabase_client import get_supabase

email = sys.argv[1]
sb = get_supabase()

# Find user
users = sb.auth.admin.list_users()
user = next((u for u in users if u.email == email), None)
if not user:
    print(f"User {email} not found")
    sys.exit(1)

# Confirm them
sb.auth.admin.update_user_by_id(user.id, {"email_confirm": True})
print(f"Confirmed {email}")