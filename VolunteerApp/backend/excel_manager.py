
from pathlib import Path
from threading import RLock
from uuid import uuid4
from datetime import datetime, date
import os
import tempfile

import pandas as pd
import bcrypt

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

FILES = {
    "users": DATA_DIR / "Users.xlsx",
    "shifts": DATA_DIR / "Shifts.xlsx",
    "signups": DATA_DIR / "Signups.xlsx",
    "hours": DATA_DIR / "Hours.xlsx",
}

COLUMNS = {
    "users": [
        "user_id", "name", "email", "password_hash",
        "role", "created_at"
    ],
    "shifts": [
        "shift_id", "title", "description", "date",
        "start_time", "end_time", "location",
        "capacity", "status", "created_by"
    ],
    "signups": [
        "signup_id", "user_id", "shift_id",
        "signup_date", "status"
    ],
    "hours": [
        "hour_id", "user_id", "shift_id",
        "hours", "status", "verified_by", "submitted_at"
    ]
}

# Protects read-modify-write operations within one Python process.
DATA_LOCK = RLock()


def initialize_files():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with DATA_LOCK:
        for name, path in FILES.items():
            if not path.exists() or path.stat().st_size == 0:
                pd.DataFrame(columns=COLUMNS[name]).to_excel(
                    path, index=False, engine="openpyxl"
                )


def _read_unlocked(name):
    if name not in FILES:
        raise ValueError("Unknown data file")

    path = FILES[name]

    if not path.exists() or path.stat().st_size == 0:
        df = pd.DataFrame(columns=COLUMNS[name])
        _save_unlocked(name, df)
        return df

    try:
        df = pd.read_excel(
            path, dtype=str, engine="openpyxl"
        ).fillna("")
    except Exception as e:
        raise RuntimeError(
            f"Unable to read {path.name}. "
            f"Close the file in Excel and check that it is valid. {e}"
        )

    for column in COLUMNS[name]:
        if column not in df.columns:
            df[column] = ""

    return df[COLUMNS[name]]


def _save_unlocked(name, dataframe):
    if name not in FILES:
        raise ValueError("Unknown data file")

    path = FILES[name]
    path.parent.mkdir(parents=True, exist_ok=True)

    df = dataframe.copy()

    for column in COLUMNS[name]:
        if column not in df.columns:
            df[column] = ""

    df = df[COLUMNS[name]]

    # Write to a temporary file before replacing the original.
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".xlsx",
            dir=path.parent,
            delete=False
        ) as temp:
            temp_path = Path(temp.name)

        df.to_excel(
            temp_path,
            index=False,
            engine="openpyxl"
        )

        os.replace(temp_path, path)

    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def read_data(name):
    with DATA_LOCK:
        return _read_unlocked(name)


def save_data(name, dataframe):
    with DATA_LOCK:
        _save_unlocked(name, dataframe)


# -------------------------
# USER MANAGEMENT
# -------------------------

def create_user(name, email, password, role="volunteer"):
    name = name.strip()
    email = email.strip().lower()

    if role not in ("volunteer", "admin"):
        return False, "Invalid account role."

    if not name or not email:
        return False, "Name and email are required."

    if len(password) < 10:
        return False, "Password must be at least 10 characters."

    with DATA_LOCK:
        users = _read_unlocked("users")

        if users["email"].str.lower().eq(email).any():
            return False, "An account with this email already exists."

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        new_user = {
            "user_id": uuid4().hex,
            "name": name,
            "email": email,
            "password_hash": password_hash,
            "role": role,
            "created_at": datetime.now().isoformat()
        }

        users = pd.concat(
            [users, pd.DataFrame([new_user])],
            ignore_index=True
        )

        _save_unlocked("users", users)

    return True, "Account created successfully!"



def authenticate_user(email, password, expected_role):

    if expected_role not in ("volunteer", "admin"):
        return None

    if not email or not password:
        return None

    users = read_data("users")
    email = email.strip().lower()

    matching = users[
        (users["email"].str.strip().str.lower() == email) &
        (users["role"].str.strip() == expected_role)
    ]

    # Do not print matching: it contains password hashes.
    if matching.empty:
        return None

    user = matching.iloc[0]

    try:
        valid = bcrypt.checkpw(
            password.encode("utf-8"),
            user["password_hash"].encode("utf-8")
        )
    except (ValueError, TypeError):
        return None

    if not valid:
        return None

    return {
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"]
    }


