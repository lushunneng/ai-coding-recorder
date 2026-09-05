from aicr.storage import RawWriter, recover_file

def test_raw_writer_and_recover(tmp_path):
 p=tmp_path/'raw.jsonl'; w=RawWriter(p); w.write('session_start',{}); w.close(); p.write_bytes(p.read_bytes()+b'{broken')
 s=recover_file(p,tmp_path/'metadata.json'); assert s['recovery']['last_valid_sequence']==1
