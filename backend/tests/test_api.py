from fastapi.testclient import TestClient
from uuid import uuid4
from app.main import app, SessionLocal
from app.models import User

def test_health_and_education():
    c=TestClient(app)
    assert c.get('/api/health').json()['status']=='ok'
    assert len(c.get('/api/education').json()) >= 3

def test_guest_cannot_analyze_without_signing_in():
    c=TestClient(app)
    result=c.post('/api/analyze/message',json={'text':'Some financial message'})
    assert result.status_code==401

def test_registration_login_and_history():
    c=TestClient(app)
    email=f'test-account-{uuid4().hex}@example.com'
    r=c.post('/api/auth/register',json={'email':email,'name':'Test User','password':'StrongTestPass!2026'})
    assert r.status_code==200
    try:
        logged_in=c.post('/api/auth/login',json={'email':email,'password':'StrongTestPass!2026'})
        assert logged_in.status_code==200
        headers={'Authorization':'Bearer '+r.json()['access_token']}
        a=c.post('/api/analyze/message',headers=headers,json={'text':'Guaranteed returns! Act now and pay via UPI'})
        assert a.status_code==200 and a.json()['risk']=='HIGH'
        assert c.get('/api/analysis/history',headers=headers).status_code==200
    finally:
        with SessionLocal() as session:
            user=session.query(User).filter_by(email=email).first()
            if user:
                session.delete(user)
                session.commit()

def test_education_quiz_is_hidden_until_submit_and_progress_is_saved():
    c=TestClient(app)
    items=c.get('/api/education').json()
    assert len(items)==10
    detail=c.get('/api/education/guaranteed-returns').json()
    assert len(detail['quiz'])==3
    assert all('correct_index' not in question for question in detail['quiz'])
    email=f'quiz-user-{uuid4().hex}@example.com'
    account=c.post('/api/auth/register',json={'email':email,'name':'Quiz User','password':'StrongQuizPass!2026'})
    assert account.status_code==200
    headers={'Authorization':'Bearer '+account.json()['access_token']}
    try:
        result=c.post('/api/education/guaranteed-returns/quiz-attempt',headers=headers,json={'answers':[0,0,0]})
        assert result.status_code==200 and result.json()['total']==3
        progress=c.get('/api/education/progress',headers=headers).json()
        assert progress['completed_lessons']==1
        assert progress['quiz_attempts']==1
    finally:
        with SessionLocal() as session:
            user=session.query(User).filter_by(email=email).first()
            if user:
                session.delete(user)
                session.commit()

def test_upload_rejects_executable_and_reports_ocr_fallback(monkeypatch):
    from io import BytesIO
    from PIL import Image
    monkeypatch.delenv('OCR_PROVIDER',raising=False)
    c=TestClient(app)
    email=f'upload-user-{uuid4().hex}@example.com'
    account=c.post('/api/auth/register',json={'email':email,'name':'Upload User','password':'StrongUploadPass!2026'})
    headers={'Authorization':'Bearer '+account.json()['access_token']}
    try:
        rejected=c.post('/api/analyze/image',headers=headers,files={'file':('payload.exe',b'MZ\x00\x00','application/x-msdownload')})
        assert rejected.status_code==415
        image=Image.new('RGB',(8,8),'white');buffer=BytesIO();image.save(buffer,format='PNG')
        response=c.post('/api/analyze/image',headers=headers,files={'file':('..\\screen.png',buffer.getvalue(),'image/png')})
        assert response.status_code==200
        data=response.json()
        assert data['extraction_available'] is False
        assert 'paste' in data['message'].lower()
        assert data['filename']=='screen.png'
    finally:
        with SessionLocal() as session:
            user=session.query(User).filter_by(email=email).first()
            if user:
                session.delete(user)
                session.commit()
