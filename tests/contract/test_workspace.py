from yt2wa.infrastructure.local_workspace import LocalWorkspace


def test_job_dirs_are_unique_and_cleaned_up(tmp_path):
    workspace = LocalWorkspace(tmp_path / "work")
    first, second = workspace.new_job_dir(), workspace.new_job_dir()
    assert first != second
    workspace.cleanup(first)
    assert not first.exists()
    assert second.exists()


def test_publish_never_overwrites_an_existing_file(tmp_path):
    workspace = LocalWorkspace(tmp_path / "work")
    out = tmp_path / "out"
    for text in ("one", "two"):
        src = tmp_path / "src.mp4"
        src.write_text(text)
        workspace.publish(src, out, "clip.mp4")
    assert (out / "clip.mp4").read_text() == "one"
    assert (out / "clip-1.mp4").read_text() == "two"


def test_stale_jobs_only_lists_old_folders(tmp_path):
    workspace = LocalWorkspace(tmp_path / "work")
    job = workspace.new_job_dir()
    assert workspace.stale_jobs(3600) == []
    assert workspace.stale_jobs(-1) == [job]
