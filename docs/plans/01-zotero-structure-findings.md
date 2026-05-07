# Zotero backup structure findings

Observed on 2026-05-07 from /mnt/d/zotero_backup.

Top-level findings:
- zotero.sqlite present
- zotero_readonly.sqlite present
- storage/ present
- styles/ present
- translators/ present
- ai4paper.sqlite and ai4paper-user.sqlite also present

Storage statistics:
- 554 storage subdirectories
- 455 PDFs
- 91 HTML files
- 81 JSON files
- a few png/docx files

SQLite findings from zotero_readonly.sqlite:
- items: 1677
- itemAttachments: 540
- collections: 40
- collectionItems: 642
- tags: 1072
- itemTags: 1520

Attachment-path validation:
- sqlite attachment paths use standard Zotero pattern like storage:filename.pdf
- sampled records successfully map to /mnt/d/zotero_backup/storage/<item_key>/<filename>
- therefore sqlite can be used safely as the main metadata-enrichment source

Design implication:
- do not rely on directory scan alone
- adopt dual-source sync:
  1. directory scan for physical file truth
  2. zotero_readonly.sqlite for metadata truth

Recommended sync priority:
1. scan storage/ recursively for PDFs
2. read zotero_readonly.sqlite attachment mapping
3. join item metadata, creators, collections, tags
4. emit manifest.csv and library.json
