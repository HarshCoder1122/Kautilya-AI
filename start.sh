# Force single-threaded execution for AI models to save memory
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

# Start Automated Campaign Dialer in background
python campaign_worker.py &

# Start Gunicorn Web Server (Optimized for concurrency: 2 workers, 4 threads each)
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 600 --worker-class gthread

