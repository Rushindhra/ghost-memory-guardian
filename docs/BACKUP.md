# Backup and restore

* **Back up:** Privacy Center → *Full backup (.zip)*. It contains `ghost.sqlite3`, every attached file under `files/`, and a `manifest.json`. JSON and Markdown exports are also offered for portability (readable without GHOST).
* **Restore** into an **empty** folder (the tool refuses to overwrite an existing database):

```powershell
.\.venv\Scripts\python.exe scripts\restore_backup.py C:\path\ghost-backup.zip --data-dir D:\GhostData
$env:GHOST_DATA_DIR = "D:\GhostData"        # or set the folder in Privacy Center / .env
```

Start GHOST, then Settings → **Rebuild search index** (the index is derived data and is not in the backup).
* The ZIP is **not encrypted**. Encrypt it (BitLocker/VeraCrypt/7-Zip AES/`age`) before storing it off-device.
* Zip entry names are validated during restore; a crafted archive cannot write outside the target folder (covered by tests).
* Deleting a record removes it from GHOST's database, index and files, but **not** from earlier backups or exports, and SSD/journaling file systems can retain traces until overwritten.
