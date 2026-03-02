from qa_snapshot_tool.live_mirror import FocusMonitorThread, HierarchyThread, LogcatThread


def test_hierarchy_poll_interval_has_lower_bound():
    thread = HierarchyThread("SERIAL")
    thread.set_poll_interval(0.01)
    assert thread.poll_interval_s >= 0.2


def test_focus_poll_interval_has_lower_bound():
    thread = FocusMonitorThread("SERIAL")
    thread.set_poll_interval(0.01)
    assert thread.poll_interval_s >= 0.2


def test_logcat_emit_every_n_has_lower_bound():
    thread = LogcatThread("SERIAL")
    thread.set_emit_every_n(0)
    assert thread.emit_every_n == 1
