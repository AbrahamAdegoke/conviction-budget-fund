"""Smoke tests for the Streamlit app: every page runs offline without errors."""

from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
ROOT = Path(__file__).resolve().parents[1]
PAGES = [str(ROOT / p) for p in
         ["streamlit_app.py", "app/the_fund.py", "app/mandate_and_views.py", "app/proposed_portfolio.py",
          "app/results.py"]]


@pytest.mark.parametrize("page", PAGES)
def test_page_runs(page):
    at = AppTest.from_file(page, default_timeout=120).run()
    assert not at.exception and not at.error


def test_manual_view_changes_the_portfolio():
    at = AppTest.from_file(PAGES[3],default_timeout=120)
    at.session_state["use_manual"], at.session_state["mv_q"] = True, 3.0
    at.run()
    effect = at.dataframe[0].value["Effect of manual view"]
    assert not at.exception and effect.abs().sum() > 0.01


def test_te_budget_slider_sets_the_ex_ante_tracking_error():
    for te_pct in (1.0, 3.0):
        at = AppTest.from_file(PAGES[3], default_timeout=120)
        at.session_state["te_pct"] = te_pct
        at.run()
        assert not at.exception and at.metric[0].value == f"{te_pct:.2f}%"


def test_overlapping_certain_views_show_a_message_not_a_crash():
    at = AppTest.from_file(PAGES[3], default_timeout=120)
    at.session_state["confidence"], at.session_state["use_manual"] = 1.0, True
    at.session_state["mv_long"], at.session_state["mv_short"] = "GLD", "VNQ"   # opposite of an automatic view
    at.session_state["mv_conf"] = 1.0
    at.run()
    assert not at.exception and at.error and "100% confidence" in at.error[0].value
