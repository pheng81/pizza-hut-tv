"""
Database Migration Manager
Handles database schema changes safely
"""
import sqlite3
import os
from datetime import datetime

class DatabaseMigration:
    def __init__(self, db_path='database.db'):
        self.db_path = db_path
        self.migrations_table = 'schema_migrations'
        self._ensure_migrations_table()
    
    def _ensure_migrations_table(self):
        """Create migrations tracking table if it doesn't exist"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.migrations_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT UNIQUE NOT NULL,
                description TEXT,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def get_applied_migrations(self):
        """Get list of applied migrations"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(f'SELECT version, description, applied_at FROM {self.migrations_table} ORDER BY id')
        migrations = c.fetchall()
        conn.close()
        return migrations
    
    def is_applied(self, version):
        """Check if migration is already applied"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(f'SELECT COUNT(*) FROM {self.migrations_table} WHERE version = ?', (version,))
        count = c.fetchone()[0]
        conn.close()
        return count > 0
    
    def apply_migration(self, version, description, sql_statements):
        """Apply a migration"""
        if self.is_applied(version):
            print(f"✓ Migration {version} already applied")
            return False
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            # Execute migration SQL
            for sql in sql_statements:
                c.execute(sql)
            
            # Record migration
            c.execute(f'''
                INSERT INTO {self.migrations_table} (version, description)
                VALUES (?, ?)
            ''', (version, description))
            
            conn.commit()
            print(f"✓ Applied migration {version}: {description}")
            return True
            
        except Exception as e:
            conn.rollback()
            print(f"✗ Failed to apply migration {version}: {e}")
            raise
        finally:
            conn.close()
    
    def show_status(self):
        """Show migration status"""
        migrations = self.get_applied_migrations()
        if not migrations:
            print("No migrations applied yet")
        else:
            print("\nApplied Migrations:")
            print("-" * 80)
            for version, description, applied_at in migrations:
                print(f"{version:20} {description:40} {applied_at}")
            print("-" * 80)

# Example migrations
def run_migrations(db_path='database.db'):
    """Run all pending migrations"""
    migrator = DatabaseMigration(db_path)
    
    # Show current status
    migrator.show_status()
    
    # Define migrations here
    migrations = [
        # Example migration
        # {
        #     'version': '001',
        #     'description': 'Add user preferences table',
        #     'sql': [
        #         '''CREATE TABLE IF NOT EXISTS user_preferences (
        #             id INTEGER PRIMARY KEY AUTOINCREMENT,
        #             username TEXT NOT NULL,
        #             theme TEXT DEFAULT 'light',
        #             language TEXT DEFAULT 'en',
        #             FOREIGN KEY (username) REFERENCES users(username)
        #         )'''
        #     ]
        # }
    ]
    
    # Apply each migration
    for migration in migrations:
        migrator.apply_migration(
            migration['version'],
            migration['description'],
            migration['sql']
        )
    
    print("\n✓ All migrations complete")

if __name__ == '__main__':
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else 'database.db'
    run_migrations(db_path)
