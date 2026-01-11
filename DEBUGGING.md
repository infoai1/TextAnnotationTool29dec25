# Annotation Tool Debugging Guide

## Quick Reference

**Container Status:**
```bash
docker ps | grep annotation
docker logs islamic_annotation_tool --tail 20
```

**Restart Container:**
```bash
cd /root/annotation_tool
docker compose restart
# OR full rebuild
docker compose build && docker compose up -d
```

---

## Log Locations

| Log File | Purpose | Location |
|----------|---------|----------|
| App Log | Main application log | `/root/annotation_tool/logs/app.log` |
| Button Log | Button click tracking | `/root/annotation_tool/logs/buttons.log` |
| Docker Logs | Container output | `docker logs islamic_annotation_tool` |

---

## Quick Commands

### Watch Logs
```bash
# Watch app log
tail -f /root/annotation_tool/logs/app.log

# Watch button log
tail -f /root/annotation_tool/logs/buttons.log

# Watch both
tail -f /root/annotation_tool/logs/*.log

# Docker logs (live)
docker logs -f islamic_annotation_tool
```

### Search Logs
```bash
# Find errors
grep ERROR /root/annotation_tool/logs/app.log

# Find saves
grep SAVE /root/annotation_tool/logs/app.log | tail -10

# Find specific book
grep "book=women_in_islam" /root/annotation_tool/logs/app.log

# Find version operations
grep VERSION /root/annotation_tool/logs/app.log
```

---

## Common Issues

### Issue: Changes not saving

**Symptoms:**
- Progress lost after refresh
- "Last saved: Never" in UI

**Debug:**
```bash
# Check if saves are happening
grep SAVE /root/annotation_tool/logs/app.log | tail -5

# Check auto-save interval (should trigger every 30s)
grep "Auto-saved" /root/annotation_tool/logs/app.log | tail -10

# Check progress files exist
ls -lh /root/annotation_tool/data/*_progress.json
```

**Fix:**
1. Check container is running: `docker ps | grep annotation`
2. Check disk space: `df -h`
3. Check permissions: `ls -la /root/annotation_tool/data/`
4. Restart container: `docker compose restart`

---

### Issue: Book not loading

**Symptoms:**
- Empty book list
- "File not found" error

**Debug:**
```bash
# Check data files exist
ls /root/annotation_tool/data/*progress.json

# Validate JSON format
python3 -c "import json; json.load(open('/root/annotation_tool/data/women_in_islam_admin_progress.json'))"

# Check library books
ls /root/annotation_tool/books/
```

**Fix:**
1. Verify file exists in correct location
2. Check JSON is valid (not corrupted)
3. Check file permissions
4. Check book metadata: `cat /root/annotation_tool/books/women_in_islam/meta.json`

---

### Issue: PDF not matching text

**Symptoms:**
- Page numbers show "Unknown"
- Wrong page highlighted

**Debug:**
```bash
# Check PDF exists
ls /root/annotation_tool/books/*/document.pdf

# Check PDF loaded flag in progress file
grep "pdf_loaded" /root/annotation_tool/data/*_progress.json
```

**Fix:**
1. Re-upload PDF in the tool
2. Click "Match All Paragraphs" button
3. Check PDF and DOCX have same content
4. Check logs for PDF parsing errors

---

### Issue: Container won't start

**Symptoms:**
- `docker ps` shows container exited
- Container keeps restarting

**Debug:**
```bash
# Check logs for error
docker logs islamic_annotation_tool

# Check build errors
docker compose build

# Check port conflicts
netstat -tulpn | grep 8502
```

**Fix:**
```bash
# Rebuild from scratch
docker compose down
docker compose build --no-cache
docker compose up -d

# Check logs after restart
docker logs islamic_annotation_tool --tail 50
```

---

### Issue: Slow UI / Performance

**Symptoms:**
- Page takes long to load
- Laggy interactions

**Debug:**
```bash
# Check full reruns (bad - causes entire page reload)
grep "st.rerun()" /root/annotation_tool/app.py | grep -v "scope="

# Check memory usage
docker stats islamic_annotation_tool --no-stream
```

