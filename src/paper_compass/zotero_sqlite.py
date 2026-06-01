"""
Zotero SQLite reader for paper-compass.

Adapted from RAG-Assistant-for-Zotero backend/zotero_dbase.py.
Reads official/backup zotero.sqlite via SQLite read-only URI and resolves
PDF attachment paths.

Design:
  - Thread-safe read-only connection
  - Returns plain dicts (no ZoteroItem dependency)
  - Handles storage: / attachments: / absolute path resolution
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from paper_compass.sqlite_readonly import connect_readonly


class ZoteroLibrary:
    """Read-only access to a Zotero SQLite database.

    Args:
        db_path: Path to zotero.sqlite. The connection is opened with mode=ro.
        storage_path: Override for Zotero storage directory.
                      Defaults to <db_parent>/storage.
    """

    def __init__(self, db_path: str, storage_path: Optional[str] = None):
        self.db_path = db_path
        self.storage_path = storage_path or str(Path(db_path).parent / "storage")
        self._local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            # Always open Zotero databases in SQLite read-only mode. Do not replace
            # this with sqlite3.connect(path), which could create/write sidecar files.
            self._local.conn = connect_readonly(self.db_path)
        return self._local.conn

    @contextmanager
    def _cursor(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    # ── queries ───────────────────────────────────────────────────────────

    def get_all_items_with_pdfs(self) -> List[Dict[str, Any]]:
        """Return all Zotero items that have PDF attachments with metadata.

        Returns list of dicts: item_id, key, title, date, authors, tags,
        collections, attachment_key, attachment_path, item_type, pdf_path.
        """
        query = """
        SELECT
            i.itemID,
            i.key,
            v_title.value AS title,
            v_date.value AS date,
            GROUP_CONCAT(DISTINCT cr.lastName) AS authors,
            GROUP_CONCAT(DISTINCT t.name) AS tags,
            GROUP_CONCAT(DISTINCT c.collectionName) AS collections,
            att.key AS attachment_key,
            att_path.path AS attachment_path,
            itemType.typeName AS item_type
        FROM items i
        JOIN itemTypes itemType ON i.itemTypeID = itemType.itemTypeID
        JOIN itemCreators ic ON i.itemID = ic.itemID
        JOIN creators cr ON ic.creatorID = cr.creatorID
        JOIN itemData d_title ON i.itemID = d_title.itemID
            AND d_title.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'title')
        JOIN itemDataValues v_title ON d_title.valueID = v_title.valueID
        LEFT JOIN itemData d_date ON i.itemID = d_date.itemID
            AND d_date.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'date')
        LEFT JOIN itemDataValues v_date ON d_date.valueID = v_date.valueID
        LEFT JOIN itemTags it ON i.itemID = it.itemID
        LEFT JOIN tags t ON it.tagID = t.tagID
        LEFT JOIN collectionItems ci ON i.itemID = ci.itemID
        LEFT JOIN collections c ON ci.collectionID = c.collectionID
        LEFT JOIN itemAttachments ia ON i.itemID = ia.parentItemID
        LEFT JOIN items att ON ia.itemID = att.itemID
        LEFT JOIN itemData att_data ON att.itemID = att_data.itemID
            AND att_data.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'mimeType')
        LEFT JOIN itemDataValues att_mime ON att_data.valueID = att_mime.valueID
        LEFT JOIN itemAttachments att_path ON att.itemID = att_path.itemID
        WHERE (att_mime.value = 'application/pdf' OR att_path.path LIKE '%.pdf')
        GROUP BY i.itemID
        """

        items: List[Dict[str, Any]] = []
        with self._cursor() as cur:
            cur.execute(query)
            for row in cur.fetchall():
                item = {
                    "item_id": str(row[0]),
                    "key": row[1],
                    "title": row[2] or "",
                    "date": row[3] or "",
                    "authors": self._split_csv(row[4]),
                    "tags": self._split_csv(row[5]),
                    "collections": self._split_csv(row[6]),
                    "attachment_key": row[7] or "",
                    "attachment_path": row[8] or "",
                    "item_type": row[9] or "",
                }
                item["pdf_path"] = self._resolve_pdf_path(item["attachment_key"], item["attachment_path"])
                items.append(item)

        return items

    def get_all_tags(self) -> List[str]:
        """Return all unique tags from items with PDFs."""
        with self._cursor() as cur:
            cur.execute("""
                SELECT DISTINCT t.name FROM tags t
                INNER JOIN itemTags it ON t.tagID = it.tagID
                INNER JOIN items i ON it.itemID = i.itemID
                WHERE i.itemID IN (
                    SELECT DISTINCT parentItemID FROM itemAttachments
                    WHERE contentType = 'application/pdf' AND parentItemID IS NOT NULL
                )
                ORDER BY t.name
            """)
            return [row[0] for row in cur.fetchall() if row[0]]

    def get_all_collections(self) -> List[Dict[str, Any]]:
        """Return all collections with item counts (only items with PDFs)."""
        with self._cursor() as cur:
            cur.execute("""
                SELECT c.collectionName, COUNT(DISTINCT ci.itemID) AS item_count
                FROM collections c
                LEFT JOIN collectionItems ci ON c.collectionID = ci.collectionID
                WHERE ci.itemID IN (
                    SELECT DISTINCT parentItemID FROM itemAttachments
                    WHERE contentType = 'application/pdf' AND parentItemID IS NOT NULL
                )
                GROUP BY c.collectionID
                HAVING item_count > 0
                ORDER BY c.collectionName
            """)
            return [{"name": row[0], "count": row[1]} for row in cur.fetchall() if row[0]]

    # ── helpers ───────────────────────────────────────────────────────────

    def _resolve_pdf_path(self, attachment_key: str, attachment_path: str) -> str:
        """Resolve Zotero attachment to an absolute PDF path."""
        if not attachment_key or not attachment_path:
            return ""

        if attachment_path.startswith("storage:"):
            base_filename = os.path.basename(attachment_path[len("storage:"):])
            resolved = os.path.join(self.storage_path, attachment_key, base_filename)
            return resolved if base_filename else ""

        if os.path.isabs(attachment_path):
            return attachment_path

        if attachment_path.startswith("attachments:"):
            relative = attachment_path[len("attachments:"):]
            return os.path.join(self.storage_path, relative)

        # Unknown format — best-effort
        base_filename = os.path.basename(attachment_path)
        return os.path.join(self.storage_path, attachment_key, base_filename) if base_filename else ""

    @staticmethod
    def _split_csv(value: Optional[str]) -> List[str]:
        """Split GROUP_CONCAT result into a clean list."""
        if not value:
            return []
        return [v.strip() for v in value.split(",") if v.strip()]

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None
