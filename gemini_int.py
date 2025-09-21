from google import genai
import json
from firebase_config import db
from datetime import datetime

client = genai.Client(api_key="AIzaSyB18-oAXbC6Y26-QZb-0jMy2EGd6RV2rig")
def get_existing_categories(uid):
    """Fetch all categories for a user from Firestore"""
    categories_ref = db.collection("users").document(uid).collection("categories")
    docs = categories_ref.stream()
    return [doc.id for doc in docs]  # category names are document IDs

def parse_expense(uid, text):
    """
    Parse text with Gemini, using existing categories.
    """
    try:
        # Get user’s categories
        existing_categories = get_existing_categories(uid)
        categories_list = ", ".join(existing_categories) if existing_categories else "None yet"

        prompt = f"""
        Extract expense details from the following text and respond ONLY in JSON format.
        Text: '{text}'
        
        JSON keys: name, amount, category, merchant, date, currency.

        - Today's date is {datetime.now().strftime("%Y-%m-%d")}.
        - Default currency: INR.
        - If no date is mentioned, infer (yesterday, last Monday, etc.).
        - If not an expense → make related : False else True.
        - Available categories: [{categories_list}]. 
        - If the expense fits one of them, pick it. 
        - If none fit, create a new category.
        - 
        """

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        raw_text = response.text.strip()
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start == -1 or end == -1:
            return None

        expense_data = json.loads(raw_text[start:end])
        if expense_data.get("related") == False:
            print("Not related to expense.")
            return None
        # Ensure date exists
        print(expense_data)
        if not expense_data.get("date"):
            expense_data["date"] = datetime.now().strftime("%Y-%m-%d")

        return expense_data

    except Exception as e:
        print(f"Error parsing expense: {e}")
        return None
def safe_parse_expense(uid, text):
    expense_data = parse_expense(uid, text)
    if not expense_data:
        return None

    # Ensure required keys exist
    expense_data.setdefault("name", "Unknown")
    expense_data.setdefault("amount", 0)
    expense_data.setdefault("category", "Uncategorized")
    expense_data.setdefault("merchant", "Unknown")
    expense_data.setdefault("currency", "INR")

    # Validate amount
    try:
        expense_data["amount"] = float(expense_data["amount"])
        if expense_data["amount"] <= 0:
            return None
    except Exception:
        return None

    # Validate date format
    date_str = expense_data.get("date")
    try:
        # Only take YYYY-MM-DD if extra time is included
        date_str = date_str.split()[0]
        expense_data["date"] = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
    except Exception:
        expense_data["date"] = datetime.now().strftime("%Y-%m-%d")

    return expense_data
