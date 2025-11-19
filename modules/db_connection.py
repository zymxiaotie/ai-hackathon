# modules/db_connection.py - Debug Version
import os
from contextlib import contextmanager
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import subprocess
import time

load_dotenv()

@contextmanager  
def get_postgres_connection():
    """Use Windows native SSH port forwarding"""
    
    local_port = 5433
    tunnel_cmd = [
        'ssh',
        '-i', os.getenv('SSH_KEY_PATH'),
        '-L', f'{local_port}:localhost:{os.getenv("DB_PORT", 5432)}',
        '-N',
        '-f',
        f'{os.getenv("SSH_USER")}@{os.getenv("VM_HOST")}'
    ]
    
    tunnel_process = None
    conn = None
    
    try:
        print("Starting SSH tunnel...")
        print(f"Command: {' '.join(tunnel_cmd)}")
        
        tunnel_process = subprocess.Popen(
            tunnel_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Check if process started successfully
        time.sleep(3)
        returncode = tunnel_process.poll()
        
        if returncode is not None:
            # Process already exited
            stdout, stderr = tunnel_process.communicate()
            print(f"SSH tunnel failed!")
            print(f"Return code: {returncode}")
            print(f"STDOUT: {stdout.decode()}")
            print(f"STDERR: {stderr.decode()}")
            raise Exception("SSH tunnel failed to start")
        
        print(f"Tunnel should be running. Connecting to Postgres on local port {local_port}...")
        
        conn = psycopg2.connect(
            host='127.0.0.1',
            port=local_port,
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            cursor_factory=RealDictCursor
        )
        
        print("Connected successfully!")
        yield conn
        
    finally:
        if conn:
            conn.close()
        if tunnel_process:
            tunnel_process.terminate()
        
        subprocess.run(['taskkill', '/F', '/IM', 'ssh.exe'], 
                      capture_output=True)