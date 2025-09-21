import time
import base64
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from firebase_config import db
from gemini_int import parse_expense

import os
import json

creds_data = json.loads(os.environ["GOOGLE_OAUTH_JSON"])


CLIENT_ID = creds_data["installed"]["client_id"]
CLIENT_SECRET = creds_data["installed"]["client_secret"]
TOKEN_URI = creds_data["installed"]["token_uri"]

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_full_email_body(msg_detail):
    payload = msg_detail.get("payload", {})
    if "parts" in payload:
        body_text = ""
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part["body"].get("data")
                if data:
                    body_text += base64.urlsafe_b64decode(data).decode(errors="ignore")
        return body_text
    else:
        body_data = payload.get("body", {}).get("data")
        if body_data:
            return base64.urlsafe_b64decode(body_data).decode(errors="ignore")
    return ""

from datetime import datetime

def update_category_totals(uid, expense):
    """Update monthly totals per category in Firestore"""
    try:
        category = expense.get("category", "Uncategorized")
        amount = float(expense.get("amount", 0))
        currency = expense.get("currency", "INR")

        # Ensure date exists, fallback to today
        expense_date = expense.get("date")
        if not expense_date:
            expense_date = datetime.now().strftime("%Y-%m-%d")

        # Convert to YYYY-MM
        month_key = datetime.strptime(expense_date, "%Y-%m-%d").strftime("%Y-%m")

        month_ref = (
            db.collection("users")
              .document(uid)
              .collection("categories")
              .document(category)
              .collection("months")
              .document(month_key)
        )

        snapshot = month_ref.get()
        if snapshot.exists:
            current_total = snapshot.to_dict().get("total_amount", 0)
        else:
            current_total = 0

        new_total = current_total + amount

        month_ref.set({
            "total_amount": new_total,
            "currency": currency,
            "updated_at": datetime.now()
        }, merge=True)

        print(f"      Updated {category} total for {month_key}: +{amount} {currency}")

    except Exception as e:
        print(f"  Error updating category totals: {e}")


def fetch_gmail_and_store():
    users = db.collection("users").stream()
    for user_doc in users:
        user_data = user_doc.to_dict()
        uid = user_doc.id
        print(f"\nProcessing user: {uid}")

        if "gmail_refresh_token" not in user_data:
            print(f"  No refresh token for user {uid}, skipping...")
            continue

        refresh_token = user_data["gmail_refresh_token"]

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=TOKEN_URI,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES
        )

        try:
            creds.refresh(Request())
            service = build("gmail", "v1", credentials=creds)

            result = service.users().messages().list(
                userId="me",
                q="in:inbox -in:sent",
                maxResults=5
            ).execute()

            messages = result.get("messages", [])
            print(f"  Found {len(messages)} messages")

            for msg in messages:
                msg_id = msg["id"]

                # Check if already processed
                existing = db.collection("users").document(uid).collection("emails").document(msg_id).get()
                if existing.exists:
                    print(f"    Message {msg_id} already processed, skipping.")
                    break

                msg_detail = service.users().messages().get(userId="me", id=msg_id).execute()
                full_body = get_full_email_body(msg_detail)
                print(f"    Email body snippet:\n{full_body[:200]}...\n")
                

                parsed_expense = parse_expense(uid,full_body)

                if parsed_expense:
                    # Store raw expense entry
                    db.collection("users").document(uid).collection("expenses").add(parsed_expense)

                    # Update category + monthly totals
                    # print(parsed_expense)
                    update_category_totals(uid, parsed_expense)

                    print(f"      Stored expense for message {msg_id}")

                # Mark message as processed (always)
                db.collection("users").document(uid).collection("emails").document(msg_id).set({"processed": True})
                print(f"    Marked message {msg_id} as processed")

        except Exception as e:
            print(f"  Failed to fetch messages for user {uid}: {e}")

if __name__ == "__main__":
    while True:
        try:
            fetch_gmail_and_store()
        except Exception as e:
            print(f"Error in main loop: {e}")
        time.sleep(5)  # Run every 1 minute
