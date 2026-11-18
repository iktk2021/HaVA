
import streamlit as st
import pandas as pd
from datetime import date, time
from io import BytesIO

from backend.excel_manager import (
    initialize_files,
    read_data,
    create_user,
    authenticate_user,
    create_initial_admin,
    create_shift,
    update_shift,
    cancel_shift,
    signup_for_shift,
    cancel_signup,
    submit_hours,
    review_hours,
    update_profile
)

# -------------------------
# APPLICATION CONFIGURATION
# -------------------------

st.set_page_config(
    page_title="VolunteerHub",
    page_icon="🤝",
    layout="wide"
)

initialize_files()

try:
    success, message = create_initial_admin(
        email=st.secrets["admin"]["email"],
        password=st.secrets["admin"]["password"]
    )

    if not success:
        st.error(message)
        st.stop()

except Exception as e:
    st.error(f"Administrator initialization error: {e}")
    st.stop()



# -------------------------
# SESSION STATE
# -------------------------

if "user" not in st.session_state:
    st.session_state.user = None

if "page" not in st.session_state:
    st.session_state.page = "Home"


# -------------------------
# STYLING
# -------------------------

st.markdown("""
<style>
.stApp {
    background: #F7F8FC;
}

.block-container {
    padding-top: 2rem;
}

h1, h2, h3 {
    color: #243B53;
}

div.stButton > button {
    border-radius: 9px;
    font-weight: 600;
    min-height: 40px;
}

[data-testid="stMetric"] {
    background: white;
    border: 1px solid #E5E7EB;
    padding: 18px;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)


# -------------------------
# HELPERS
# -------------------------

def logout():
    st.session_state.user = None
    st.session_state.page = "Home"
    st.rerun()


def get_data():
    return {
        "users": read_data("users"),
        "shifts": read_data("shifts"),
        "signups": read_data("signups"),
        "hours": read_data("hours")
    }


def shift_label(row):
    return (
        f"{row['title']} | {row['date']} | "
        f"{row['start_time']} | {row['location']}"
    )


def display_shift(row):
    st.markdown(f"### {row['title']}")
    st.write(f"📅 {row['date']}")
    st.write(
        f"🕒 {row['start_time']} – {row['end_time']}"
    )
    st.write(f"📍 {row['location']}")
    st.write(f"👥 Capacity: {row['capacity']}")
    if row["description"]:
        st.write(row["description"])


# -------------------------
# PUBLIC LANDING PAGE
# -------------------------

def home_page():

    st.title("🤝 VolunteerHub")
    st.subheader("Making community service easier.")

    st.write(
        "Find volunteer opportunities, organize shifts, "
        "and make a difference in your community,"
        f"{st.secrets['admin']['email']}"
        f"{st.secrets['admin']['password']}"
    )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        with st.container(border=True):
            st.subheader("🙋 Volunteers")
            st.write(
                "Browse opportunities, manage your shifts, "
                "and track your service hours."
            )

            if st.button("Volunteer Login", use_container_width=True):
                st.session_state.page = "Volunteer Login"
                st.rerun()

            if st.button(
                "Create an Account",
                use_container_width=True
            ):
                st.session_state.page = "Register"
                st.rerun()

    with col2:
        with st.container(border=True):
            st.subheader("🛡️ Administrators")
            st.write(
                "Create opportunities, manage volunteers, "
                "and oversee your organization."
            )

            if st.button(
                "Administrator Login",
                use_container_width=True
            ):
                st.session_state.page = "Administrator Login"
                st.rerun()


# -------------------------
# LOGIN
# -------------------------

def login_page(role):

    st.title(role)

    with st.form("login_form"):

        email = st.text_input("Email Address")
        password = st.text_input(
            "Password",
            type="password"
        )

        submitted = st.form_submit_button(
            "Log In",
            use_container_width=True
        )

        if submitted:

            user = authenticate_user(
                email,
                password,
                "admin" if role == "Administrator Login"
                else "volunteer"
            )

            if user:
                st.session_state.user = user
                st.session_state.page = "Dashboard"
                st.rerun()
            else:
                st.error("Incorrect email or password.")

    if st.button("Back to Home"):
        st.session_state.page = "Home"
        st.rerun()


# -------------------------
# REGISTRATION
# -------------------------

def register_page():

    st.title("Create Your Volunteer Account")

    with st.form("register_form"):

        name = st.text_input("Full Name")
        email = st.text_input("Email Address")
        password = st.text_input(
            "Password",
            type="password"
        )
        confirm = st.text_input(
            "Confirm Password",
            type="password"
        )

        submitted = st.form_submit_button(
            "Register",
            use_container_width=True
        )

        if submitted:

            if not name.strip() or not email.strip():
                st.error("Please complete all fields.")

            elif len(password) < 10:
                st.error("Password must be at least 10 characters.")

            elif password != confirm:
                st.error("Passwords do not match.")

            else:
                success, message = create_user(
                    name, email, password
                )

                if success:
                    st.success(message)
                else:
                    st.error(message)

    if st.button("Back to Home"):
        st.session_state.page = "Home"
        st.rerun()


# ==================================================
# VOLUNTEER INTERFACE
# ==================================================

def volunteer_dashboard(user):

    data = get_data()

    users = data["users"]
    shifts = data["shifts"]
    signups = data["signups"]
    hours = data["hours"]

    user_id = user["user_id"]

    my_signups = signups[
        (signups["user_id"] == user_id) &
        (signups["status"] == "Signed Up")
    ]

    my_hours = hours[
        (hours["user_id"] == user_id) &
        (hours["status"] == "Approved")
    ]

    approved_hours = pd.to_numeric(
        my_hours["hours"], errors="coerce"
    ).fillna(0).sum()

    st.sidebar.title("🤝 VolunteerHub")
    st.sidebar.caption(f"Welcome, {user['name']}")

    page = st.sidebar.radio(
        "Navigation",
        [
            "Dashboard",
            "Find Shifts",
            "My Signups",
            "My Hours",
            "My Profile"
        ]
    )

    if st.sidebar.button("Log Out", use_container_width=True):
        logout()

    # -------------------------
    # VOLUNTEER HOME
    # -------------------------

    if page == "Dashboard":

        st.title(f"Welcome, {user['name']}!")

        st.write("Here's an overview of your volunteering.")

        c1, c2, c3 = st.columns(3)

        c1.metric("My Signups", len(my_signups))
        c2.metric("Approved Hours", f"{approved_hours:g}")
        c3.metric("Available Shifts", len(
            shifts[
                (shifts["status"] == "Open") &
                (pd.to_datetime(
                    shifts["date"], errors="coerce"
                ).dt.date >= date.today())
            ]
        ))

        st.subheader("My Upcoming Shifts")

        if my_signups.empty:
            st.info("You haven't signed up for any shifts yet.")
        else:
            upcoming = my_signups.merge(
                shifts, on="shift_id", how="left"
            )

            upcoming = upcoming[
                (upcoming["status_y"] == "Open") &
                (pd.to_datetime(
                    upcoming["date"], errors="coerce"
                ).dt.date >= date.today())
            ] if "status_y" in upcoming.columns else upcoming

            for _, row in upcoming.iterrows():
                with st.container(border=True):
                    display_shift(row)

    # -------------------------
    # FIND SHIFTS
    # -------------------------

    elif page == "Find Shifts":

        st.title("Find Volunteer Opportunities")

        available = shifts[
            (shifts["status"] == "Open") &
            (pd.to_datetime(
                shifts["date"], errors="coerce"
            ).dt.date >= date.today())
        ]

        if available.empty:
            st.info("There are currently no available shifts.")
        else:

            for _, row in available.iterrows():

                active = signups[
                    (signups["shift_id"] == row["shift_id"]) &
                    (signups["status"] == "Signed Up")
                ]

                remaining = max(
                    0, int(row["capacity"]) - len(active)
                )

                with st.container(border=True):

                    display_shift(row)

                    st.write(f"**Spots remaining:** {remaining}")

                    already_signed = not signups[
                        (signups["user_id"] == user_id) &
                        (signups["shift_id"] == row["shift_id"]) &
                        (signups["status"] == "Signed Up")
                    ].empty

                    if already_signed:
                        st.success("You are signed up!")
                    elif remaining == 0:
                        st.warning("This shift is full.")
                    elif st.button(
                        "Sign Up",
                        key=f"signup_{row['shift_id']}"
                    ):
                        success, message = signup_for_shift(
                            user_id, row["shift_id"]
                        )

                        if success:
                            st.success(message)
                        else:
                            st.error(message)

                        st.rerun()

    # -------------------------
    # MY SIGNUPS
    # -------------------------

    elif page == "My Signups":

        st.title("My Volunteer Signups")

        if my_signups.empty:
            st.info("You have no active signups.")
        else:

            records = my_signups.merge(
                shifts, on="shift_id", how="left",
                suffixes=("_signup", "_shift")
            )

            for _, row in records.iterrows():

                with st.container(border=True):

                    display_shift(row)

                    if row["date"] >= str(date.today()):
                        if st.button(
                            "Cancel Signup",
                            key=f"cancel_{row['shift_id']}"
                        ):
                            success, message = cancel_signup(
                                user_id, row["shift_id"]
                            )

                            if success:
                                st.success(message)
                            else:
                                st.error(message)

                            st.rerun()

    # -------------------------
    # MY HOURS
    # -------------------------

    elif page == "My Hours":

        st.title("My Volunteer Hours")

        st.metric(
            "Total Approved Hours",
            f"{approved_hours:g}"
        )

        my_records = hours[hours["user_id"] == user_id]

        st.subheader("Hours History")

        if my_records.empty:
            st.info("No hours submitted yet.")
        else:
            history = my_records.merge(
                shifts[["shift_id", "title", "date"]],
                on="shift_id",
                how="left"
            )

            st.dataframe(
                history[[
                    "title", "date", "hours", "status"
                ]],
                use_container_width=True,
                hide_index=True
            )

        st.divider()
        st.subheader("Submit Volunteer Hours")

        eligible = my_signups.merge(
            shifts, on="shift_id", how="left"
        )

        eligible = eligible[
            pd.to_datetime(
                eligible["date"], errors="coerce"
            ).dt.date <= date.today()
        ]

        if eligible.empty:
            st.info("No completed shifts available for hour submission.")
        else:

            options = {
                shift_label(row): row["shift_id"]
                for _, row in eligible.iterrows()
            }

            with st.form("hours_form"):

                selected = st.selectbox(
                    "Select Shift",
                    list(options.keys())
                )

                submitted_hours = st.number_input(
                    "Hours Volunteered",
                    min_value=0.5,
                    max_value=24.0,
                    step=0.5
                )

                submit = st.form_submit_button(
                    "Submit Hours"
                )

                if submit:

                    success, message = submit_hours(
                        user_id,
                        options[selected],
                        submitted_hours
                    )

                    if success:
                        st.success(message)
                    else:
                        st.error(message)

    # -------------------------
    # PROFILE
    # -------------------------

    elif page == "My Profile":

        st.title("My Profile")

        with st.form("profile_form"):

            name = st.text_input(
                "Full Name",
                value=user["name"]
            )

            st.text_input(
                "Email Address",
                value=user["email"],
                disabled=True
            )

            save = st.form_submit_button("Save Changes")

            if save:

                if not name.strip():
                    st.error("Name cannot be empty.")
                else:
                    success, message = update_profile(
                        user_id, name
                    )

                    if success:
                        st.session_state.user["name"] = name.strip()
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)


# ==================================================
# ADMINISTRATOR INTERFACE
# ==================================================

def administrator_dashboard(user):

    data = get_data()

    users = data["users"]
    shifts = data["shifts"]
    signups = data["signups"]
    hours = data["hours"]

    page = st.sidebar.radio(
        "Administration",
        [
            "Dashboard",
            "Create Shift",
            "Manage Shifts",
            "Manage Signups",
            "Approve Hours",
            "Volunteers",
            "Reports"
        ]
    )

    st.sidebar.title("🛡️ VolunteerHub Admin")
    st.sidebar.caption(user["email"])

    if st.sidebar.button("Log Out", use_container_width=True):
        logout()

    # -------------------------
    # ADMIN DASHBOARD
    # -------------------------

    if page == "Dashboard":

        st.title("Administrator Dashboard")
        st.write("Organization overview")

        active_users = users[
            users["role"] == "volunteer"
        ]

        open_shifts = shifts[
            shifts["status"] == "Open"
        ]

        active_signups = signups[
            signups["status"] == "Signed Up"
        ]

        pending = hours[
            hours["status"] == "Pending"
        ]

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Volunteers", len(active_users))
        c2.metric("Open Shifts", len(open_shifts))
        c3.metric("Active Signups", len(active_signups))
        c4.metric("Pending Hours", len(pending))

        st.divider()

        st.subheader("Recent Signups")

        if active_signups.empty:
            st.info("No signups yet.")
        else:

            recent = active_signups.merge(
                users[["user_id", "name"]],
                on="user_id",
                how="left"
            ).merge(
                shifts[["shift_id", "title", "date"]],
                on="shift_id",
                how="left"
            )

            st.dataframe(
                recent[["name", "title", "date", "signup_date"]],
                use_container_width=True,
                hide_index=True
            )

        st.subheader("Hours Awaiting Approval")
        st.metric("Pending submissions", len(pending))

    # -------------------------
    # CREATE SHIFT
    # -------------------------

    elif page == "Create Shift":

        st.title("Create a Volunteer Shift")

        with st.form("create_shift_form"):

            title = st.text_input("Shift Title")

            description = st.text_area(
                "Description",
                placeholder="Describe the volunteer responsibilities..."
            )

            col1, col2 = st.columns(2)

            with col1:
                shift_date = st.date_input(
                    "Date",
                    value=date.today()
                )

                start_time = st.time_input(
                    "Start Time",
                    value=time(9, 0)
                )

            with col2:
                location = st.text_input("Location")

                end_time = st.time_input(
                    "End Time",
                    value=time(12, 0)
                )

            capacity = st.number_input(
                "Volunteer Capacity",
                min_value=1,
                max_value=1000,
                value=10
            )

            create = st.form_submit_button(
                "Publish Shift",
                use_container_width=True
            )

            if create:

                success, message = create_shift(
                    title,
                    description,
                    shift_date,
                    start_time,
                    end_time,
                    location,
                    capacity,
                    user["email"]
                )

                if success:
                    st.success(message)
                else:
                    st.error(message)

    # -------------------------
    # MANAGE SHIFTS
    # -------------------------

    elif page == "Manage Shifts":

        st.title("Manage Volunteer Shifts")

        if shifts.empty:
            st.info("No shifts have been created.")
        else:

            options = {
                shift_label(row): row["shift_id"]
                for _, row in shifts.iterrows()
            }

            selected = st.selectbox(
                "Select a Shift",
                list(options.keys())
            )

            shift_id = options[selected]
            row = shifts[
                shifts["shift_id"] == shift_id
            ].iloc[0]

            st.divider()

            if row["status"] == "Cancelled":
                st.warning("This shift has been cancelled.")

            with st.form("edit_shift_form"):

                title = st.text_input(
                    "Title", value=row["title"]
                )

                description = st.text_area(
                    "Description", value=row["description"]
                )

                col1, col2 = st.columns(2)

                try:
                    existing_date = date.fromisoformat(row["date"])
                except ValueError:
                    existing_date = date.today()

                try:
                    existing_start = time.fromisoformat(row["start_time"])
                    existing_end = time.fromisoformat(row["end_time"])
                except ValueError:
                    existing_start = time(9, 0)
                    existing_end = time(12, 0)

                with col1:
                    new_date = st.date_input(
                        "Date", value=existing_date
                    )
                    new_start = st.time_input(
                        "Start Time", value=existing_start
                    )

                with col2:
                    new_location = st.text_input(
                        "Location", value=row["location"]
                    )
                    new_end = st.time_input(
                        "End Time", value=existing_end
                    )

                new_capacity = st.number_input(
                    "Capacity",
                    min_value=1,
                    max_value=1000,
                    value=max(1, int(row["capacity"]))
                )

                save = st.form_submit_button("Save Changes")

                if save:

                    success, message = update_shift(
                        shift_id,
                        title,
                        description,
                        new_date,
                        new_start,
                        new_end,
                        new_location,
                        new_capacity
                    )

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

            if row["status"] == "Open":

                if st.button(
                    "Cancel This Shift",
                    type="secondary"
                ):
                    success, message = cancel_shift(shift_id)
                    st.success(message)
                    st.rerun()

    # -------------------------
    # MANAGE SIGNUPS
    # -------------------------

    elif page == "Manage Signups":

        st.title("Manage Volunteer Signups")

        if shifts.empty:
            st.info("No shifts available.")
        else:

            options = {
                shift_label(row): row["shift_id"]
                for _, row in shifts.iterrows()
            }

            selected = st.selectbox(
                "Choose a Shift",
                list(options.keys())
            )

            shift_id = options[selected]

            roster = signups[
                (signups["shift_id"] == shift_id) &
                (signups["status"] == "Signed Up")
            ]

            roster = roster.merge(
                users[["user_id", "name", "email"]],
                on="user_id",
                how="left"
            )

            st.subheader(f"Volunteers Registered: {len(roster)}")

            if roster.empty:
                st.info("No volunteers have signed up.")
            else:

                st.dataframe(
                    roster[["name", "email", "signup_date"]],
                    use_container_width=True,
                    hide_index=True
                )

    # -------------------------
    # APPROVE HOURS
    # -------------------------

    elif page == "Approve Hours":

        st.title("Review Volunteer Hours")

        pending = hours[
            hours["status"] == "Pending"
        ]

        if pending.empty:
            st.success("No hours are waiting for approval.")
        else:

            review_data = pending.merge(
                users[["user_id", "name", "email"]],
                on="user_id",
                how="left"
            ).merge(
                shifts[["shift_id", "title", "date"]],
                on="shift_id",
                how="left"
            )

            for _, row in review_data.iterrows():

                with st.container(border=True):

                    st.subheader(row["name"])
                    st.write(f"Shift: {row['title']}")
                    st.write(f"Date: {row['date']}")
                    st.write(f"Hours: {row['hours']}")

                    col1, col2 = st.columns(2)

                    with col1:
                        if st.button(
                            "Approve",
                            key=f"approve_{row['hour_id']}"
                        ):
                            success, message = review_hours(
                                row["hour_id"],
                                "Approved",
                                user["email"]
                            )

                            if success:
                                st.success(message)
                            else:
                                st.error(message)

                            st.rerun()

                    with col2:
                        if st.button(
                            "Reject",
                            key=f"reject_{row['hour_id']}"
                        ):
                            success, message = review_hours(
                                row["hour_id"],
                                "Rejected",
                                user["email"]
                            )

                            if success:
                                st.success(message)
                            else:
                                st.error(message)

                            st.rerun()

    # -------------------------
    # VOLUNTEERS
    # -------------------------

    elif page == "Volunteers":

        st.title("Volunteer Directory")

        volunteers = users[
            users["role"] == "volunteer"
        ]

        if volunteers.empty:
            st.info("No registered volunteers.")
        else:

            approved = hours[
                hours["status"] == "Approved"
            ].copy()

            approved["hours"] = pd.to_numeric(
                approved["hours"], errors="coerce"
            ).fillna(0)

            totals = approved.groupby(
                "user_id"
            )["hours"].sum()

            directory = volunteers.copy()

            directory["approved_hours"] = (
                directory["user_id"].map(totals).fillna(0)
            )

            st.dataframe(
                directory[[
                    "name", "email", "created_at", "approved_hours"
                ]],
                use_container_width=True,
                hide_index=True
            )

    # -------------------------
    # REPORTS
    # -------------------------

    elif page == "Reports":

        st.title("Organization Reports")

        approved = hours[
            hours["status"] == "Approved"
        ].copy()

        approved["hours"] = pd.to_numeric(
            approved["hours"], errors="coerce"
        ).fillna(0)

        total_hours = approved["hours"].sum()

        st.metric("Total Approved Volunteer Hours", f"{total_hours:g}")

        st.subheader("Export Data")

        report_type = st.selectbox(
            "Choose Report",
            ["Volunteers", "Shifts", "Signups", "Approved Hours"]
        )

        report_map = {
            "Volunteers": ("users", users),
            "Shifts": ("shifts", shifts),
            "Signups": ("signups", signups),
            "Approved Hours": ("hours", approved)
        }

        sheet_name, report = report_map[report_type]

        if report_type == "Volunteers":
            report = report[report["role"] == "volunteer"]

        if report_type == "Approved Hours":
            report = report[report["status"] == "Approved"]

        output = BytesIO()

        with pd.ExcelWriter(
            output,
            engine="openpyxl"
        ) as writer:

            report.to_excel(
                writer,
                index=False,
                sheet_name=sheet_name.title()
            )

        st.download_button(
            "Download Excel Report",
            data=output.getvalue(),
            file_name=f"{sheet_name}_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# ==================================================
# MAIN APPLICATION ROUTER
# ==================================================

if st.session_state.user is None:

    page = st.session_state.page

    if page == "Home":
        home_page()

    elif page == "Volunteer Login":
        login_page("Volunteer Login")

    elif page == "Administrator Login":
        login_page("Administrator Login")

    elif page == "Register":
        register_page()

else:

    user = st.session_state.user

    if user["role"] == "volunteer":
        volunteer_dashboard(user)

    elif user["role"] == "admin":
        administrator_dashboard(user)

    else:
        logout()
