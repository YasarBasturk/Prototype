import os
import sqlite3
import uuid
import json
from datetime import datetime

class Database:
    def __init__(self, db_path='results.db'):
        self.db_path = db_path
        self.initialize_db()
        
    def get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
        
    def initialize_db(self):
        """Initialize database tables if they don't exist"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create documents table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ocr_document (
            id TEXT PRIMARY KEY,
            document_name TEXT,
            filename TEXT,
            created_at TEXT,
            image_path TEXT,
            original_image_path TEXT
        )
        ''')
        
        # Create text items table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ocr_text_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT,
            text TEXT,
            confidence REAL,
            is_handwritten INTEGER,
            text_region TEXT,
            edited INTEGER DEFAULT 0,
            FOREIGN KEY (document_id) REFERENCES ocr_document (id)
        )
        ''')
        
        conn.commit()
        conn.close()
        
    def save_document(self, document_name, filename, original_image_path, output_image_path, json_data):
        """Save a document and its text items to the database"""
        document_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Insert document
        cursor.execute(
            'INSERT INTO ocr_document (id, document_name, filename, created_at, image_path, original_image_path) VALUES (?, ?, ?, ?, ?, ?)',
            (document_id, document_name, filename, created_at, output_image_path, original_image_path)
        )
        
        # Insert text items from cells_with_text
        if 'cells_with_text' in json_data:
            for cell in json_data['cells_with_text']:
                # Check if the item has been edited
                is_edited = 1 if cell.get('edited', False) else 0
                
                cursor.execute(
                    'INSERT INTO ocr_text_item (document_id, text, confidence, is_handwritten, text_region, edited) VALUES (?, ?, ?, ?, ?, ?)',
                    (
                        document_id, 
                        cell['text'], 
                        cell.get('confidence', 0.0),
                        0,  # Not handwritten by default
                        json.dumps({"cell_id": cell['cell_id']}),
                        is_edited   # Track edited state
                    )
                )
                
        # Insert text items from unassigned_text
        if 'unassigned_text' in json_data:
            for text in json_data['unassigned_text']:
                # Check if the item has been edited
                is_edited = 1 if text.get('edited', False) else 0
                
                cursor.execute(
                    'INSERT INTO ocr_text_item (document_id, text, confidence, is_handwritten, text_region, edited) VALUES (?, ?, ?, ?, ?, ?)',
                    (
                        document_id, 
                        text['text'], 
                        text.get('confidence', 0.0),
                        0,  # Not handwritten by default
                        json.dumps({"text_id": text['text_id']}),
                        is_edited   # Track edited state
                    )
                )
        
        conn.commit()
        conn.close()
        
        return document_id
        
    def get_all_documents(self):
        """Get all documents from the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT d.*, COUNT(t.id) as text_count 
            FROM ocr_document d
            LEFT JOIN ocr_text_item t ON d.id = t.document_id
            GROUP BY d.id
            ORDER BY d.created_at DESC
        ''')
        
        documents = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return documents
        
    def get_document(self, document_id):
        """Get a document and its text items by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get document
        cursor.execute('SELECT * FROM ocr_document WHERE id = ?', (document_id,))
        document_row = cursor.fetchone()
        if not document_row:
            conn.close()
            return None
            
        document = dict(document_row)
        
        # Get text items
        cursor.execute('SELECT * FROM ocr_text_item WHERE document_id = ?', (document_id,))
        document['text_items'] = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return document 