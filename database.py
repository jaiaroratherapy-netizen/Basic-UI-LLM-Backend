"""
Database connection and helper functions for Supabase
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import os
from typing import Optional, List, Dict
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================
# Configuration
# ============================================

# Get from environment variable
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set!")

# ============================================
# Connection Pool Helper
# ============================================

@contextmanager
def get_db_connection():
    """
    Context manager for database connections
    Automatically handles opening and closing connections
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM students")
    """
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

# ============================================
# Database Helper Functions
# ============================================

def get_or_create_student(email: str, name: str) -> int:
    """
    Get student_id if exists, otherwise create new student
    
    Args:
        email: Student's email (used as unique identifier)
        name: Student's name
    
    Returns:
        student_id: The ID of the student
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Try to get existing student
        cursor.execute(
            "SELECT student_id FROM students WHERE email = %s",
            (email,)
        )
        result = cursor.fetchone()
        
        if result:
            # Update last_login
            cursor.execute(
                "UPDATE students SET last_login = CURRENT_TIMESTAMP WHERE student_id = %s",
                (result['student_id'],)
            )
            return result['student_id']
        
        # Create new student
        cursor.execute(
            """
            INSERT INTO students (email, name, created_at, last_login)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING student_id
            """,
            (email, name)
        )
        result = cursor.fetchone()
        return result['student_id']

def create_session(student_id: int, ai_client_type: str) -> tuple:
    """
    Create a new session
    
    Args:
        student_id: ID of the student
        ai_client_type: Type of AI (e.g., "Pritam", "Jitesh")
    
    Returns:
        (session_id, session_name): UUID and display name
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Generate UUID for session
        session_id = str(uuid.uuid4())
        
        # Count existing sessions for this student to generate name
        cursor.execute(
            "SELECT COUNT(*) as count FROM sessions WHERE student_id = %s",
            (student_id,)
        )
        count = cursor.fetchone()['count']
        session_name = f"Session-{count + 1}"
        
        # Create session
        cursor.execute(
            """
            INSERT INTO sessions (session_id, student_id, ai_client_type, created_at, status)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, 'active')
            """,
            (session_id, student_id, ai_client_type)
        )
        
        return session_id, session_name

def save_message(session_id: str, sender_type: str, content: str) -> None:
    """
    Save a message to the database
    
    Args:
        session_id: UUID of the session
        sender_type: "user" or "assistant"
        content: Message text
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get next sequence number for this session
        cursor.execute(
            "SELECT COALESCE(MAX(sequence_number), 0) + 1 as next_seq FROM messages WHERE session_id = %s",
            (session_id,)
        )
        sequence_number = cursor.fetchone()['next_seq']
        
        # Insert message
        cursor.execute(
            """
            INSERT INTO messages (session_id, sender_type, content, sequence_number, created_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            """,
            (session_id, sender_type, content, sequence_number)
        )

def get_conversation_history(session_id: str) -> List[Dict]:
    """
    Get all messages for a session in order
    
    Args:
        session_id: UUID of the session
    
    Returns:
        List of message dicts with role, content, timestamp
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT sender_type, content, created_at
            FROM messages
            WHERE session_id = %s
            ORDER BY sequence_number ASC
            """,
            (session_id,)
        )
        
        messages = cursor.fetchall()
        
        # Convert to list of dicts
        return [
            {
                "role": msg['sender_type'],
                "content": msg['content'],
                "timestamp": msg['created_at'].strftime("%Y-%m-%d %H:%M:%S")
            }
            for msg in messages
        ]

def get_user_sessions(email: str) -> List[Dict]:
    """
    Get all sessions for a user
    
    Args:
        email: Student's email
    
    Returns:
        List of session dicts with id, name, created_at, message_count
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT 
                s.session_id,
                s.ai_client_type,
                s.created_at,
                COUNT(m.message_id) as message_count
            FROM sessions s
            JOIN students st ON s.student_id = st.student_id
            LEFT JOIN messages m ON s.session_id = m.session_id
            WHERE st.email = %s
            GROUP BY s.session_id, s.ai_client_type, s.created_at
            ORDER BY s.created_at DESC
            """,
            (email,)
        )
        
        sessions = cursor.fetchall()
        
        # Count sessions to generate session names
        session_list = []
        for idx, session in enumerate(sessions):
            session_list.append({
                "session_id": str(session['session_id']),
                "session_name": f"Session-{len(sessions) - idx}",
                "created_at": session['created_at'].strftime("%Y-%m-%d %H:%M:%S"),
                "message_count": session['message_count']
            })
        
        return session_list

def session_exists(session_id: str) -> bool:
    """
    Check if a session exists
    
    Args:
        session_id: UUID of the session
    
    Returns:
        True if exists, False otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT 1 FROM sessions WHERE session_id = %s",
            (session_id,)
        )
        
        return cursor.fetchone() is not None

def get_session_name(session_id: str, email: str) -> Optional[str]:
    """
    Get session name for display
    
    Args:
        session_id: UUID of the session
        email: Student's email (for verification)
    
    Returns:
        Session name or None if not found
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get session created_at and total sessions for this user
        cursor.execute(
            """
            SELECT s.created_at,
                   (SELECT COUNT(*) FROM sessions s2 
                    JOIN students st2 ON s2.student_id = st2.student_id
                    WHERE st2.email = %s AND s2.created_at >= s.created_at) as session_number
            FROM sessions s
            JOIN students st ON s.student_id = st.student_id
            WHERE s.session_id = %s AND st.email = %s
            """,
            (email, session_id, email)
        )
        
        result = cursor.fetchone()
        
        if result:
            return f"Session-{result['session_number']}"
        
        return None

# ============================================
# Test Connection
# ============================================

def test_connection():
    """Test if database connection works"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            print("✅ Database connection successful!")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    # Test the connection when running this file directly
    test_connection()
