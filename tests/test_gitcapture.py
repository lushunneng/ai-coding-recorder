from aicr.gitcapture import snapshot


def test_non_git(tmp_path):
    r = snapshot(str(tmp_path))
    assert r["is_git"] is False
