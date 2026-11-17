"""Differential contract tests against the original global-search algorithm."""
import sqlite3

import pytest

from hub.search import folded, search
from scripts.benchmark_search import SearchStore, seed, legacy_search, legacy_folded


@pytest.mark.parametrize('text',[
    'abc', 'Ação', 'Ação', 'ANA JÚLIA', 'Straße', 'İstanbul',
    '100%', 'café_12', '音楽', '', '  Espaço  ', 'ẞ', 'ﬂauta',
])
def test_fast_ascii_folding_preserves_reference_unicode_semantics(text):
    assert folded(text)==legacy_folded(text)


def test_global_search_rank_and_results_match_legacy_on_mixed_data(tmp_path):
    path=tmp_path/'search-fixture.db'
    seed(path)
    with sqlite3.connect(path) as db:
        db.executemany('INSERT INTO notes VALUES (?,?,?,?,?,?)', [
            ('n-a','AÇÃO musical','Música com partitura 100% revisada',None,None,None),
            ('n-b','Ação musical','Outra música com acento composto',None,None,None),
            ('n-c','Ação de estudo','Objetivo: 100% qualidade',None,None,None),
            ('n-d','Musicxml','Revisão em andamento',None,None,None),
            ('n-e','Ana Júlia','Estudo de flauta',None,None,None),
        ])
    store=SearchStore(str(path))
    queries=(
        'ação', 'acao', 'ACAO', 'musica', 'MÚSICA', 'musicxml',
        'projeto', 'revisao', 'ana', 'ana julia', '100%',
        '%_', "' OR 1=1 --", 'inexistente', 'ção', 'Projeto Musica 42',
        'ação musical', 'musicXML 12', 'ana empresa'
    )
    for q in queries:
        for per_kind,total in ((8,40),(1,2),(5,12),(100,100)):
            assert search(store,q,per_kind=per_kind,total=total)==legacy_search(
                store,q,per_kind=per_kind,total=total),(q,per_kind,total)


def test_search_can_limit_large_number_of_matching_candidates(tmp_path):
    path=tmp_path/'search-fixture.db'
    seed(path)
    store=SearchStore(str(path))
    actual=search(store,'revisao')
    expected=legacy_search(store,'revisao')
    assert actual==expected
    assert actual['limited'] is True
    assert len(actual['results'])<=40


@pytest.mark.parametrize('per_kind,total',[(0,40),(8,0),(101,40),(8,101)])
def test_search_rejects_unsafe_non_api_limits(tmp_path,per_kind,total):
    path=tmp_path/'search-fixture.db'
    seed(path)
    with pytest.raises(ValueError,match='Limites da pesquisa'):
        search(SearchStore(str(path)),'música',per_kind=per_kind,total=total)
