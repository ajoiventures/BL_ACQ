import json,hashlib,sqlite3,copy
import pytest
from backend.core import tickets,release_sync
from tools.sync_ticket_release import event

def fixture(tmp_path):
    db=sqlite3.connect(tmp_path/'release.db');db.row_factory=sqlite3.Row
    db.execute('CREATE TABLE audit(seq INTEGER PRIMARY KEY,domain,actor,action,object_id,body,prev_hash,hash,at)')
    old=json.loads(tickets.SEED.read_text(encoding='utf-8'))[:-1]
    p=tmp_path/'old.json';p.write_text(json.dumps(old));tickets.import_manifest(db,event,p);db.commit()
    return db,old

def digest(rows):return hashlib.sha256(release_sync.canonical(rows).encode()).hexdigest()
def test_sync_preserves_user_state_and_evidence(tmp_path):
    db,old=fixture(tmp_path);rows=json.loads(tickets.SEED.read_text(encoding='utf-8'));r=rows[0];r['acceptance']+=' Revised acceptance.'
    db.execute("UPDATE project_tickets SET status='in_progress',evidence='human evidence',source='private local source',version=5 WHERE id=?",(r['id'],));db.commit()
    with db:
        result=release_sync.synchronize(db,event,rows,digest(rows));assert result['inserted']==[rows[-1]['id']] and r['id'] in result['metadata_updated']
    actual=tickets.get(db,r['id']);assert (actual['status'],actual['evidence'],actual['source'],actual['version'])==('in_progress','human evidence','private local source',6)
    assert tickets.history(db,r['id'])[-1]['action']=='TICKET_METADATA_SYNC'
    with db: assert release_sync.synchronize(db,event,rows,digest(rows))['replay']
    assert tickets.get(db,r['id'])['version']==6
    with pytest.raises(sqlite3.IntegrityError),db:db.execute('DELETE FROM release_receipts')
    backup=sqlite3.connect(tmp_path/'backup.db');db.backup(backup);assert backup.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert backup.execute('SELECT count(*) FROM project_tickets').fetchone()[0]==len(rows)

def test_sync_rejects_wrong_digest_and_removed_records(tmp_path):
    db,old=fixture(tmp_path)
    with pytest.raises(ValueError,match='digest'),db:release_sync.synchronize(db,event,old,'wrong')
    db.execute("UPDATE project_tickets SET id='EXTRA' WHERE id=?",(old[0]['id'],));db.commit()
    with pytest.raises(ValueError,match='omit'),db:release_sync.synchronize(db,event,old,digest(old))

def test_sync_reviewed_metadata_conflict_rolls_back(tmp_path):
    db,old=fixture(tmp_path);rows=copy.deepcopy(old);rows[-1]['acceptance']+=' revised';rows[0]['title']+=' revised'
    db.execute("UPDATE project_tickets SET status='closed' WHERE id=?",(rows[-1]['id'],));db.commit()
    with pytest.raises(ValueError,match='Reviewed'),db:release_sync.synchronize(db,event,rows,digest(rows))
    assert tickets.get(db,rows[0]['id'])['title']==old[0]['title']

def test_preflight_rejects_runtime_drift_and_replay_metadata_drift(tmp_path):
    db,old=fixture(tmp_path);rows=json.loads(tickets.SEED.read_text(encoding='utf-8'));pre=release_sync.state_digest(db)
    with db:db.execute("UPDATE project_tickets SET evidence='later observation', version=version+1 WHERE id=?",(old[0]['id'],))
    with pytest.raises(ValueError,match='Runtime drift'),db:release_sync.synchronize(db,event,rows,digest(rows),pre)
    with db:release_sync.synchronize(db,event,rows,digest(rows),release_sync.state_digest(db))
    with db:db.execute("UPDATE project_tickets SET title='Untracked change' WHERE id=?",(old[0]['id'],))
    with pytest.raises(ValueError,match='metadata drift'),db:release_sync.synchronize(db,event,rows,digest(rows))


@pytest.mark.parametrize(("column", "message"), [
    ("manifest", "manifest does not match"),
    ("result", "result does not match"),
])
def test_replay_rejects_a_divergent_receipt(tmp_path, column, message):
    db, rows = fixture(tmp_path)
    release_sha = digest(rows)
    with db:
        release_sync.synchronize(db, event, rows, release_sha)
    with db:
        # Model receipt corruption from an offline restore in a disposable fixture.
        db.execute("DROP TRIGGER release_no_update")
        db.execute(f"UPDATE release_receipts SET {column} = '{{}}'")
    before = release_sync.state_digest(db)
    with pytest.raises(ValueError, match=message), db:
        release_sync.synchronize(db, event, rows, release_sha)
    assert release_sync.state_digest(db) == before


def test_release_preserves_explicit_reviewed_execution_lineage(tmp_path):
    from backend.core.acquisition_patterns import digest as pattern_digest

    db, rows = fixture(tmp_path)
    ticket = next(row for row in rows if row["area"] == "Acquisition")
    ticket["reviewed_execution_links"] = [{"assessment_id": "assessment", "operation_id": "operation"}]
    body = '{"note":"Exercise involving café records"}'
    fingerprint = pattern_digest({"operation_id": "operation", "body": body, "prior_hash": "GENESIS"})
    with db:
        db.execute("CREATE TABLE assessments(id, skill_id, evidence, reviewer, verdict)")
        db.execute("CREATE TABLE acquisition_pattern_receipts(operation_id, body, prior_hash, receipt_hash)")
        db.execute("INSERT INTO acquisition_pattern_receipts VALUES(?,?,?,?)",
                   ("operation", body, "GENESIS", fingerprint))
        db.execute("INSERT INTO assessments VALUES(?,?,?,?,?)",
                   ("assessment", "skill", "Other exercise was reviewed", "SW-13", "PASS_SIMULATION"))

    before = release_sync.state_digest(db)
    with pytest.raises(ValueError, match="exact execution receipt"), db:
        release_sync.synchronize(db, event, rows, digest(rows))
    assert release_sync.state_digest(db) == before

    with db:
        db.execute("UPDATE assessments SET evidence=?", (f"Checked exercise evidence\nreceipt_sha256:{fingerprint}",))
        result = release_sync.synchronize(db, event, rows, digest(rows))
    assert result["reviewed_execution_links"] == [{
        "ticket_id": ticket["id"], "assessment_id": "assessment", "operation_id": "operation",
        "skill_id": "skill", "receipt_sha256": fingerprint, "verdict": "PASS_SIMULATION",
    }]
    assert tickets.get(db, ticket["id"])["status"] == ticket["status"]
    assert release_sync.synchronize(db, event, rows, digest(rows)) == {**result, "replay": True}
