import pytest

from logi_mouse_map import instance


def test_second_lock_fails_until_first_released(tmp_path):
    path = tmp_path / "app.lock"
    first = instance.acquire(path)
    with pytest.raises(instance.AlreadyRunningError):
        instance.acquire(path)
    first.close()
    instance.acquire(path).close()
