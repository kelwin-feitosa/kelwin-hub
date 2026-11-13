"""Synthetic HTTP benchmark contracts; never measure a personal database."""
from scripts.benchmark_http import benchmark, percentile95
import pytest


def test_benchmark_uses_bounded_temporary_sqlite_and_reports_real_samples():
    report=benchmark(records=37,iterations=3)
    assert report['tasks']==37
    assert report['iterations_per_route']==3
    assert set(report['routes'])=={'tasks_page','tasks_all_legacy','focus_30min','workspace'}
    for name,data in report['routes'].items():
        assert data['p50_ms']>=0 and data['p95_ms']>=0
        assert data['response_bytes']>=0
    assert report['routes']['tasks_page']['response_bytes'] < report['routes']['tasks_all_legacy']['response_bytes']


@pytest.mark.parametrize(('records','iterations'),[(5001,3),(-1,3),(3,1),(3,201)])
def test_benchmark_enforces_safety_bounds(records,iterations):
    with pytest.raises(ValueError):
        benchmark(records,iterations)


def test_percentile95_is_upper_tail_not_mean():
    assert percentile95([1,2,3,4,5,6,7,8,9,10])==10
