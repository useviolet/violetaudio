"""
Diagnose database connection issues
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
import psycopg2
from urllib.parse import urlparse

def diagnose_connection():
    """Diagnose why database connection is failing"""
    
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    
    print("=" * 80)
    print("🔍 Database Connection Diagnosis")
    print("=" * 80)
    
    # Parse URL
    parsed = urlparse(database_url)
    print(f"\n📋 Connection Details:")
    print(f"   Host: {parsed.hostname}")
    print(f"   Port: {parsed.port or 5432}")
    print(f"   Database: {parsed.path[1:] if parsed.path else 'N/A'}")
    print(f"   User: {parsed.username}")
    print(f"   Password: {'*' * len(parsed.password) if parsed.password else 'N/A'}")
    
    # Check 1: Basic network connectivity
    print(f"\n1️⃣ Testing basic network connectivity...")
    try:
        import socket
        host = parsed.hostname
        port = parsed.port or 5432
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            print(f"   ✅ Port {port} is reachable on {host}")
        else:
            print(f"   ❌ Port {port} is NOT reachable on {host}")
            print(f"   💡 Possible causes:")
            print(f"      - Database server is down")
            print(f"      - Firewall blocking connection")
            print(f"      - Database is sleeping (Render free tier)")
    except Exception as e:
        print(f"   ⚠️ Network test failed: {e}")
    
    # Check 2: SSL/TLS requirements
    print(f"\n2️⃣ Testing SSL/TLS connection...")
    ssl_modes = ["require", "prefer", "allow"]
    for ssl_mode in ssl_modes:
        try:
            conn = psycopg2.connect(
                database_url,
                connect_timeout=5,
                sslmode=ssl_mode
            )
            conn.close()
            print(f"   ✅ Connection successful with sslmode={ssl_mode}")
            break
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            if "SSL/TLS required" in error_msg:
                print(f"   ❌ sslmode={ssl_mode}: SSL/TLS required by server")
            elif "SSL connection has been closed" in error_msg:
                print(f"   ⚠️ sslmode={ssl_mode}: SSL connection closed unexpectedly")
            elif "timeout" in error_msg.lower():
                print(f"   ⚠️ sslmode={ssl_mode}: Connection timeout")
            else:
                print(f"   ❌ sslmode={ssl_mode}: {error_msg[:100]}")
        except Exception as e:
            print(f"   ❌ sslmode={ssl_mode}: {type(e).__name__}: {str(e)[:100]}")
    
    # Check 3: SQLAlchemy connection
    print(f"\n3️⃣ Testing SQLAlchemy connection...")
    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=1,
            max_overflow=0,
            connect_args={
                "connect_timeout": 10,
                "sslmode": "require"
            }
        )
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"   ✅ SQLAlchemy connection successful")
            print(f"   PostgreSQL version: {version[:50]}...")
        engine.dispose()
    except Exception as e:
        print(f"   ❌ SQLAlchemy connection failed: {type(e).__name__}")
        print(f"   Error: {str(e)[:200]}")
        print(f"\n   💡 Possible solutions:")
        print(f"      1. Check if database is running (Render databases sleep after inactivity)")
        print(f"      2. Verify database URL is correct")
        print(f"      3. Check firewall/network settings")
        print(f"      4. Try connecting from a different network")
        print(f"      5. Check Render dashboard for database status")
    
    # Check 4: Render-specific issues
    print(f"\n4️⃣ Render.com Specific Checks...")
    if "render.com" in database_url:
        print(f"   ℹ️  This is a Render.com database")
        print(f"   💡 Render free tier databases:")
        print(f"      - Sleep after 90 days of inactivity")
        print(f"      - Require SSL connections")
        print(f"      - May have connection limits")
        print(f"      - Check Render dashboard: https://dashboard.render.com")
        print(f"      - Wake up database if it's sleeping")
    
    print("\n" + "=" * 80)
    print("✅ Diagnosis complete")
    print("=" * 80)

if __name__ == "__main__":
    diagnose_connection()

