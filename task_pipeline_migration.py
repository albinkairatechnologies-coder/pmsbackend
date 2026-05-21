import sys
import os
from dotenv import load_dotenv
load_dotenv()
from app.utils.database import get_db_connection

def run():
    print("Connecting to database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        print("Checking/Creating task_pipeline_stages table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_pipeline_stages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task_id INT NOT NULL,
                stage_name VARCHAR(50) NOT NULL,
                start_date DATE NULL,
                end_date DATE NULL,
                responsible_person_id INT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (responsible_person_id) REFERENCES users(id) ON DELETE SET NULL,
                UNIQUE KEY unique_task_stage (task_id, stage_name)
            )
        """)
        conn.commit()
        print("Table 'task_pipeline_stages' verified/created successfully.")
    except Exception as e:
        print(f"Error creating table: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    run()
