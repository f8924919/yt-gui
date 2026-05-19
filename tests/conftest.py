import pytest

from yt_gui import i18n


@pytest.fixture(autouse=True)
def _restore_language():
    original = i18n._current_lang
    yield
    i18n._current_lang = original
