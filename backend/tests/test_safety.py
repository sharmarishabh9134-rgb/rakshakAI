from app.main import analyze_text
from app.ai import enforce_safety
from app.url_safety import analyze_url, URLRejected
import pytest

def test_detects_risk_indicators_without_certainty():
    result=analyze_text('Guaranteed returns. Act now and pay via UPI: https://x.invalid')
    assert result['risk']=='HIGH'
    assert 'not proof' in result['explanation']
    assert len(result['indicators']) >= 3

def test_ai_guardrail_rewrites_recommendation():
    result=enforce_safety({'explanation':'Buy this asset now','recommendation':'BUY XYZ','price_target':'100','details':{'action':'SELL','text':'Buy shares'}})
    assert 'not investment recommendations' in result['explanation']
    assert 'recommendation' not in result and 'price_target' not in result
    assert result['details']=={'text':result['explanation']}

def test_benign_text_is_not_proof_of_safety():
    result=analyze_text('Please read the published annual report.')
    assert result['risk']=='LOW'
    assert 'not a legal' in result['disclaimer']

@pytest.mark.parametrize('language,expected',[
    ('mr','धोक्याचे संकेत'),('te','ప్రమాద సూచనలు'),('ml','അപകട സൂചനകൾ'),
])
def test_additional_languages_localize_analysis(language,expected):
    result=analyze_text('Guaranteed returns. Act now and pay via UPI.',language)
    assert result['language']==language
    assert expected in result['explanation']
    assert result['findings']
    assert all(item['title'] and item['reason'] and item['recommended_action'] for item in result['findings'])

@pytest.mark.parametrize('url',['http://127.0.0.1/admin','http://10.0.0.8','http://localhost','http://[::1]/'])
def test_url_analyzer_rejects_private_or_local_targets(url):
    with pytest.raises(URLRejected):
        analyze_url(url)

@pytest.mark.parametrize('text',['Buy this stock now','Sell this share now','Hold this fund','The price will rise','Guaranteed return of 20%','Invest in this token','I recommend buying the share','Use Example Broker'])
def test_ai_safety_guard_blocks_financial_recommendations(text):
    guarded=enforce_safety({'explanation':text})
    assert 'not investment recommendations' in guarded['explanation']
