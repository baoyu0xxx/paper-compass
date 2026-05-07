# SQLite-enhanced Zotero sync plan

Revised sync design after inspecting the real backup structure.

Final sync model:
- file existence source: /mnt/d/zotero_backup/storage/**
- metadata source: /mnt/d/zotero_backup/zotero_readonly.sqlite
- fallback metadata mode: scan-only when sqlite join fails

Output files:
- data/zotero-export/manifest.csv
- data/zotero-export/library.json

Minimum manifest fields:
- file_location
- title
- doi

Recommended library.json fields:
- doc_id
- zotero_item_key
- attachment_key
- title
- creators
- year
- journal
- doi
- collections
- tags
- pdf_path
- relative_path
- sha256
- metadata_source

Required implementation steps:
1. scan PDFs under storage/
2. read attachment records from zotero_readonly.sqlite
3. resolve actual PDF path from storage/<attachment_key>/<filename>
4. join parent item metadata
5. join creators
6. join collections
7. join tags
8. emit normalized records

Fallback rule:
- if sqlite join fails, keep the file in outputs with low-quality metadata rather than dropping it
