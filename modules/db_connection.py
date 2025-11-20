# modules/db_connection.py - Cross-Platform Version
import os
import platform
from contextlib import contextmanager
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import subprocess
import time
import signal

load_dotenv()

@contextmanager  
def get_postgres_connection():
    """Use native SSH port forwarding (works on Mac/Linux/Windows)"""
    
    local_port = 5433
    
    # Build SSH command - works on Mac, Linux, and Windows (via OpenSSH)
    tunnel_cmd = [
        'ssh',
        '-i', os.getenv('SSH_KEY_PATH'),
        '-L', f'{local_port}:localhost:{os.getenv("DB_PORT", 5432)}',
        '-N',  # Don't execute remote command
        '-o', 'StrictHostKeyChecking=no',  # Don't ask about host key
        '-o', 'UserKnownHostsFile=/dev/null',  # Don't save host key
        f'{os.getenv("SSH_USER")}@{os.getenv("VM_HOST")}'
    ]
    
    tunnel_process = None
    conn = None
    
    try:
        print("Starting SSH tunnel...")
        print(f"Command: {' '.join(tunnel_cmd)}")
        
        # Start tunnel in background
        tunnel_process = subprocess.Popen(
            tunnel_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        
        # Give tunnel time to establish
        time.sleep(3)
        
        # Check if process is still running
        if tunnel_process.poll() is not None:
            # Process died - get error
            _, stderr = tunnel_process.communicate()
            raise Exception(f"SSH tunnel failed: {stderr.decode()}")
        
        print(f"Connecting to Postgres on local port {local_port}...")
        
        conn = psycopg2.connect(
            host='127.0.0.1',
            port=local_port,
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            cursor_factory=RealDictCursor,
            connect_timeout=10
        )
        
        print("Connected successfully!")
        yield conn
        
    finally:
        if conn:
            conn.close()
        
        # Kill tunnel process - cross-platform way
        if tunnel_process:
            if platform.system() == 'Windows':
                subprocess.run(['taskkill', '/F', '/PID', str(tunnel_process.pid)], 
                              capture_output=True)
            else:
                # Mac/Linux
                try:
                    os.kill(tunnel_process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass  # Process already dead