**Fix:**
- Use `st.rerun(scope="fragment")` inside @st.fragment functions
- Reduce auto-save frequency if needed (config.py)
- Check container memory limits in docker-compose.yml

---

### Issue: Version history lost

**Symptoms:**
- Can't rollback to previous version
- Version list empty

**Debug:**
```bash
# Check version files exist
ls /root/annotation_tool/data/versions/women_in_islam_admin/

# Check version count (should keep last 10)
ls /root/annotation_tool/data/versions/women_in_islam_admin/ | wc -l
```

**Fix:**
- Versions are auto-created on save
- Check VERSION_KEEP_COUNT in config.py (default: 10)
- Older versions are auto-deleted

---

## Rollback Procedures

### Rollback last Git commit
```bash
cd /root/annotation_tool
git log --oneline -5  # See recent commits
git checkout HEAD~1 -- app.py  # Rollback app.py one commit
docker compose restart
```

### Rollback to backup file
```bash
# List backups
ls -lh /root/annotation_tool/app.py.backup.*

# Restore from backup
cp app.py.backup.20260111_151243 app.py
docker compose restart
```

### Rollback book progress to version
Use the UI "Versions" feature in sidebar, or manually:
```bash
# List versions
ls /root/annotation_tool/data/versions/women_in_islam_admin/

# Copy version to current progress
cp /root/annotation_tool/data/versions/women_in_islam_admin/v_2026-01-11T13:29:20.json \
   /root/annotation_tool/data/women_in_islam_admin_progress.json
```

---

## Module Import Errors

### Issue: "ModuleNotFoundError"

**Debug:**
```bash
# Test imports in container
docker exec islamic_annotation_tool python3 -c "from config import DATA_DIR; print(DATA_DIR)"
docker exec islamic_annotation_tool python3 -c "from helpers import slugify; print(slugify('test'))"
docker exec islamic_annotation_tool python3 -c "import db; print('db OK')"
```

**Fix:**
- Rebuild container: `docker compose build`
- Check file exists: `docker exec islamic_annotation_tool ls -la /app/config.py`

---

## Data Files Reference

### Progress File Structure
Location: `/root/annotation_tool/data/{book_slug}_{user}_progress.json`

```json
{
  "book_title": "Women in Islam",
  "paragraphs": [...],
  "groups": [...],
  "pdf_loaded": true,
  "pdf_pages": [...],
  "book_status": "in_progress",
  "last_saved": "2026-01-11T13:29:20",
  "last_saved_by": "admin"
}
```

### Meta File Structure
Location: `/root/annotation_tool/books/{book_folder}/meta.json`

```json
{
  "title": "Women in Islam",
  "author": "Maulana Wahiduddin Khan",
  "status": "in_progress",
  "locked_by": "admin",
  "locked_at": "2026-01-11T13:29:20"
}
```

---

## Performance Benchmarks

| Operation | Expected Time | What to Check |
|-----------|---------------|---------------|
| Book load | < 3 seconds | DOCX parsing, PDF matching |
| Auto-save | < 500ms | File write speed |
| Page render | < 1 second | Number of paragraphs |
| PDF match all | 5-30 seconds | PDF size, paragraph count |

---

## Health Checks

### Quick Health Check
```bash
# 1. Container running?
docker ps | grep annotation

# 2. App responding?
curl -s http://localhost:8502/_stcore/health

# 3. Recent saves?
grep SAVE /root/annotation_tool/logs/app.log | tail -3

# 4. Disk space?
df -h /root/annotation_tool
```

---

## Contact & Support

- **GitHub Issues**: https://github.com/anthropics/claude-code/issues
- **Log Location**: Attach `/root/annotation_tool/logs/app.log` when reporting issues
- **Configuration**: `/root/annotation_tool/config.py`

---

**Last Updated:** Jan 11, 2026
**Version:** 2.5.0 (Refactor Phase 1)