def create_initial_admin(email, password):
    email = email.strip().lower()

    if not email or not password:
        return False, "Administrator email and password are required."

    if len(password.encode("utf-8")) > 72:
        return False, "Administrator password exceeds bcrypt's 72-byte limit."

    with DATA_LOCK:
        users = _read_unlocked("users")

        matching = users[
            users["email"].str.strip().str.lower() == email
        ]

        # Prevent accidentally converting a volunteer account.
        if not matching.empty:
            user = matching.iloc[0]

            if user["role"] != "admin":
                return False, (
                    "This email already belongs to a volunteer account. "
                    "Use a different administrator email."
                )

            # Synchronize the existing administrator password
            # with the password configured in Streamlit secrets.
            password_hash = bcrypt.hashpw(
                password.encode("utf-8"),
                bcrypt.gensalt()
            ).decode("utf-8")

            users.loc[
                users["user_id"] == user["user_id"],
                "password_hash"
            ] = password_hash

            _save_unlocked("users", users)

            return True, "Administrator account synchronized."

        # Create a new administrator.
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        new_admin = {
            "user_id": uuid4().hex,
            "name": "Administrator",
            "email": email,
            "password_hash": password_hash,
            "role": "admin",
            "created_at": datetime.now().isoformat()
        }

        users = pd.concat(
            [users, pd.DataFrame([new_admin])],
            ignore_index=True
        )

        _save_unlocked("users", users)

    return True, "Administrator account created successfully!"



def update_profile(user_id, name):
    with DATA_LOCK:
        users = _read_unlocked("users")
        match = users["user_id"] == user_id

        if not match.any():
            return False, "User not found."

        users.loc[match, "name"] = name.strip()
        _save_unlocked("users", users)

    return True, "Profile updated."


# -------------------------
# SHIFT MANAGEMENT
# -------------------------

def create_shift(
    title, description, shift_date,
    start_time, end_time, location,
    capacity, created_by
):
    if not title.strip() or not location.strip():
        return False, "Title and location are required."

    if int(capacity) < 1:
        return False, "Capacity must be at least 1."

    if end_time <= start_time:
        return False, "End time must be after start time."

    with DATA_LOCK:
        shifts = _read_unlocked("shifts")

        new_shift = {
            "shift_id": uuid4().hex[:10],
            "title": title.strip(),
            "description": description.strip(),
            "date": str(shift_date),
            "start_time": str(start_time),
            "end_time": str(end_time),
            "location": location.strip(),
            "capacity": str(int(capacity)),
            "status": "Open",
            "created_by": created_by
        }

        shifts = pd.concat(
            [shifts, pd.DataFrame([new_shift])],
            ignore_index=True
        )

        _save_unlocked("shifts", shifts)

    return True, "Shift created successfully!"


def update_shift(shift_id, title, description, shift_date,
                 start_time, end_time, location, capacity):

    if not title.strip() or not location.strip():
        return False, "Title and location are required."

    if int(capacity) < 1:
        return False, "Capacity must be at least 1."

    if end_time <= start_time:
        return False, "End time must be after start time."

    with DATA_LOCK:
        shifts = _read_unlocked("shifts")
        signups = _read_unlocked("signups")

        match = shifts["shift_id"] == shift_id

        if not match.any():
            return False, "Shift not found."

        active = signups[
            (signups["shift_id"] == shift_id) &
            (signups["status"] == "Signed Up")
        ]

        if int(capacity) < len(active):
            return False, "Capacity cannot be lower than existing signups."

        shifts.loc[match, [
            "title", "description", "date",
            "start_time", "end_time", "location", "capacity"
        ]] = [
            title.strip(), description.strip(), str(shift_date),
            str(start_time), str(end_time),
            location.strip(), str(int(capacity))
        ]

        _save_unlocked("shifts", shifts)

    return True, "Shift updated successfully!"


def cancel_shift(shift_id):
    with DATA_LOCK:
        shifts = _read_unlocked("shifts")
        match = shifts["shift_id"] == shift_id

        if not match.any():
            return False, "Shift not found."

        shifts.loc[match, "status"] = "Cancelled"
        _save_unlocked("shifts", shifts)

    return True, "Shift cancelled."


