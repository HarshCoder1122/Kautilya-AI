"""
Kautilya AI — Campaign Dialer Worker

Runs as a side-process started by `start.sh` (the line:
`if [ -f "campaign_worker.py" ]; then python campaign_worker.py & fi`).

Polls Firestore for campaigns marked `status == 'running'`, dials each phone
number in the list with a configurable concurrency cap, and updates progress
+ per-number status as calls launch. Pauses cleanly when the user flips a
campaign to `paused`.

Schema expected (already created by `routes/campaigns_routes.py`):
    users/<uid>/campaigns/<camp_id>:
        name:        str
        agent_id:    str
        numbers:     list[str]
        status:      "pending" | "running" | "paused" | "completed" | "failed"
        progress:    int      (count of numbers we've launched)
        total:       int
        created_at:  Timestamp

Fields the worker WRITES on each iteration:
    progress, status, dialed (map: phone -> {call_id, status, ts, error?}),
    last_run, finished_at
"""
import os
import sys
import json
import time
import signal
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import firebase_admin
from firebase_admin import credentials, firestore

from services.telephony_dialer import dial_outbound, load_provider_config

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
POLL_INTERVAL = float(os.environ.get('CAMPAIGN_POLL_INTERVAL', '5'))
PER_CAMPAIGN_CONCURRENCY = int(os.environ.get('CAMPAIGN_CONCURRENCY', '3'))
GLOBAL_MAX_IN_FLIGHT = int(os.environ.get('CAMPAIGN_GLOBAL_MAX', '20'))
DIAL_PACING_SEC = float(os.environ.get('CAMPAIGN_DIAL_PACING', '0.5'))
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', '').rstrip('/')

# --------------------------------------------------------------------------
# Firebase
# --------------------------------------------------------------------------
def _init_firebase():
    if firebase_admin._apps:
        return firestore.client()
    sa_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT') or os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
    if sa_json:
        try:
            info = json.loads(sa_json)
            cred = credentials.Certificate(info)
            firebase_admin.initialize_app(cred)
        except Exception:
            if os.path.exists(sa_json):
                cred = credentials.Certificate(sa_json)
                firebase_admin.initialize_app(cred)
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    return firestore.client()


db = _init_firebase()
print('[Campaign] Firebase ready')

# --------------------------------------------------------------------------
# Graceful shutdown
# --------------------------------------------------------------------------
_stop = threading.Event()


def _on_signal(signum, _frame):
    print(f'[Campaign] Signal {signum} received, shutting down…')
    _stop.set()


signal.signal(signal.SIGTERM, _on_signal)
signal.signal(signal.SIGINT, _on_signal)

# Per-process global semaphore to cap concurrent in-flight dials across ALL
# campaigns. Prevents one user's huge campaign from saturating Vobiz/Exotel.
_global_sem = threading.Semaphore(GLOBAL_MAX_IN_FLIGHT)

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _resolve_base_url():
    """Best-effort base URL for webhook callbacks. Prefers env override.
    Falls back to a couple of common platform-provided env vars."""
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    for k in ('RENDER_EXTERNAL_URL', 'KOYEB_PUBLIC_URL', 'PUBLIC_URL'):
        v = os.environ.get(k)
        if v:
            return v.rstrip('/')
    print('[Campaign] WARNING: no PUBLIC_BASE_URL set — webhook callbacks may fail')
    return ''


def _load_agent(agent_id):
    if not agent_id:
        return None
    try:
        doc = db.collection('agents').document(agent_id).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        print(f'[Campaign] agent {agent_id} load failed: {e}')
        return None


