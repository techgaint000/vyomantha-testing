import os
import sys

def main():
    api_path = '/home/frappe/frappe-bench/apps/lms/lms/lms/api.py'
    if not os.path.exists(api_path):
        print(f"❌ Error: {api_path} not found!")
        sys.exit(1)

    with open(api_path, 'r') as f:
        content = f.read()

    # If an old get_google_auth_url exists, remove it and everything after it
    if 'def get_google_auth_url' in content:
        print("Found existing get_google_auth_url. Removing old definition first...")
        # Split at the decorator or the function definition
        if '@frappe.whitelist(allow_guest=True)\ndef get_google_auth_url' in content:
            content = content.split('@frappe.whitelist(allow_guest=True)\ndef get_google_auth_url')[0]
        elif 'def get_google_auth_url' in content:
            # Fallback split
            content = content.split('def get_google_auth_url')[0]
            # Strip trailing decorator if present
            content = content.rstrip().rstrip('@frappe.whitelist(allow_guest=True)').rstrip()

    patch_code = """

@frappe.whitelist(allow_guest=True)
def get_google_auth_url(redirect_to=None):
    import frappe
    import traceback
    try:
        from frappe.utils.oauth import get_oauth2_authorize_url
        return get_oauth2_authorize_url("google", redirect_to)
    except Exception as e:
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
"""

    with open(api_path, 'w') as f:
        f.write(content.strip() + patch_code)
    print("✅ Patched apps/lms/lms/lms/api.py successfully!")

if __name__ == '__main__':
    main()
