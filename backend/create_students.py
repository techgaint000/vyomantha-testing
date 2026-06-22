import frappe
from frappe.utils.password import update_password

# Print existing courses to debug what is in the database
try:
    courses = frappe.get_all("LMS Course", fields=["name", "title", "published"])
    print("DEBUG: EXISTING COURSES IN DB:", courses)
except Exception as e:
    print("DEBUG: Failed to fetch courses:", e)


def grant_permission(doctype, role, read=1, write=0, create=0, delete=0):
    try:
        has_perm = frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role})
        if has_perm:
            doc = frappe.get_doc("Custom DocPerm", has_perm)
            doc.read = read
            doc.write = write
            doc.create = create
            doc.delete = delete
            doc.save(ignore_permissions=True)
            print(f"Updated permissions for {doctype} -> {role}")
        else:
            doc = frappe.get_doc({
                "doctype": "Custom DocPerm",
                "parent": doctype,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role,
                "permlevel": 0,
                "read": read,
                "write": write,
                "create": create,
                "delete": delete
            })
            doc.insert(ignore_permissions=True)
            print(f"Created permissions for {doctype} -> {role}")
        frappe.clear_cache(doctype=doctype)
    except Exception as e:
        print(f"Failed to grant permissions for {doctype} to {role}: {e}")

# Grant permissions for LMS DocTypes
permissions_to_grant = [
    # LMS Course
    ("LMS Course", "LMS Student", 1, 0, 0, 0),
    ("LMS Course", "Guest", 1, 0, 0, 0),
    
    # Course Chapter
    ("Course Chapter", "LMS Student", 1, 0, 0, 0),
    ("Course Chapter", "Guest", 1, 0, 0, 0),
    
    # Course Lesson
    ("Course Lesson", "LMS Student", 1, 0, 0, 0),
    ("Course Lesson", "Guest", 1, 0, 0, 0),
    
    # LMS Course Category
    ("LMS Course Category", "LMS Student", 1, 0, 0, 0),
    ("LMS Course Category", "Guest", 1, 0, 0, 0),
    
    # LMS Enrollment
    ("LMS Enrollment", "LMS Student", 1, 1, 1, 0),
    ("LMS Enrollment", "Guest", 1, 1, 1, 0),
]

for dt, role, r, w, c, d in permissions_to_grant:
    grant_permission(dt, role, r, w, c, d)



students = [
    {"email": "student@lms.com", "name": "Student"},
    {"email": "student1@lms.com", "name": "Aarav Mehta"},
    {"email": "student2@lms.com", "name": "Sneha Patel"},
    {"email": "student3@lms.com", "name": "Rohan Sharma"},
    {"email": "student4@lms.com", "name": "Priya Nair"},
    {"email": "student5@lms.com", "name": "Aditya Rao"}
]

for s in students:
    email = s["email"]
    name = s["name"]
    
    if not frappe.db.exists("User", email):
        print(f"Creating user {email} ({name})...")
        first_name = name.split(" ")[0]
        last_name = name.split(" ")[1] if len(name.split(" ")) > 1 else ""
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "enabled": 1,
            "send_welcome_email": 0
        })
        user.insert(ignore_permissions=True)
        
        # Add LMS student role if it exists
        if frappe.db.exists("Role", "LMS Student"):
            user.add_roles("LMS Student")
    else:
        print(f"User {email} already exists.")

    # Always set/update the password to ensure it matches 'student123'
    print(f"Setting password for {email} to 'student123'...")
    update_password(user=email, pwd="student123", logout_all_sessions=False)

# Seed Google Social Login Key
try:
    import os
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    
    if google_client_id and google_client_secret:
        print("Seeding Google Social Login Key...")
        if not frappe.db.exists("Social Login Key", "google"):
            doc = frappe.get_doc({
                "doctype": "Social Login Key",
                "name": "google",
                "enable_social_login": 1,
                "social_login_provider": "Google",
                "client_id": google_client_id,
                "client_secret": google_client_secret,
                "provider_name": "Google",
                "base_url": "https://accounts.google.com",
                "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
                "access_token_url": "https://oauth2.googleapis.com/token",
                "redirect_url": "https://vyomanta.onrender.com/api/method/frappe.integrations.oauth2_logins.login_via_google",
                "api_endpoint": "https://www.googleapis.com/oauth2/v2/userinfo",
                "user_id_property": "email",
                "custom_base_url": 1,
                "auth_url_data": '{"scope": "openid https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email", "response_type": "code"}'
            })
            doc.insert(ignore_permissions=True)
            print("Google Social Login Key inserted successfully via Frappe API.")
        else:
            doc = frappe.get_doc("Social Login Key", "google")
            doc.client_id = google_client_id
            doc.client_secret = google_client_secret
            doc.custom_base_url = 1
            doc.base_url = "https://accounts.google.com"
            doc.authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
            doc.access_token_url = "https://oauth2.googleapis.com/token"
            doc.redirect_url = "https://vyomanta.onrender.com/api/method/frappe.integrations.oauth2_logins.login_via_google"
            doc.api_endpoint = "https://www.googleapis.com/oauth2/v2/userinfo"
            doc.save(ignore_permissions=True)
            print("Google Social Login Key updated successfully via Frappe API.")
    else:
        print("Skipping Google Social Login Key seeding: GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET environment variables not set.")
except Exception as e:
    print(f"Failed to seed Google Social Login Key: {e}")

# Diagnostics check at startup
try:
    print("DIAGNOSTICS: Calling get_google_auth_url...")
    import lms.lms.api
    print("DIAGNOSTICS api.__file__:", lms.lms.api.__file__)
    print("DIAGNOSTICS api attributes:", [attr for attr in dir(lms.lms.api) if 'google' in attr or 'traceback' in attr])
    
    try:
        with open(lms.lms.api.__file__, 'r') as f:
            lines = f.readlines()
        print("DIAGNOSTICS api.py last 30 lines:")
        for line in lines[-30:]:
            print(line.rstrip())
    except Exception as file_err:
        print("Failed to read api.py:", file_err)

    from lms.lms.api import get_google_auth_url
    res = get_google_auth_url("http://localhost:3000/auth/callback")
    print("DIAGNOSTICS SUCCESS:", res)
except Exception as e:
    import traceback
    tb_str = traceback.format_exc()
    print("DIAGNOSTICS FAILED:", e)
    print(tb_str)
    try:
        frappe.log_error(title="Google Auth Diagnostics", message=tb_str)
        frappe.db.commit()
        print("Logged diagnostic failure to database successfully.")
    except Exception as db_err:
        print("Failed to log error to database:", db_err)

frappe.db.commit()
print("Students bootstrap completed successfully!")
