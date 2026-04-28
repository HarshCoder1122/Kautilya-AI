"""
Kautilya AI — Limits Manager
Handles usage limits, credits, bans, and Pro status.
Rewritten to use Firestore exclusively (no local JSON files) with an in-memory cache for high-frequency reads.
"""
import time
from datetime import datetime
from collections import OrderedDict

class SimpleCache:
    def __init__(self, ttl=60, max_size=1000):
        self.cache = OrderedDict()
        self.ttl = ttl
        self.max_size = max_size

    def get(self, key):
        if key in self.cache:
            val, expiry = self.cache[key]
            if time.time() < expiry:
                self.cache.move_to_end(key)
                return val
            else:
                del self.cache[key]
        return None

    def set(self, key, value):
        if key in self.cache:
            del self.cache[key]
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = (value, time.time() + self.ttl)
        
    def invalidate(self, key):
        if key in self.cache:
            del self.cache[key]


class LimitManager:
    def __init__(self, data_dir=None):
        # data_dir is kept for backward compatibility in imports, but ignored.
        self.db = None
        self._pro_cache = SimpleCache(ttl=300)      # Cache pro status for 5 mins
        self._ban_cache = SimpleCache(ttl=300)      # Cache ban status for 5 mins
        self._credits_cache = SimpleCache(ttl=60)   # Cache credits for 1 min
        
        # We'll use a small fast in-memory map for the daily usage counters 
        # to prevent hammering Firestore on every single chat message.
        # This acts as a write-behind / read-through cache.
        self.usage_data = {}

    def set_db(self, db):
        """Set the Firestore DB instance for cloud persistence"""
        self.db = db

    # ================= CREDITS (Pay As You Go) =================
    def get_credits(self, user_id):
        if not user_id or not self.db: return 0.0
        
        cached = self._credits_cache.get(user_id)
        if cached is not None:
            return cached
            
        try:
            doc = self.db.collection('user_credits').document(user_id).get()
            if doc.exists:
                balance = doc.to_dict().get('balance', 0.0)
                self._credits_cache.set(user_id, balance)
                return balance
        except Exception as e:
            print(f"[LimitManager] Firestore get credits failed: {e}")
        return 0.0

    def add_credits(self, user_id, amount):
        if not user_id or amount <= 0 or not self.db: return False
        
        current_balance = self.get_credits(user_id)
        new_balance = current_balance + amount
        
        try:
            self.db.collection('user_credits').document(user_id).set({
                "uid": user_id,
                "balance": new_balance,
                "last_updated": datetime.now().isoformat()
            }, merge=True)
            self._credits_cache.set(user_id, new_balance)
            print(f"[LimitManager] Added {amount} credits to User {user_id}. New Balance: {new_balance}")
            return True
        except Exception as e:
            print(f"[LimitManager] Firestore add credits failed: {e}")
            return False

    def deduct_credits(self, user_id, amount):
        if not user_id or amount <= 0 or not self.db: return True
        
        current_balance = self.get_credits(user_id)
        if current_balance < amount:
            return False # Insufficient funds
            
        new_balance = current_balance - amount
        
        try:
            self.db.collection('user_credits').document(user_id).set({
                "uid": user_id,
                "balance": new_balance,
                "last_updated": datetime.now().isoformat()
            }, merge=True)
            self._credits_cache.set(user_id, new_balance)
            return True
        except Exception as e:
            print(f"[LimitManager] Firestore deduct credits failed: {e}")
            return False

    # ================= PRO USERS =================
    def is_pro_user(self, user_id):
        if not user_id or not self.db: return False
        
        cached = self._pro_cache.get(user_id)
        if cached is not None:
            return cached
            
        try:
            doc = self.db.collection('pro_users').document(user_id).get()
            is_pro = doc.exists
            self._pro_cache.set(user_id, is_pro)
            return is_pro
        except Exception as e:
            print(f"[LimitManager] Firestore check pro failed: {e}")
            return False

    def add_pro_user(self, user_id):
        if not user_id or not self.db: return
        try:
            self.db.collection('pro_users').document(user_id).set({
                "uid": user_id,
                "granted_at": datetime.now().isoformat()
            })
            self._pro_cache.set(user_id, True)
            print(f"[LimitManager] Added User {user_id} to PRO tier.")
        except Exception as e:
            print(f"[LimitManager] Firestore add pro failed: {e}")

    def remove_pro_user(self, user_id):
        if not user_id or not self.db: return
        try:
            self.db.collection('pro_users').document(user_id).delete()
            self._pro_cache.set(user_id, False)
            print(f"[LimitManager] Removed User {user_id} from PRO tier.")
        except Exception as e:
            print(f"[LimitManager] Firestore remove pro failed: {e}")

    # ================= DAILY USAGE HELPER =================
    def _get_daily_usage(self, user_id):
        """Fetch daily usage document from Firestore, caching it locally in memory."""
        if not user_id: return {}
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        if user_id in self.usage_data:
            local_record = self.usage_data[user_id]
            if local_record.get('date') == today:
                return local_record
        
        # Cache miss or new day -> Fetch from Firestore
        record = {'date': today, 'chat_count': 0, 'image_count': 0}
        if self.db:
            try:
                doc = self.db.collection('api_usage').document(user_id).collection('daily').document(today).get()
                if doc.exists:
                    data = doc.to_dict()
                    record['chat_count'] = data.get('chat_count', 0)
                    record['image_count'] = data.get('image_count', 0)
            except Exception as e:
                pass # Fail open for read if Firestore is down momentarily, rely on local
                
        self.usage_data[user_id] = record
        return record
        
    def _save_daily_usage(self, user_id, record):
        """Save the updated daily usage to Firestore."""
        self.usage_data[user_id] = record
        if self.db:
            try:
                today = record['date']
                self.db.collection('api_usage').document(user_id).collection('daily').document(today).set({
                    'chat_count': record.get('chat_count', 0),
                    'image_count': record.get('image_count', 0),
                    'updated_at': datetime.now().isoformat()
                }, merge=True)
            except Exception as e:
                print(f"[LimitManager] Firestore save daily usage failed: {e}")

    # ================= IMAGE LIMITS =================
    def check_image_limit(self, user_id, limit_per_day=3):
        if not user_id: return True # Dev mode
        
        record = self._get_daily_usage(user_id)
        if record.get('image_count', 0) >= limit_per_day:
            return False
        return True

    def increment_image_count(self, user_id):
        if not user_id: return
        record = self._get_daily_usage(user_id)
        record['image_count'] += 1
        self._save_daily_usage(user_id, record)

    # ================= CHAT LIMITS =================
    def check_chat_limit(self, user_id, is_pro=False, limit_per_day=30):
        if not user_id or is_pro: return True 
        
        record = self._get_daily_usage(user_id)
        if record.get('chat_count', 0) >= limit_per_day:
            return False
        return True

    def increment_chat_count(self, user_id):
        if not user_id: return
        record = self._get_daily_usage(user_id)
        record['chat_count'] += 1
        self._save_daily_usage(user_id, record)

    # ================= CONTEXT LIMITS =================
    def check_context_limit(self, messages, model_mode, limit_tokens=50000, is_pro=False):
        total_chars = sum([len(str(m.get("content", ""))) for m in messages])
        est_tokens = total_chars / 4
        
        if is_pro:
            return True, int(est_tokens)
            
        if est_tokens > limit_tokens:
            return False, int(est_tokens)
            
        return True, int(est_tokens)

    # ================= SECURITY BANS =================
    def is_banned(self, user_id, ip_address):
        """Check if User ID or IP is banned."""
        if not self.db: return False
        
        keys_to_check = []
        if user_id: keys_to_check.append(f"uid_{user_id}")
        if ip_address: keys_to_check.append(f"ip_{ip_address.replace('.', '_')}")
            
        for key in keys_to_check:
            cached = self._ban_cache.get(key)
            if cached is not None:
                if cached: return True
                continue
                
            try:
                doc_id = user_id if key.startswith('uid_') else ip_address
                doc = self.db.collection('banned_users').document(doc_id).get()
                is_banned = doc.exists
                self._ban_cache.set(key, is_banned)
                if is_banned: return True
            except Exception as e:
                pass
                
        return False

    def ban_user(self, user_id, ip_address, reason="Security Violation"):
        if not self.db: return
        timestamp = datetime.now().isoformat()
        
        try:
            if user_id:
                self.db.collection('banned_users').document(user_id).set({"reason": reason, "timestamp": timestamp})
                self._ban_cache.set(f"uid_{user_id}", True)
            if ip_address:
                self.db.collection('banned_users').document(ip_address).set({"reason": reason, "timestamp": timestamp})
                self._ban_cache.set(f"ip_{ip_address.replace('.', '_')}", True)
            print(f"[LimitManager] BANNED User: {user_id} IP: {ip_address} Reason: {reason}")
        except Exception as e:
            print(f"[LimitManager] Firestore ban user failed: {e}")

    # ================= TRANSACTIONS =================
    def add_transaction(self, user_id, amount, plan_type, order_id, payment_id):
        if not user_id or not self.db: return
        
        tx = {
            "timestamp": time.time(),
            "amount": amount,
            "plan_type": plan_type,
            "order_id": order_id,
            "payment_id": payment_id,
            "status": "success",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            self.db.collection('users').document(user_id).collection('transactions').add(tx)
        except Exception as e:
            print(f"[LimitManager] Firestore add transaction failed: {e}")
        
    def get_transactions(self, user_id):
        if not user_id or not self.db: return []
        
        try:
            docs = self.db.collection('users').document(user_id).collection('transactions')\
                     .order_by('timestamp', direction=self.db.Query.DESCENDING).limit(50).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"[LimitManager] Firestore get transactions failed: {e}")
            return []
