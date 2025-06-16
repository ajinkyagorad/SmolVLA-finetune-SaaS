"""
Database migration utility to add task_id column to training_jobs table.
Run this script directly to apply the migration.
"""
from app import create_app, db
import logging

def add_task_id_column():
    """Add task_id column to training_jobs table if it doesn't exist."""
    app = create_app()
    
    with app.app_context():
        # Check if column exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('training_jobs')]
        
        if 'task_id' not in columns:
            print("Adding task_id column to training_jobs table...")
            db.engine.execute('ALTER TABLE training_jobs ADD COLUMN task_id VARCHAR(128)')
            print("Migration completed successfully.")
        else:
            print("task_id column already exists in training_jobs table.")

if __name__ == '__main__':
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Run the migration
    add_task_id_column()