def _dial_one(camp_ref, uid, agent_id, agent, telephony_config, base_url, number):
    """Dial a single number under the global concurrency cap. Updates the
    campaign doc with per-number outcome."""
    with _global_sem:
        if _stop.is_set():
            return
        result = dial_outbound(uid, agent_id, agent, telephony_config, number, base_url, db=db)
        ts = firestore.SERVER_TIMESTAMP
        if result.get('ok'):
            entry = {
                'call_id': result.get('call_id'),
                'status': 'launched',
                'provider': result.get('provider'),
                'ts': ts,
            }
            print(f'[Campaign] ✅ dialed {number} via {result.get("provider")} (call={result.get("call_id")})')
        else:
            entry = {'status': 'failed', 'error': result.get('error', 'unknown'), 'ts': ts}
            print(f'[Campaign] ❌ {number} failed: {entry["error"]}')
        try:
            camp_ref.update({
                f'dialed.{_doc_key(number)}': entry,
                'progress': firestore.Increment(1),
                'last_run': ts,
            })
        except Exception as e:
            print(f'[Campaign] progress update failed for {number}: {e}')


def _doc_key(s):
    """Sanitize a phone number into a Firestore-safe map key."""
    return ''.join(ch if ch.isalnum() else '_' for ch in str(s))


def _process_campaign(camp_snap):
    """Run a single iteration on one campaign — dial whatever's still
    pending, up to PER_CAMPAIGN_CONCURRENCY at a time. Returns True when
    the campaign is fully drained."""
    camp_ref = camp_snap.reference
    camp = camp_snap.to_dict() or {}
    uid_path = camp_ref.parent.parent  # users/<uid>
    uid = uid_path.id

    if camp.get('status') != 'running':
        return True

    agent_id = camp.get('agent_id')
    agent = _load_agent(agent_id)
    if not agent:
        camp_ref.update({'status': 'failed', 'last_error': f'Agent {agent_id} not found'})
        return True

    provider_type = (agent.get('telephony_provider') or 'exotel').lower()
    telephony_config = load_provider_config(db, uid, provider_type)
    if not telephony_config:
        camp_ref.update({'status': 'failed', 'last_error': f'Provider {provider_type} not configured for user'})
        return True

    base_url = _resolve_base_url()
    if not base_url:
        camp_ref.update({'status': 'failed', 'last_error': 'No PUBLIC_BASE_URL configured'})
        return True

    numbers = list(camp.get('numbers') or [])
    dialed_map = camp.get('dialed') or {}
    pending = [n for n in numbers if _doc_key(n) not in dialed_map]
    if not pending:
        camp_ref.update({'status': 'completed', 'finished_at': firestore.SERVER_TIMESTAMP})
        print(f'[Campaign] ✅ {camp_ref.id} completed ({len(numbers)} numbers dialed)')
        return True

    batch = pending[:PER_CAMPAIGN_CONCURRENCY]
    print(f'[Campaign] {camp_ref.id} dialing batch of {len(batch)} (pending {len(pending)} / total {len(numbers)})')

    with ThreadPoolExecutor(max_workers=PER_CAMPAIGN_CONCURRENCY) as ex:
        futures = []
        for n in batch:
            if _stop.is_set():
                break
            futures.append(ex.submit(_dial_one, camp_ref, uid, agent_id, agent, telephony_config, base_url, n))
            # Pacing avoids burst rate-limits on the provider API.
            time.sleep(DIAL_PACING_SEC)
        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                print(f'[Campaign] task error: {e}')

    return False  # more work likely remaining; main loop will revisit


# --------------------------------------------------------------------------
# Main loop
# --------------------------------------------------------------------------
def main():
    print(f'[Campaign] Worker started — poll={POLL_INTERVAL}s, per_camp={PER_CAMPAIGN_CONCURRENCY}, global={GLOBAL_MAX_IN_FLIGHT}')
    while not _stop.is_set():
        try:
            running = list(
                db.collection_group('campaigns')
                  .where(filter=firestore.FieldFilter('status', '==', 'running'))
                  .limit(20)
                  .stream()
            )
            if not running:
                _stop.wait(POLL_INTERVAL)
                continue

            for c in running:
                if _stop.is_set():
                    break
                try:
                    _process_campaign(c)
                except Exception as e:
                    print(f'[Campaign] {c.id} failed: {e}')
                    traceback.print_exc()
        except Exception as e:
            print(f'[Campaign] loop error: {e}')
            traceback.print_exc()

        _stop.wait(POLL_INTERVAL)
    print('[Campaign] Worker stopped cleanly')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'[Campaign] fatal: {e}')
        traceback.print_exc()
        sys.exit(1)