# -------------------------
# VOLUNTEER SIGNUPS
# -------------------------

def signup_for_shift(user_id, shift_id):
    with DATA_LOCK:
        shifts = _read_unlocked("shifts")
        signups = _read_unlocked("signups")

        match = shifts[shifts["shift_id"] == shift_id]

        if match.empty:
            return False, "Shift not found."

        shift = match.iloc[0]

        if shift["status"] != "Open":
            return False, "This shift is not available."

        if pd.to_datetime(shift["date"]).date() < date.today():
            return False, "This shift has already passed."

        existing = signups[
            (signups["user_id"] == user_id) &
            (signups["shift_id"] == shift_id) &
            (signups["status"] == "Signed Up")
        ]

        if not existing.empty:
            return False, "You are already signed up."

        active = signups[
            (signups["shift_id"] == shift_id) &
            (signups["status"] == "Signed Up")
        ]

        if len(active) >= int(shift["capacity"]):
            return False, "This shift is full."

        new_signup = {
            "signup_id": uuid4().hex,
            "user_id": user_id,
            "shift_id": shift_id,
            "signup_date": datetime.now().isoformat(),
            "status": "Signed Up"
        }

        signups = pd.concat(
            [signups, pd.DataFrame([new_signup])],
            ignore_index=True
        )

        _save_unlocked("signups", signups)

    return True, "You successfully signed up!"


def cancel_signup(user_id, shift_id):
    with DATA_LOCK:
        signups = _read_unlocked("signups")

        match = (
            (signups["user_id"] == user_id) &
            (signups["shift_id"] == shift_id) &
            (signups["status"] == "Signed Up")
        )

        if not match.any():
            return False, "Active signup not found."

        signups.loc[match, "status"] = "Cancelled"
        _save_unlocked("signups", signups)

    return True, "Signup cancelled."


# -------------------------
# VOLUNTEER HOURS
# -------------------------

def submit_hours(user_id, shift_id, hours):
    try:
        hours = float(hours)
    except (ValueError, TypeError):
        return False, "Enter a valid number of hours."

    if not 0 < hours <= 24:
        return False, "Hours must be greater than 0 and at most 24."

    with DATA_LOCK:
        shifts = _read_unlocked("shifts")
        signups = _read_unlocked("signups")
        records = _read_unlocked("hours")

        shift = shifts[shifts["shift_id"] == shift_id]

        if shift.empty:
            return False, "Shift not found."

        shift = shift.iloc[0]

        if pd.to_datetime(shift["date"]).date() > date.today():
            return False, "You cannot submit hours for a future shift."

        signup = signups[
            (signups["user_id"] == user_id) &
            (signups["shift_id"] == shift_id) &
            (signups["status"] == "Signed Up")
        ]

        if signup.empty:
            return False, "You must have signed up for this shift."

        previous = records[
            (records["user_id"] == user_id) &
            (records["shift_id"] == shift_id)
        ]

        if not previous.empty:
            last_status = previous.iloc[-1]["status"]

            if last_status in ("Pending", "Approved"):
                return False, "Hours have already been submitted."

            # Allow resubmission after rejection.
            records = records.drop(previous.index)

        new_record = {
            "hour_id": uuid4().hex,
            "user_id": user_id,
            "shift_id": shift_id,
            "hours": str(hours),
            "status": "Pending",
            "verified_by": "",
            "submitted_at": datetime.now().isoformat()
        }

        records = pd.concat(
            [records, pd.DataFrame([new_record])],
            ignore_index=True
        )

        _save_unlocked("hours", records)

    return True, "Hours submitted for administrator approval."


def review_hours(hour_id, decision, admin_email):
    if decision not in ("Approved", "Rejected"):
        return False, "Invalid decision."

    with DATA_LOCK:
        records = _read_unlocked("hours")
        match = records["hour_id"] == hour_id

        if not match.any():
            return False, "Record not found."

        if records.loc[match, "status"].iloc[0] != "Pending":
            return False, "This record has already been reviewed."

        records.loc[match, "status"] = decision
        records.loc[match, "verified_by"] = admin_email

        _save_unlocked("hours", records)

    return True, f"Hours {decision.lower()} successfully."
