import os
os.environ.pop('OPENAI_API_KEY', None)
from fastapi.testclient import TestClient
from main import app
client = TestClient(app)

def test_health():
    r=client.get('/health');assert r.status_code==200 and r.json()['status']=='ok'

def test_analysis_and_roadmap():
    records=[{'grade':1,'subject':'공통수학','text':'기온 데이터를 수집하여 그래프를 그리고 일차함수로 모델을 만들어 오차를 분석하고 비교함.'},
             {'grade':1,'subject':'통합과학','text':'교실의 이산화탄소 농도를 반복 측정하여 환기 전후 변화와 오차를 분석함.'}]
    r=client.post('/analyze',json={'grade':1,'records':records,'analysis_mode':'rule'})
    assert r.status_code==200,r.text
    data=r.json();assert data['record_count']==2 and len(data['competencies'])==5 and len(data['evidence'])>=2
    assert all(m['total_score'] is None for m in data['majors'])
    p=client.post('/roadmap',json={'grade':1,'major':'환경공학과','records':records,'current_unit':'환경과 에너지'})
    assert p.status_code==200,p.text
    assert len(p.json()['activities'])==3 and bool(p.json()['subjects'])

def test_no_records():
    r=client.post('/analyze',json={'grade':1,'records':[]})
    assert r.status_code==400
