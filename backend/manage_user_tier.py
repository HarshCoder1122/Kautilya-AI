#!/usr/bin/env python3
import os
import sys
import argparse
from datetime import datetime

# Add this directory to path to resolve imports
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_path)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(backend_path, '.env'))
except ImportError:
    pass

try:
    from extensions import db
    from limits_manager import LimitManager
except ImportError as e:
    print(f"\033[91mError: Could not import backend modules. Details: {e}\033[0m")
    sys.exit(1)

if not db:
    print("\033[91mError: Firestore client could not be initialized. Please check your credentials (e.g. FIREBASE_SERVICE_ACCOUNT_JSON).\033[0m")
    sys.exit(1)

limit_manager = LimitManager()
limit_manager.set_db(db)

def get_user_info(uid):
    """Fetch user profile details if they exist in the users collection."""
    try:
        user_doc = db.collection('users').document(uid).get()
        if user_doc.exists:
            return user_doc.to_dict()
    except Exception as e:
        print(f"Error fetching user info for {uid}: {e}")
    return None

def search_user_by_email(email):
    """Find user UIDs by email address."""
    email = email.strip().lower()
    try:
        users_ref = db.collection('users')
        results = []
        for doc in users_ref.stream():
            data = doc.to_dict()
            if data.get('email', '').strip().lower() == email:
                results.append((doc.id, data))
        return results
    except Exception as e:
        print(f"Error searching user: {e}")
        return []

def list_pro_users():
    """List all users currently marked as PRO."""
    print("\n\033[94mFetching active PRO users from Firestore...\033[0m")
    try:
        pro_docs = db.collection('pro_users').stream()
        pro_list = list(pro_docs)
        
        if not pro_list:
            print("No PRO users found.")
            return []
            
        print(f"\nFound {len(pro_list)} PRO user(s):")
        print("-" * 80)
        print(f"{'UID':<30} | {'Email':<25} | {'Granted At':<20}")
        print("-" * 80)
        
        for doc in pro_list:
            uid = doc.id
            data = doc.to_dict()
            granted_at = data.get('granted_at', 'Unknown')
            
            uinfo = get_user_info(uid)
            email = uinfo.get('email', 'N/A') if uinfo else 'N/A'
            print(f"{uid:<30} | {email:<25} | {granted_at:<20}")
        print("-" * 80)
        return pro_list
    except Exception as e:
        print(f"Failed to list PRO users: {e}")
        return []

def promote_user(uid):
    """Promote a user to PRO tier."""
    uinfo = get_user_info(uid)
    email = uinfo.get('email', 'N/A') if uinfo else 'N/A'
    
    print(f"\nPromoting User: {uid} ({email}) to PRO...")
    try:
        limit_manager.add_pro_user(uid)
        print(f"\033[92mSuccess: User {uid} promoted to PRO.\033[0m")
        limit_manager._pro_cache.invalidate(uid)
    except Exception as e:
        print(f"\033[91mFailed to promote user: {e}\033[0m")

def demote_user(uid):
    """Remove a user from PRO tier (make them Free)."""
    uinfo = get_user_info(uid)
    email = uinfo.get('email', 'N/A') if uinfo else 'N/A'
    
    print(f"\nDemoting User: {uid} ({email}) from PRO...")
    try:
        doc = db.collection('pro_users').document(uid).get()
        if not doc.exists:
            print(f"\033[93mWarning: User {uid} is not currently in the PRO users collection.\033[0m")
            
        limit_manager.remove_pro_user(uid)
        print(f"\033[92mSuccess: User {uid} removed from PRO.\033[0m")
        limit_manager._pro_cache.invalidate(uid)
    except Exception as e:
        print(f"\033[91mFailed to demote user: {e}\033[0m")

def interactive_mode():
    print("=" * 60)
    print("           KAUTILYA AI - SUBSCRIPTION MANAGER")
    print("=" * 60)
    
    while True:
        print("\nOptions:")
        print("1. List all PRO users")
        print("2. Search user by email")
        print("3. Promote a user to PRO (Add)")
        print("4. Demote a user from PRO (Remove)")
        print("5. Exit")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == '1':
            list_pro_users()
        elif choice == '2':
            email = input("Enter email to search: ").strip()
            if email:
                results = search_user_by_email(email)
                if results:
                    print(f"\nFound {len(results)} matching user(s):")
                    for uid, data in results:
                        print(f"UID: {uid} | Name: {data.get('name', 'N/A')} | Email: {data.get('email', 'N/A')}")
                else:
                    print("No user found with that email address.")
        elif choice == '3':
            uid = input("Enter User ID (UID) to promote: ").strip()
            if uid:
                promote_user(uid)
        elif choice == '4':
            uid = input("Enter User ID (UID) to demote from PRO: ").strip()
            if uid:
                demote_user(uid)
        elif choice == '5':
            print("Exiting subscription manager.")
            break
        else:
            print("Invalid choice, try again.")

def main():
    parser = argparse.ArgumentParser(description="Kautilya AI Admin subscription manager CLI")
    parser.add_argument('--uid', type=str, help='The Firebase UID of the target user')
    parser.add_argument('--action', type=str, choices=['list', 'promote', 'demote', 'search'], help='Action to execute')
    parser.add_argument('--email', type=str, help='User email (used for searching)')
    
    args = parser.parse_args()
    
    if not args.action and not args.uid and not args.email:
        interactive_mode()
        return

    if args.action == 'list':
        list_pro_users()
    elif args.action == 'search':
        if not args.email:
            print("Error: --email is required when using search action.")
            sys.exit(1)
        results = search_user_by_email(args.email)
        if results:
            for uid, data in results:
                print(f"UID: {uid} | Name: {data.get('name', 'N/A')} | Email: {data.get('email', 'N/A')}")
        else:
            print("No matching user found.")
    elif args.action == 'promote':
        if not args.uid:
            print("Error: --uid is required for promote action.")
            sys.exit(1)
        promote_user(args.uid)
    elif args.action == 'demote':
        if not args.uid:
            print("Error: --uid is required for demote action.")
            sys.exit(1)
        demote_user(args.uid)

if __name__ == '__main__':
    main()
