from datetime import datetime, timedelta, timezone
import re
from uuid import uuid4
import os
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import create_engine, select, event
from sqlalchemy.orm import Session, sessionmaker
from app.document_extraction import extract_document, validate_upload, MAX_TEXT_CHARS
from app.url_safety import analyze_url, URLRejected
from app.models import Base, User, Analysis, AnalysisIndicator, Role, Quiz, QuizAttempt, EducationModule, OfficialVideo, UserProgress, GrievanceGuide, Notification, Feedback, AuditLog, UploadedDocument, user_roles
from app.education_content import LESSONS
from app.grievance_content import RIGHTS_GUIDES, GRIEVANCE_GUIDES
from app.localization import ANALYSIS_COPY as EXTRA_ANALYSIS_COPY, INDICATOR_LABELS as EXTRA_INDICATOR_LABELS, GUIDANCE as EXTRA_GUIDANCE
from app.platforms import router as platforms_router
from app.platforms import DATA_FILE as PLATFORM_DATA_FILE
import json
import logging
from app.ai import DEFAULT_GEMINI_MODEL, SAFE_FALLBACK, GeminiAssistant, enforce_safety

logger = logging.getLogger(__name__)

SECRET = os.getenv('JWT_SECRET', 'dev-only-change-this-secret-before-deployment')
APP_ENV = os.getenv('APP_ENV','development').lower()
if APP_ENV == 'production' and (SECRET == 'dev-only-change-this-secret-before-deployment' or len(SECRET)<32):
    raise RuntimeError('Set a unique JWT_SECRET of at least 32 characters before starting in production.')
DB_URL = os.getenv('DATABASE_URL', 'sqlite:///./rakshakai.db')
if DB_URL.startswith('postgres://'):
    DB_URL = 'postgresql://' + DB_URL[len('postgres://'):]
if APP_ENV == 'production' and DB_URL.startswith('sqlite'):
    raise RuntimeError('Use PostgreSQL for production; SQLite is supported for local demo use.')
engine = create_engine(DB_URL, connect_args={'check_same_thread': False} if DB_URL.startswith('sqlite') else {})
if DB_URL.startswith('sqlite'):
    @event.listens_for(engine,'connect')
    def enable_sqlite_foreign_keys(connection,record):
        cursor=connection.cursor();cursor.execute('PRAGMA foreign_keys=ON');cursor.close()
SessionLocal = sessionmaker(engine, expire_on_commit=False)
pwd = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth = OAuth2PasswordBearer(tokenUrl='/api/auth/login', auto_error=False)

app=FastAPI(title='RakshakAI API', version='0.1.0', description='Informational investor safety tools; no investment advice.')
app.include_router(platforms_router)
allowed_origins=['https://rakshakai-frontend-5117.getvoroa.com']+[item.strip() for item in os.getenv('FRONTEND_ORIGINS','http://localhost:3000,http://127.0.0.1:3000').split(',') if item.strip()]

@app.on_event('startup')
async def log_runtime_configuration():
    model=os.getenv('GEMINI_MODEL',DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
    logger.info('Backend ready: gemini_api_key_present=%s gemini_model=%s',bool(os.getenv('GEMINI_API_KEY','').strip()),model)

RATE_BUCKETS={}
@app.middleware('http')
async def secure_request_middleware(request:Request,call_next):
    length=request.headers.get('content-length')
    if length:
        try:
            if int(length)>12*1024*1024:
                return JSONResponse(status_code=413,content={'detail':'Request body is too large.','error':{'code':'request_too_large','message':'Request body is limited to 12 MB.'}})
        except ValueError:
            return JSONResponse(status_code=400,content={'detail':'Invalid Content-Length header.','error':{'code':'invalid_request','message':'Invalid request headers.'}})
    if request.method!='OPTIONS' and request.url.path not in ('/api/health','/openapi.json'):
        ip=request.client.host if request.client else 'unknown'
        key=(ip,'auth' if request.url.path.startswith('/api/auth/') else 'analysis' if '/analyze/' in request.url.path else 'general')
        now=__import__('time').monotonic(); window=60
        limit={'auth':12,'analysis':60,'general':150}[key[1]]
        hits=[t for t in RATE_BUCKETS.get(key,[]) if now-t<window]
        if len(hits)>=limit:
            return JSONResponse(status_code=429,headers={'Retry-After':'60'},content={'detail':'Too many requests. Please wait and try again.','error':{'code':'rate_limited','message':'Request rate limit exceeded.'}})
        hits.append(now);RATE_BUCKETS[key]=hits
        if len(RATE_BUCKETS)>10000:
            for expired in [k for k,v in RATE_BUCKETS.items() if not v or now-v[-1]>=window]: RATE_BUCKETS.pop(expired,None)
    try:
        response=await call_next(request)
    except Exception as exc:
        error_message=str(exc)[:500]
        api_key=os.getenv('GEMINI_API_KEY','').strip()
        if api_key: error_message=error_message.replace(api_key,'[REDACTED]')
        error_message=re.sub(r'AIza[0-9A-Za-z_-]{20,}','[REDACTED]',error_message)
        logger.error('Unhandled request exception method=%s path=%s type=%s message=%s',request.method,request.url.path,type(exc).__name__,error_message)
        response=JSONResponse(status_code=500,content={'detail':'An unexpected server error occurred.','error':{'code':'internal_error','message':'An unexpected server error occurred.'}})
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Permissions-Policy']='camera=(), microphone=(self), geolocation=()'
    if APP_ENV == 'production': response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
    if not request.url.path.startswith(('/docs','/redoc','/openapi.json')):
        response.headers['Content-Security-Policy']="default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    return response

@app.exception_handler(HTTPException)
async def structured_http_error(request:Request,exc:HTTPException):
    detail=exc.detail if isinstance(exc.detail,str) else 'The request could not be completed.'
    return JSONResponse(status_code=exc.status_code,headers=exc.headers,content={'detail':detail,'error':{'code':f'http_{exc.status_code}','message':detail}})

@app.exception_handler(Exception)
async def structured_unexpected_error(request:Request,exc:Exception):
    return JSONResponse(status_code=500,content={'detail':'An unexpected server error occurred.','error':{'code':'internal_error','message':'An unexpected server error occurred.'}})

from fastapi.exceptions import RequestValidationError
@app.exception_handler(RequestValidationError)
async def structured_validation_error(request:Request,exc:RequestValidationError):
    issues=[{'field':'.'.join(str(p) for p in item.get('loc',[]) if p!='body'),'message':item.get('msg','Invalid value'),'code':item.get('type','invalid')} for item in exc.errors()]
    return JSONResponse(status_code=422,content={'detail':'Request validation failed.','error':{'code':'validation_error','message':'Request validation failed.','issues':issues}})

def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()

def record_audit(session:Session,user_id:str|None,action:str,entity_type:str,entity_id:str|None=None,outcome:str='success'):
    # Audit events contain metadata only; never pass message text, passwords, tokens, or file contents.
    session.add(AuditLog(user_id=user_id,action=action,entity_type=entity_type,entity_id=entity_id,outcome=outcome))

def save_analysis(session:Session,user:User,kind:str,result:dict)->Analysis:
    row=Analysis(user_id=user.id,kind=kind,risk=result['risk'],summary=result.get('explanation',result.get('risk_phrase','Analysis completed.'))[:2000])
    session.add(row);session.flush()
    for indicator in result.get('indicators',[]):
        # Persist only the indicator category and title. Evidence can quote sensitive user text.
        session.add(AnalysisIndicator(analysis_id=row.id,code=str(indicator.get('code','unknown'))[:64],label=str(indicator.get('label','Pattern detected'))[:160],evidence=''))
    record_audit(session,user.id,'analysis.created','analysis',row.id)
    return row

def seed_content():
    with SessionLocal() as session:
        for name,description,permissions in [('user','Standard account',[]),('admin','Content and moderation administration',['content:write','feedback:read','audit:read'])]:
            if not session.scalar(select(Role).where(Role.name==name)):
                session.add(Role(name=name,description=description,permissions=permissions))
        session.flush()
        for lesson_data in LESSONS:
            module=session.scalar(select(EducationModule).where(EducationModule.slug==lesson_data['slug']))
            if module is None:
                content={key:value for key,value in lesson_data.items() if key not in ('slug','title','quiz')}
                module=EducationModule(slug=lesson_data['slug'],title=lesson_data['title'],content=content,active=True)
                session.add(module);session.flush()
            if not session.scalar(select(Quiz).where(Quiz.module_id==module.id)):
                session.add(Quiz(module_id=module.id,questions=lesson_data['quiz'],active=True))
        for guide in RIGHTS_GUIDES+GRIEVANCE_GUIDES:
            if not session.scalar(select(GrievanceGuide).where(GrievanceGuide.slug==guide['slug'])):
                session.add(GrievanceGuide(slug=guide['slug'],title=guide['title'],category=guide['category'],content=guide['content'],active=True))
        session.commit()

seed_content()
class Register(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1,max_length=80)
    password: str = Field(min_length=10,max_length=128)
    preferred_language: str = 'en'
    @field_validator('password')
    @classmethod
    def bcrypt_password_size(cls,value):
        if len(value.encode('utf-8'))>72: raise ValueError('Password must be at most 72 UTF-8 bytes.')
        return value
class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1,max_length=128)
    @field_validator('password')
    @classmethod
    def login_password_size(cls,value):
        if len(value.encode('utf-8'))>72: raise ValueError('Password input is too long.')
        return value
SUPPORTED_LANGUAGES={'en','hi','kn','ta','te','mr','bn','ml','gu','pa'}
class MessageIn(BaseModel): text: str = Field(min_length=3,max_length=12000); channel: Literal['message','whatsapp','telegram','document','url'] = 'message'; language: str | None = Field(default=None,max_length=5)
class AssistantTurn(BaseModel): role: Literal['user','assistant']; content: str = Field(min_length=1,max_length=2000)
class AssistantChatInput(BaseModel): message: str = Field(min_length=1,max_length=2000); language: str = Field(default='en',min_length=2,max_length=5); history: list[AssistantTurn] = Field(default_factory=list,max_length=10)
class LanguagePreference(BaseModel): language: str = Field(min_length=2,max_length=5)
class QuizAttemptInput(BaseModel):
    answers: list[int] = Field(min_length=3,max_length=3)
    @field_validator('answers')
    @classmethod
    def quiz_answers_in_range(cls, answers):
        if any(answer < 0 or answer > 10 for answer in answers):
            raise ValueError('Quiz answer selections must be valid option indexes.')
        return answers
class FeedbackInput(BaseModel): category: str = Field(min_length=2,max_length=48); message: str = Field(min_length=3,max_length=2000)
class NotificationReadInput(BaseModel): read: bool = True
class GuideUpdate(BaseModel):
    title: str = Field(min_length=3,max_length=180)
    category: str = Field(min_length=2,max_length=64)
    content: dict
    official_url: str|None = Field(default=None,max_length=500)
    @field_validator('official_url')
    @classmethod
    def validate_official_url(cls,value):
        if value is not None and (not value.startswith('https://') or any(ch.isspace() for ch in value)):
            raise ValueError('Official links must use HTTPS.')
        return value
    @field_validator('content')
    @classmethod
    def bound_guide_content(cls,value):
        if len(str(value))>20000: raise ValueError('Guidance content exceeds the size limit.')
        return value
class OfficialVideoInput(BaseModel):
    title: str = Field(min_length=2,max_length=180)
    description: str = Field(default='',max_length=800)
    youtube_url: str = Field(min_length=12,max_length=500)
    thumbnail: str|None = Field(default=None,max_length=500)
    language: str = Field(min_length=2,max_length=24)
    authority: str = Field(min_length=2,max_length=160)
    topic: str = Field(min_length=2,max_length=64)
    is_official: bool = False
    @field_validator('youtube_url')
    @classmethod
    def official_youtube_host(cls,value):
        from urllib.parse import urlparse
        parsed=urlparse(value)
        if parsed.scheme!='https' or parsed.hostname not in ('youtube.com','www.youtube.com','youtu.be','m.youtube.com'):
            raise ValueError('Use an HTTPS link from youtube.com or youtu.be.')
        if parsed.hostname in ('youtube.com','www.youtube.com','m.youtube.com') and not (parsed.path=='/watch' and parsed.query or parsed.path.startswith(('/embed/','/shorts/'))):
            raise ValueError('Enter a valid YouTube video link.')
        if parsed.hostname=='youtu.be' and not parsed.path.strip('/'):
            raise ValueError('Enter a valid YouTube video link.')
        return value

class OfficialPlatformInput(BaseModel):
    id: str = Field(min_length=2,max_length=80)
    name: str = Field(min_length=2,max_length=160)
    category: str = Field(min_length=2,max_length=100)
    organization: str = Field(min_length=2,max_length=180)
    officialWebsite: str = Field(min_length=12,max_length=500)
    officialAppUrl: str = Field(default='',max_length=500)
    registrationNumber: str = Field(default='',max_length=120)
    registrationType: str = Field(default='',max_length=120)
    authority: str = Field(default='',max_length=160)
    description: str = Field(min_length=10,max_length=1200)
    languages: list[str] = Field(default_factory=list,max_length=20)
    lastVerified: str = Field(min_length=10,max_length=10)
    verificationSource: str = Field(min_length=8,max_length=500)
    verificationStatus: Literal['MATCHED','INCOMPLETE','INCONSISTENT','UNAVAILABLE'] = 'INCOMPLETE'
    isOfficial: bool = False
    @field_validator('officialWebsite','officialAppUrl')
    @classmethod
    def platform_https(cls,value):
        if value and (not value.startswith('https://') or any(ch.isspace() for ch in value)):
            raise ValueError('Platform links must use HTTPS.')
        return value

def current_user(token: str|None=Depends(oauth), s: Session=Depends(db)):
    if not token: raise HTTPException(401,'Sign in to view your private history')
    try: uid=jwt.decode(token,SECRET,algorithms=['HS256'])['sub']
    except (JWTError,KeyError): raise HTTPException(401,'Session expired. Please sign in again.')
    user=s.get(User,uid)
    if not user: raise HTTPException(401,'User session was not found')
    return user

@app.post('/api/assistant/chat')
async def assistant_chat(data:AssistantChatInput,u=Depends(current_user)):
    language=data.language or u.preferred_language
    if language not in SUPPORTED_LANGUAGES: raise HTTPException(422,'Unsupported language')
    assistant=GeminiAssistant()
    try:
        answer=await assistant.answer(data.message.strip(),language,[turn.model_dump() for turn in data.history])
    except Exception as exc:
        # Keep the chat response shape stable even if an unexpected provider error escapes.
        logger.error('Assistant provider request failed type=%s',type(exc).__name__)
        answer=SAFE_FALLBACK
        assistant.used_fallback=True
        assistant.failure_category='server'
    safe=enforce_safety({'answer':answer})
    return {'answer':safe['answer'],'language':language,'provider':'fallback' if assistant.used_fallback else 'gemini','provider_status':assistant.failure_category or 'ok','disclaimer':'RakshakAI provides general information, not personalized financial, legal, or tax advice. Do not share OTPs, PINs, passwords, or bank credentials.'}

def optional_analysis_user(token: str|None=Depends(oauth), s: Session=Depends(db)):
    """Use a valid session for history; let analysis continue without one."""
    if not token: return None
    try: uid=jwt.decode(token,SECRET,algorithms=['HS256'])['sub']
    except ExpiredSignatureError: return None
    except (JWTError,KeyError): raise HTTPException(401,'Invalid session. Please sign in again.')
    user=s.get(User,uid)
    if not user: raise HTTPException(401,'User session was not found')
    return user

def token_for(u): return jwt.encode({'sub':u.id,'exp':datetime.now(timezone.utc)+timedelta(minutes=int(__import__('os').getenv('ACCESS_TOKEN_MINUTES','30')))},SECRET,algorithm='HS256')

INDICATORS=[
 ('guaranteed_return',r'guaranteed|risk[- ]?free|assured return|100% profit|fixed returns?'),
 ('fake_investment_group',r'investment group|trading group|vip signals?|premium signals?|investment club|double your money'),
 ('urgency',r'act now|limited time|today only|last chance|urgent|before midnight|only \d+ (?:hours?|minutes?)'),
 ('payment_request',r'pay|transfer|upi|deposit|send money|processing fee|wallet address|send crypto'),
 ('credential_request',r'otp|password|pin|credential|bank details|recovery phrase|seed phrase|private key'),
 ('impersonation',r'sebi|rbi|government|official|authorized|advisor|support team|account manager|police|tax department'),
 ('fake_authority',r'(?:official|verified|authorized)\s+(?:telegram\s+)?(?:admin|advisor|agent|support|representative)|(?:government|regulator|police)\s+(?:approved|certified|agent)'),
 ('referral_pressure',r'refer|commission|invite friends|bonus|referral|recruit'),
 ('suspicious_link',r'https?://|www\.'),
 ('fear_tactic',r'account.{0,20}(blocked|frozen)|legal action|arrest|prosecuted')
]
ANALYSIS_COPY={
 'en': {'explanation':'{count} risk indicator(s) were detected. These signals are not proof of fraud; verify independently.','steps':['Contact the organization using contact details from its official website or app.','Do not use links or phone numbers in the message.','Never share an OTP, password, PIN, or remote access.','Pause before sending money and discuss with someone you trust.'],'disclaimer':'Risk indicates patterns detected in the submitted content. It is not a legal finding or a guarantee.'},
 'hi': {'explanation':'जोखिम के {count} संकेत मिले। ये संकेत धोखाधड़ी का प्रमाण नहीं हैं; स्वतंत्र रूप से सत्यापित करें।','steps':['संगठन की आधिकारिक वेबसाइट या ऐप पर दिए संपर्क विवरण से संपर्क करें।','संदेश में दिए लिंक या फ़ोन नंबर का उपयोग न करें।','OTP, पासवर्ड, PIN या रिमोट एक्सेस कभी साझा न करें।','पैसे भेजने से पहले रुकें और किसी भरोसेमंद व्यक्ति से बात करें।'],'disclaimer':'जोखिम का अर्थ है कि दी गई सामग्री में कुछ पैटर्न मिले। यह कानूनी निष्कर्ष या गारंटी नहीं है।'},
 'kn': {'explanation':'{count} ಅಪಾಯದ ಸೂಚನೆಗಳು ಪತ್ತೆಯಾಗಿವೆ. ಇವು ವಂಚನೆಯ ಪುರಾವೆಯಲ್ಲ; ಸ್ವತಂತ್ರವಾಗಿ ಪರಿಶೀಲಿಸಿ.','steps':['ಸಂಸ್ಥೆಯ ಅಧಿಕೃತ ವೆಬ್‌ಸೈಟ್ ಅಥವಾ ಆ್ಯಪ್‌ನ ಸಂಪರ್ಕ ವಿವರಗಳನ್ನು ಬಳಸಿ ಸಂಪರ್ಕಿಸಿ.','ಸಂದೇಶದಲ್ಲಿರುವ ಲಿಂಕ್ ಅಥವಾ ಫೋನ್ ಸಂಖ್ಯೆಯನ್ನು ಬಳಸಬೇಡಿ.','OTP, ಪಾಸ್‌ವರ್ಡ್, PIN ಅಥವಾ ರಿಮೋಟ್ ಪ್ರವೇಶವನ್ನು ಎಂದಿಗೂ ಹಂಚಿಕೊಳ್ಳಬೇಡಿ.','ಹಣ ಕಳುಹಿಸುವ ಮೊದಲು ವಿರಾಮ ತೆಗೆದುಕೊಂಡು ನಂಬಿಕಸ್ತ ವ್ಯಕ್ತಿಯೊಂದಿಗೆ ಚರ್ಚಿಸಿ.'],'disclaimer':'ಅಪಾಯ ಎಂದರೆ ಸಲ್ಲಿಸಿದ ವಿಷಯದಲ್ಲಿ ಕೆಲವು ಮಾದರಿಗಳು ಕಂಡಿವೆ. ಇದು ಕಾನೂನು ನಿರ್ಧಾರ ಅಥವಾ ಖಾತರಿಯಲ್ಲ.'}
}
INDICATOR_LABELS={
 'hi': {'guaranteed_return':'गारंटीकृत रिटर्न का दावा','urgency':'जल्दबाज़ी का दबाव','payment_request':'भुगतान का अनुरोध','credential_request':'गोपनीय जानकारी का अनुरोध','impersonation':'संस्था की पहचान का दावा','referral_pressure':'रेफ़रल का दबाव','suspicious_link':'संदिग्ध लिंक','fear_tactic':'डराने की रणनीति'},
 'kn': {'guaranteed_return':'ಖಾತರಿಯ ಲಾಭದ ಭರವಸೆ','urgency':'ತುರ್ತು ಒತ್ತಡ','payment_request':'ಪಾವತಿ ವಿನಂತಿ','credential_request':'ಗೌಪ್ಯ ಮಾಹಿತಿಯ ವಿನಂತಿ','impersonation':'ಸಂಸ್ಥೆಯ ಸೋಗು ಹಾಕುವಿಕೆ','referral_pressure':'ರೆಫರಲ್ ಒತ್ತಡ','suspicious_link':'ಅನುಮಾನಾಸ್ಪದ ಲಿಂಕ್','fear_tactic':'ಭಯ ಹುಟ್ಟಿಸುವ ತಂತ್ರ'}
}
GUIDANCE={
 'en': {
  'guaranteed_return':('Unrealistic return promise','The message promises guaranteed, risk-free, or unusually high returns. No investment return is guaranteed.','Do not pay or invest based on the promise. Check the offer and the entity on official regulator sources.'),
  'urgency':('Pressure to act quickly','A deadline or urgent wording can stop you from checking the claim carefully.','Pause. Contact the organization using details from its official website or app.'),
  'payment_request':('Request to send money','The message asks for a payment, transfer, deposit, or fee. An upfront fee can be used to collect money.','Do not send money yet. Independently verify the fee and recipient through the organization’s official channel.'),
  'credential_request':('Request for sensitive credentials','The message refers to an OTP, password, PIN, or bank details. These details can give someone access to your account.','Do not share the code or credentials. If you already shared them, contact your bank using its official number immediately.'),
  'impersonation':('Claim to represent an authority or organization','The message invokes a regulator, government body, company, or adviser. That claim alone does not verify who sent it.','Find the organization’s official contact details yourself and ask whether the message is genuine.'),
  'referral_pressure':('Pressure to recruit others','A bonus or commission tied to inviting others may shift the focus from a verifiable product to recruitment.','Do not recruit or pay to qualify. Ask for written terms and independently verify the business.'),
  'suspicious_link':('A link is included','A link in an unsolicited message may lead to a lookalike page. This check does not open or verify the destination.','Do not open the message link. Type the known official website address yourself.'),
  'fear_tactic':('Threatening or frightening language','Threats about a blocked account, arrest, or legal action can pressure you into acting without checking.','Do not call numbers in the message or transfer money. Contact the named organization through its official channel.'),
  'no_https':('The URL does not use HTTPS','The address uses an unencrypted connection. This alone does not determine whether the site is fraudulent.','Do not enter personal or payment details. Find the organization’s official HTTPS address independently.'),
  'invalid_domain':('Unusual domain structure','The URL does not have a typical registered domain structure.','Do not enter information. Verify the address against the organization’s official website.'),
  'keyword_domain':('Authority or finance terms in the domain','The domain includes words associated with finance or authorities. A word in a domain does not prove affiliation.','Check the exact domain through the organization’s official website or regulator directory.'),
  'unusual_domain':('Unusual domain formatting','The domain has a long name or several hyphens, which can make impersonation harder to spot.','Compare every part of the domain with the known official address before proceeding.'),
 },
 'hi': {
  'guaranteed_return':('असामान्य लाभ का वादा','संदेश निश्चित, जोखिम-मुक्त या बहुत अधिक लाभ का वादा करता है। किसी निवेश का लाभ निश्चित नहीं होता।','इस वादे के आधार पर पैसा न भेजें। आधिकारिक नियामक स्रोतों पर प्रस्ताव और संस्था जाँचें।'),
  'urgency':('जल्दी कार्रवाई का दबाव','समय-सीमा या जल्दबाज़ी की भाषा आपको दावे की जाँच से रोक सकती है।','रुकें। संस्था की आधिकारिक वेबसाइट या ऐप पर दिए संपर्क विवरण से पुष्टि करें।'),
  'payment_request':('पैसे भेजने का अनुरोध','संदेश भुगतान, ट्रांसफ़र, जमा या शुल्क माँगता है। अग्रिम शुल्क से पैसे वसूले जा सकते हैं।','अभी पैसे न भेजें। संस्था के आधिकारिक माध्यम से शुल्क और प्राप्तकर्ता की स्वतंत्र पुष्टि करें।'),
  'credential_request':('गोपनीय जानकारी माँगी गई','संदेश में OTP, पासवर्ड, PIN या बैंक विवरण माँगे गए हैं। इनसे खाते तक पहुँच मिल सकती है।','कोड या जानकारी साझा न करें। यदि साझा कर चुके हैं, तो तुरंत बैंक के आधिकारिक नंबर पर संपर्क करें।'),
  'impersonation':('संस्था या प्राधिकरण का प्रतिनिधि होने का दावा','संदेश नियामक, सरकारी निकाय, कंपनी या सलाहकार का नाम लेता है। केवल दावा करने से भेजने वाले की पहचान सत्यापित नहीं होती।','संस्था का आधिकारिक संपर्क स्वयं खोजें और पूछें कि संदेश असली है या नहीं।'),
  'referral_pressure':('दूसरों को जोड़ने का दबाव','लोगों को जोड़ने पर मिलने वाला बोनस सत्यापित उत्पाद के बजाय भर्ती पर ध्यान दिला सकता है।','योग्य बनने के लिए लोगों को न जोड़ें और भुगतान न करें। लिखित शर्तें लें और व्यवसाय की स्वतंत्र जाँच करें।'),
  'suspicious_link':('संदेश में लिंक दिया गया है','अनचाहे संदेश का लिंक नकली वेबसाइट पर ले जा सकता है। यह जाँच लिंक को खोलती या सत्यापित नहीं करती।','संदेश का लिंक न खोलें। आधिकारिक वेबसाइट का पता स्वयं टाइप करें।'),
  'fear_tactic':('धमकी या डराने वाली भाषा','खाता बंद होने, गिरफ्तारी या कानूनी कार्रवाई की धमकी बिना जाँच जल्दबाज़ी करा सकती है।','संदेश में दिए नंबर पर कॉल या भुगतान न करें। संस्था से उसके आधिकारिक माध्यम पर संपर्क करें।'),
  'no_https':('URL में HTTPS नहीं है','पता एन्क्रिप्टेड कनेक्शन का उपयोग नहीं करता। इससे अकेले धोखाधड़ी साबित नहीं होती।','व्यक्तिगत या भुगतान विवरण न डालें। संस्था का आधिकारिक HTTPS पता स्वयं खोजें।'),
  'invalid_domain':('डोमेन संरचना असामान्य है','URL में सामान्य पंजीकृत डोमेन संरचना नहीं दिखती।','जानकारी न डालें। संस्था की आधिकारिक वेबसाइट से पते की पुष्टि करें।'),
  'keyword_domain':('डोमेन में वित्त या प्राधिकरण से जुड़े शब्द हैं','डोमेन में वित्त या प्राधिकरण से जुड़े शब्द हैं। केवल ऐसा शब्द संस्था से संबंध सिद्ध नहीं करता।','संस्था की आधिकारिक वेबसाइट या नियामक सूची पर पूरा डोमेन जाँचें।'),
  'unusual_domain':('डोमेन का प्रारूप असामान्य है','डोमेन लंबा है या उसमें कई हाइफ़न हैं, जिससे नकली पहचान पकड़ना कठिन हो सकता है।','आगे बढ़ने से पहले डोमेन की तुलना आधिकारिक पते से करें।'),
 },
 'kn': {
  'guaranteed_return':('ಅಸಾಮಾನ್ಯ ಲಾಭದ ಭರವಸೆ','ಸಂದೇಶವು ಖಚಿತ, ಅಪಾಯವಿಲ್ಲದ ಅಥವಾ ಅತಿಹೆಚ್ಚಿನ ಲಾಭವನ್ನು ಭರವಸೆ ನೀಡುತ್ತದೆ. ಯಾವುದೇ ಹೂಡಿಕೆಯ ಲಾಭ ಖಚಿತವಲ್ಲ.','ಈ ಭರವಸೆಯ ಆಧಾರದಲ್ಲಿ ಹಣ ಹೂಡಬೇಡಿ. ಅಧಿಕೃತ ನಿಯಂತ್ರಕ ಮೂಲಗಳಲ್ಲಿ ಕೊಡುಗೆ ಮತ್ತು ಸಂಸ್ಥೆಯನ್ನು ಪರಿಶೀಲಿಸಿ.'),
  'urgency':('ತಕ್ಷಣ ಕ್ರಮ ಕೈಗೊಳ್ಳುವ ಒತ್ತಡ','ಗಡುವು ಅಥವಾ ತುರ್ತು ಪದಗಳು ವಿಷಯವನ್ನು ಪರಿಶೀಲಿಸದಂತೆ ತಡೆಯಬಹುದು.','ವಿರಾಮ ತೆಗೆದುಕೊಳ್ಳಿ. ಸಂಸ್ಥೆಯ ಅಧಿಕೃತ ವೆಬ್‌ಸೈಟ್ ಅಥವಾ ಆ್ಯಪ್‌ನ ಸಂಪರ್ಕ ವಿವರಗಳಿಂದ ದೃಢೀಕರಿಸಿ.'),
  'payment_request':('ಹಣ ಕಳುಹಿಸುವ ವಿನಂತಿ','ಸಂದೇಶವು ಪಾವತಿ, ವರ್ಗಾವಣೆ, ಠೇವಣಿ ಅಥವಾ ಶುಲ್ಕ ಕೇಳುತ್ತದೆ. ಮುಂಗಡ ಶುಲ್ಕದ ಮೂಲಕ ಹಣ ವಸೂಲಿ ಮಾಡಬಹುದು.','ಈಗ ಹಣ ಕಳುಹಿಸಬೇಡಿ. ಅಧಿಕೃತ ಮಾರ್ಗದ ಮೂಲಕ ಶುಲ್ಕ ಮತ್ತು ಸ್ವೀಕರಿಸುವವರನ್ನು ಸ್ವತಂತ್ರವಾಗಿ ಪರಿಶೀಲಿಸಿ.'),
  'credential_request':('ಗೌಪ್ಯ ರುಜುವಾತುಗಳ ವಿನಂತಿ','ಸಂದೇಶವು OTP, ಪಾಸ್‌ವರ್ಡ್, PIN ಅಥವಾ ಬ್ಯಾಂಕ್ ವಿವರಗಳನ್ನು ಕೇಳುತ್ತದೆ. ಇವು ಖಾತೆಗೆ ಪ್ರವೇಶ ನೀಡಬಹುದು.','ಕೋಡ್ ಅಥವಾ ರುಜುವಾತುಗಳನ್ನು ಹಂಚಿಕೊಳ್ಳಬೇಡಿ. ಈಗಾಗಲೇ ಹಂಚಿದ್ದರೆ ಬ್ಯಾಂಕಿನ ಅಧಿಕೃತ ಸಂಖ್ಯೆಗೆ ತಕ್ಷಣ ಕರೆ ಮಾಡಿ.'),
  'impersonation':('ಸಂಸ್ಥೆ ಅಥವಾ ಪ್ರಾಧಿಕಾರದ ಪ್ರತಿನಿಧಿಯೆಂಬ ಹೇಳಿಕೆ','ಸಂದೇಶವು ನಿಯಂತ್ರಕ, ಸರ್ಕಾರಿ ಸಂಸ್ಥೆ, ಕಂಪನಿ ಅಥವಾ ಸಲಹೆಗಾರರ ಹೆಸರನ್ನು ಹೇಳುತ್ತದೆ. ಈ ಹೇಳಿಕೆಯೊಂದರಿಂದ ಕಳುಹಿಸಿದವರ ಗುರುತು ದೃಢವಾಗುವುದಿಲ್ಲ.','ಸಂಸ್ಥೆಯ ಅಧಿಕೃತ ಸಂಪರ್ಕ ವಿವರಗಳನ್ನು ನೀವೇ ಹುಡುಕಿ, ಸಂದೇಶ ನಿಜವೇ ಎಂದು ವಿಚಾರಿಸಿ.'),
  'referral_pressure':('ಇತರರನ್ನು ಸೇರಿಸುವ ಒತ್ತಡ','ಜನರನ್ನು ಆಹ್ವಾನಿಸಿದರೆ ಸಿಗುವ ಬೋನಸ್ ಪರಿಶೀಲಿಸಬಹುದಾದ ಉತ್ಪನ್ನಕ್ಕಿಂತ ನೇಮಕಾತಿಗೆ ಗಮನ ಹರಿಸಬಹುದು.','ಅರ್ಹತೆಗಾಗಿ ಯಾರನ್ನೂ ಸೇರಿಸಬೇಡಿ ಅಥವಾ ಹಣ ಪಾವತಿಸಬೇಡಿ. ಲಿಖಿತ ಷರತ್ತುಗಳನ್ನು ಪಡೆದು ವ್ಯವಹಾರವನ್ನು ಪರಿಶೀಲಿಸಿ.'),
  'suspicious_link':('ಸಂದೇಶದಲ್ಲಿ ಲಿಂಕ್ ಇದೆ','ಅಪೇಕ್ಷಿಸದ ಸಂದೇಶದ ಲಿಂಕ್ ನಕಲಿ ವೆಬ್‌ಸೈಟ್‌ಗೆ ಕರೆದೊಯ್ಯಬಹುದು. ಈ ಪರಿಶೀಲನೆ ಗಮ್ಯಸ್ಥಾನವನ್ನು ತೆರೆಯುವುದಿಲ್ಲ ಅಥವಾ ದೃಢೀಕರಿಸುವುದಿಲ್ಲ.','ಸಂದೇಶದ ಲಿಂಕ್ ತೆರೆಯಬೇಡಿ. ಅಧಿಕೃತ ವೆಬ್‌ಸೈಟ್ ವಿಳಾಸವನ್ನು ನೀವೇ ಟೈಪ್ ಮಾಡಿ.'),
  'fear_tactic':('ಬೆದರಿಕೆ ಅಥವಾ ಭಯ ಹುಟ್ಟಿಸುವ ಭಾಷೆ','ಖಾತೆ ನಿರ್ಬಂಧ, ಬಂಧನ ಅಥವಾ ಕಾನೂನು ಕ್ರಮದ ಬೆದರಿಕೆ ಪರಿಶೀಲಿಸದೆ ಕ್ರಮ ಕೈಗೊಳ್ಳುವಂತೆ ಮಾಡಬಹುದು.','ಸಂದೇಶದಲ್ಲಿನ ಸಂಖ್ಯೆಗೆ ಕರೆ ಮಾಡಬೇಡಿ ಅಥವಾ ಹಣ ಕಳುಹಿಸಬೇಡಿ. ಅಧಿಕೃತ ಮಾರ್ಗದಲ್ಲಿ ಸಂಸ್ಥೆಯನ್ನು ಸಂಪರ್ಕಿಸಿ.'),
  'no_https':('URL ನಲ್ಲಿ HTTPS ಇಲ್ಲ','ವಿಳಾಸವು ಎನ್‌ಕ್ರಿಪ್ಟ್ ಮಾಡಿದ ಸಂಪರ್ಕವನ್ನು ಬಳಸುವುದಿಲ್ಲ. ಇದೊಂದರಿಂದ ವಂಚನೆ ಸಾಬೀತಾಗುವುದಿಲ್ಲ.','ವೈಯಕ್ತಿಕ ಅಥವಾ ಪಾವತಿ ವಿವರಗಳನ್ನು ನಮೂದಿಸಬೇಡಿ. ಸಂಸ್ಥೆಯ ಅಧಿಕೃತ HTTPS ವಿಳಾಸವನ್ನು ನೀವೇ ಹುಡುಕಿ.'),
  'invalid_domain':('ಡೊಮೇನ್ ರಚನೆ ಅಸಾಮಾನ್ಯವಾಗಿದೆ','URL ನಲ್ಲಿ ಸಾಮಾನ್ಯ ನೋಂದಾಯಿತ ಡೊಮೇನ್ ರಚನೆ ಕಾಣುತ್ತಿಲ್ಲ.','ಮಾಹಿತಿ ನಮೂದಿಸಬೇಡಿ. ಸಂಸ್ಥೆಯ ಅಧಿಕೃತ ವೆಬ್‌ಸೈಟ್‌ನಲ್ಲಿ ವಿಳಾಸವನ್ನು ಪರಿಶೀಲಿಸಿ.'),
  'keyword_domain':('ಡೊಮೇನ್‌ನಲ್ಲಿ ಹಣಕಾಸು ಅಥವಾ ಪ್ರಾಧಿಕಾರದ ಪದಗಳಿವೆ','ಡೊಮೇನ್‌ನಲ್ಲಿ ಹಣಕಾಸು ಅಥವಾ ಪ್ರಾಧಿಕಾರಕ್ಕೆ ಸಂಬಂಧಿಸಿದ ಪದಗಳಿವೆ. ಪದವೊಂದರಿಂದ ಸಂಬಂಧ ದೃಢವಾಗುವುದಿಲ್ಲ.','ಸಂಸ್ಥೆಯ ಅಧಿಕೃತ ವೆಬ್‌ಸೈಟ್ ಅಥವಾ ನಿಯಂತ್ರಕ ಪಟ್ಟಿಯಲ್ಲಿ ಪೂರ್ಣ ಡೊಮೇನ್ ಪರಿಶೀಲಿಸಿ.'),
  'unusual_domain':('ಡೊಮೇನ್ ವಿನ್ಯಾಸ ಅಸಾಮಾನ್ಯವಾಗಿದೆ','ಡೊಮೇನ್ ಉದ್ದವಾಗಿದೆ ಅಥವಾ ಹಲವು ಹೈಫನ್‌ಗಳನ್ನು ಹೊಂದಿದೆ; ಇದರಿಂದ ಸೋಗು ಗುರುತಿಸುವುದು ಕಷ್ಟವಾಗಬಹುದು.','ಮುಂದುವರಿಯುವ ಮೊದಲು ಡೊಮೇನ್ ಅನ್ನು ಅಧಿಕೃತ ವಿಳಾಸದೊಂದಿಗೆ ಹೋಲಿಸಿ.'),
 }
}

ANALYSIS_COPY.update(EXTRA_ANALYSIS_COPY)
INDICATOR_LABELS.update(EXTRA_INDICATOR_LABELS)
GUIDANCE.update(EXTRA_GUIDANCE)

def build_findings(indicators, language):
    guide=GUIDANCE.get(language,GUIDANCE['en'])
    findings=[]
    for indicator in indicators:
        copy=guide.get(indicator['code']) or (indicator['label'],'This pattern may need closer verification.','Pause and verify independently through an official source.')
        findings.append({'code':indicator['code'],'title':copy[0],'reason':copy[1],'evidence':indicator['evidence'],'recommended_action':copy[2]})
    return findings

def analyze_text(text, language='en'):
    if language not in SUPPORTED_LANGUAGES: raise HTTPException(422,'Unsupported language')
    found=[]
    for key,pattern in INDICATORS:
        m=re.search(pattern,text,re.I)
        if m: found.append({'code':key,'label':INDICATOR_LABELS.get(language,{}).get(key,key.replace('_',' ').title()),'evidence':text[max(0,m.start()-35):min(len(text),m.end()+45)].strip(),'start':m.start(),'end':m.end()})
    risk='HIGH' if len(found)>=3 else 'MODERATE' if len(found)>=1 else 'LOW'
    # Risk codes stay canonical for downstream logic; only explanatory copy is localized.
    copy=ANALYSIS_COPY.get(language,ANALYSIS_COPY['en'])
    findings=build_findings(found,language)
    next_steps=list(dict.fromkeys(item['recommended_action'] for item in findings)) if findings else copy['steps']
    return {'language':language,'risk':risk,'indicators':found,'findings':findings,'problem_summary':copy['explanation'].format(count=len(found)),'explanation':copy['explanation'].format(count=len(found)),'next_steps':next_steps,'verification_steps':next_steps,'safe_next_actions':next_steps[:2],'disclaimer':copy['disclaimer']}

@app.get('/api/health')
def health(): return {'status':'ok','mode':'demo','raw_upload_retention':'none','gemini':{'configured':bool(os.getenv('GEMINI_API_KEY','').strip()),'model':os.getenv('GEMINI_MODEL',DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL}}
@app.get('/')
def api_home(): return {'service':'RakshakAI API','status':'ok','frontend':'http://localhost:3000','docs':'/docs','health':'/api/health'}
@app.post('/api/auth/register')
def register(data:Register,s:Session=Depends(db)):
    if data.preferred_language not in SUPPORTED_LANGUAGES: raise HTTPException(422,'Unsupported language')
    if s.scalar(select(User).where(User.email==data.email.lower())): raise HTTPException(409,'An account with this email already exists')
    u=User(email=data.email.lower(),name=data.name,password_hash=pwd.hash(data.password),preferred_language=data.preferred_language); s.add(u); s.flush()
    role=s.scalar(select(Role).where(Role.name=='user'))
    if role: s.execute(user_roles.insert().values(user_id=u.id,role_id=role.id))
    record_audit(s,u.id,'auth.register','user',u.id);s.commit();s.refresh(u)
    return {'access_token':token_for(u),'token_type':'bearer','user':{'id':u.id,'email':u.email,'name':u.name,'role':u.role}}
@app.post('/api/auth/login')
def login(data:Login,s:Session=Depends(db)):
    u=s.scalar(select(User).where(User.email==data.email.lower()))
    if not u or not pwd.verify(data.password,u.password_hash): raise HTTPException(401,'Email or password was not recognized')
    record_audit(s,u.id,'auth.login','user',u.id);s.commit()
    return {'access_token':token_for(u),'token_type':'bearer','user':{'id':u.id,'email':u.email,'name':u.name,'role':u.role}}
@app.post('/api/auth/logout')
def logout(): return {'message':'Signed out. Remove the session token from this device.'}
@app.get('/api/users/me')
def me(u=Depends(current_user)): return {'id':u.id,'email':u.email,'name':u.name,'role':u.role,'preferred_language':u.preferred_language}
@app.patch('/api/users/me/language')
def update_language(data:LanguagePreference,u=Depends(current_user),s:Session=Depends(db)):
    if data.language not in SUPPORTED_LANGUAGES: raise HTTPException(422,'Unsupported language')
    u.preferred_language=data.language; s.commit(); return {'preferred_language':u.preferred_language}
@app.post('/api/analyze/message')
def message(data:MessageIn,u=Depends(current_user),s:Session=Depends(db)):
    language=data.language or u.preferred_language
    if language not in SUPPORTED_LANGUAGES: raise HTTPException(422,'Unsupported language')
    result=analyze_text(data.text,language)
    a=save_analysis(s,u,data.channel,result); s.commit(); s.refresh(a)
    return {'id':a.id,**result,'history_saved':True,'session_valid':True,'created_at':a.created_at.isoformat()}
@app.post('/api/analyze/image')
async def image(file:UploadFile=File(...),language:str|None=Query(None),u=Depends(current_user)):
    language=language or u.preferred_language
    if language not in SUPPORTED_LANGUAGES: raise HTTPException(422,'Unsupported language')
    try:
        return await _process_uploaded_document(file,language,u,images_only=True)
    finally:
        await file.close()
@app.post('/api/analyze/document')
async def document(file:UploadFile=File(...),language:str|None=Query(None),u=Depends(current_user)):
    language=language or u.preferred_language
    if language not in SUPPORTED_LANGUAGES: raise HTTPException(422,'Unsupported language')
    try:
        return await _process_uploaded_document(file,language,u)
    finally:
        await file.close()

async def _process_uploaded_document(file:UploadFile,language:str,u,images_only:bool=False):
    data=await file.read(10*1024*1024+1)
    try:
        content_type,safe_name=validate_upload(data,file.content_type or '',file.filename)
    except OverflowError as exc:
        raise HTTPException(413,str(exc))
    except ValueError as exc:
        raise HTTPException(415 if 'Supported files' in str(exc) else 422,str(exc))
    if images_only and not content_type.startswith('image/'):
        raise HTTPException(415,'Screenshot analysis accepts PNG, JPG, JPEG, and WEBP images.')
    try:
        extracted_text,method=await extract_document(data,content_type)
    except RuntimeError:
        return {'filename':safe_name,'language':language,'extracted_text':'','extraction_available':False,'history_saved':False,'session_valid':bool(u),'message':'Text extraction is unavailable. Configure local Tesseract OCR or paste the message text manually. The upload was discarded.','risk':'UNKNOWN'}
    except ImportError:
        return {'filename':safe_name,'language':language,'extracted_text':'','extraction_available':False,'history_saved':False,'session_valid':bool(u),'message':'The extraction provider is not installed. Paste the text manually to continue. The upload was discarded.','risk':'UNKNOWN'}
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    except Exception:
        return {'filename':safe_name,'language':language,'extracted_text':'','extraction_available':False,'history_saved':False,'session_valid':bool(u),'message':'Text extraction failed. Paste the visible text manually to continue. The upload was discarded.','risk':'UNKNOWN'}
    # Normalize extracted text, remove NUL/control characters, then cap what is analyzed.
    extracted_text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',' ',extracted_text)
    extracted_text=re.sub(r'[ \t]+',' ',extracted_text).strip()[:MAX_TEXT_CHARS]
    if len(extracted_text)<3:
        return {'filename':safe_name,'language':language,'extracted_text':extracted_text,'extraction_available':True,'history_saved':False,'session_valid':bool(u),'extraction_method':method,'risk':'UNKNOWN','indicators':[],'findings':[],'explanation':'No readable text was extracted. Paste the message text manually to continue.','verification_steps':[],'safe_next_actions':[],'disclaimer':'OCR and document extraction can miss or misread content.'}
    result=analyze_text(extracted_text,language)
    analysis_id=None
    if u:
        with SessionLocal() as session:
            row=save_analysis(session,u,'document',result);session.commit();session.refresh(row)
            analysis_id=row.id
    return {'id':analysis_id,'filename':safe_name,'language':language,'extracted_text':extracted_text,'extraction_available':True,'history_saved':bool(u),'session_valid':bool(u),'extraction_method':method,**result}
@app.post('/api/analyze/url')
def url_analyze(data:MessageIn,u=Depends(current_user),s:Session=Depends(db)):
    language=data.language or u.preferred_language
    if language not in SUPPORTED_LANGUAGES: raise HTTPException(422,'Unsupported language')
    try:
        result=analyze_url(data.text)
    except URLRejected as exc:
        raise HTTPException(422,str(exc))
    except ValueError as exc:
        raise HTTPException(422,str(exc))
    result['language']=language
    result['explanation']=result['risk_phrase']+' '+result['explanation']
    row=save_analysis(s,u,'url',result)
    s.commit();s.refresh(row)
    return {'id':row.id,**result,'history_saved':True,'session_valid':True}
@app.get('/api/analysis/history')
def history(limit:int=Query(20,ge=1,le=100),offset:int=Query(0,ge=0),risk:str|None=None,kind:str|None=None,u=Depends(current_user),s:Session=Depends(db)):
    query=select(Analysis).where(Analysis.user_id==u.id,Analysis.deleted_at.is_(None))
    if risk: query=query.where(Analysis.risk==risk.upper())
    if kind: query=query.where(Analysis.kind==kind[:32])
    rows=s.scalars(query.order_by(Analysis.created_at.desc()).offset(offset).limit(limit)).all()
    return {'items':[{'id':a.id,'type':a.kind,'risk':a.risk,'summary':a.summary,'created_at':a.created_at.isoformat()} for a in rows],'limit':limit,'offset':offset,'has_more':len(rows)==limit}
@app.get('/api/analysis/{analysis_id}')
def get_analysis(analysis_id:str,u=Depends(current_user),s:Session=Depends(db)):
    a=s.get(Analysis,analysis_id)
    if not a or a.user_id!=u.id or a.deleted_at: raise HTTPException(404,'Analysis not found')
    return {'id':a.id,'type':a.kind,'risk':a.risk,'summary':a.summary,'created_at':a.created_at.isoformat()}
@app.delete('/api/analysis/{analysis_id}')
def delete_analysis(analysis_id:str,u=Depends(current_user),s:Session=Depends(db)):
    a=s.get(Analysis,analysis_id)
    if not a or a.user_id!=u.id or a.deleted_at: raise HTTPException(404,'Analysis not found')
    a.deleted_at=datetime.now(timezone.utc);a.updated_at=a.deleted_at;record_audit(s,u.id,'analysis.soft_deleted','analysis',a.id);s.commit();return {'deleted':True}

@app.get('/api/education')
def education(s:Session=Depends(db)):
    rows=s.scalars(select(EducationModule).where(EducationModule.active.is_(True)).order_by(EducationModule.title)).all()
    return [{'slug':m.slug,'title':m.title,'simple_explanation':m.content.get('simple_explanation','')} for m in rows]
@app.get('/api/education/videos')
def official_videos(topic:str|None=None,language:str|None=None,s:Session=Depends(db)):
    query=select(OfficialVideo).where(OfficialVideo.active.is_(True))
    if topic: query=query.where(OfficialVideo.topic==topic[:64])
    if language and language.lower()!='other': query=query.where(OfficialVideo.language==language[:24])
    rows=s.scalars(query.order_by(OfficialVideo.title)).all()
    return [{'id':v.id,'title':v.title,'description':v.description,'youtubeUrl':v.youtube_url,'thumbnail':v.thumbnail,'language':v.language,'authority':v.authority,'topic':v.topic,'isOfficial':v.is_official} for v in rows]
@app.get('/api/education/progress')
def education_progress(u=Depends(current_user),s:Session=Depends(db)):
    modules=s.scalars(select(EducationModule).where(EducationModule.active.is_(True))).all()
    progress={p.module_id:p for p in s.scalars(select(UserProgress).where(UserProgress.user_id==u.id)).all()}
    attempts=s.scalars(select(QuizAttempt).where(QuizAttempt.user_id==u.id).order_by(QuizAttempt.created_at.desc())).all()
    by_quiz={q.id:q.module_id for q in s.scalars(select(Quiz)).all()}
    latest={}
    for attempt in attempts:
        slug=next((m.slug for m in modules if m.id==by_quiz.get(attempt.quiz_id)),None)
        if slug and slug not in latest: latest[slug]={'score':attempt.score,'total':attempt.total,'created_at':attempt.created_at.isoformat()}
    completed=sum(1 for m in modules if progress.get(m.id) and progress[m.id].completed_at)
    return {'completed_lessons':completed,'total_lessons':len(modules),'progress_percent':round(completed*100/len(modules)) if modules else 0,'quiz_attempts':len(attempts),'average_quiz_score':round(sum(a.score*100/a.total for a in attempts if a.total)/len([a for a in attempts if a.total])) if any(a.total for a in attempts) else 0,'lessons':[{'slug':m.slug,'completed':bool(progress.get(m.id) and progress[m.id].completed_at),'best_score':progress[m.id].best_score if m.id in progress else 0,'latest_attempt':latest.get(m.slug)} for m in modules]}
@app.get('/api/education/{lesson_id}')
def lesson(lesson_id:str,s:Session=Depends(db)):
    module=s.scalar(select(EducationModule).where(EducationModule.slug==lesson_id,EducationModule.active.is_(True)))
    if not module: raise HTTPException(404,'Lesson not found')
    quiz=s.scalar(select(Quiz).where(Quiz.module_id==module.id,Quiz.active.is_(True)))
    questions=[{k:v for k,v in q.items() if k not in ('correct_index','explanation')} for q in (quiz.questions if quiz else [])]
    return {'slug':module.slug,'title':module.title,**module.content,'quiz_id':quiz.id if quiz else None,'quiz':questions}
@app.post('/api/education/{lesson_id}/quiz-attempt')
def submit_quiz(lesson_id:str,data:QuizAttemptInput,u=Depends(current_user),s:Session=Depends(db)):
    module=s.scalar(select(EducationModule).where(EducationModule.slug==lesson_id,EducationModule.active.is_(True)))
    if not module: raise HTTPException(404,'Lesson not found')
    quiz=s.scalar(select(Quiz).where(Quiz.module_id==module.id,Quiz.active.is_(True)))
    if not quiz or len(quiz.questions)!=3: raise HTTPException(409,'Quiz is currently unavailable')
    if any(answer>=len(q.get('options',[])) for answer,q in zip(data.answers,quiz.questions)): raise HTTPException(422,'An answer selection is outside the available options.')
    score=sum(answer==q['correct_index'] for answer,q in zip(data.answers,quiz.questions))
    attempt=QuizAttempt(user_id=u.id,quiz_id=quiz.id,score=score,total=3,answers=data.answers)
    progress=s.scalar(select(UserProgress).where(UserProgress.user_id==u.id,UserProgress.module_id==module.id))
    if not progress: progress=UserProgress(user_id=u.id,module_id=module.id,best_score=0,quiz_attempts=0);s.add(progress)
    progress.quiz_attempts+=1;progress.best_score=max(progress.best_score,score);progress.completed_at=progress.completed_at or datetime.now(timezone.utc)
    s.add(attempt);record_audit(s,u.id,'education.quiz_submitted','quiz',quiz.id);s.commit()
    return {'score':score,'total':3,'completed':True,'review':[{'correct':data.answers[i]==q['correct_index'],'correct_index':q['correct_index'],'explanation':q['explanation']} for i,q in enumerate(quiz.questions)]}
@app.get('/api/rights')
def rights(s:Session=Depends(db)):
    rows=s.scalars(select(GrievanceGuide).where(GrievanceGuide.category=='rights',GrievanceGuide.active.is_(True)).order_by(GrievanceGuide.title)).all()
    return [{'slug':g.slug,'title':g.title,'content':g.content,'reviewed_at':g.reviewed_at.isoformat() if g.reviewed_at else None} for g in rows]
@app.get('/api/grievance')
def grievance(s:Session=Depends(db)):
    rows=s.scalars(select(GrievanceGuide).where(GrievanceGuide.category!='rights',GrievanceGuide.active.is_(True)).order_by(GrievanceGuide.title)).all()
    return {'categories':[{'slug':g.slug,'title':g.title} for g in rows],'notice':'General information only. This assistant does not file complaints or provide legal advice.'}
@app.get('/api/grievance/{category}')
def grievance_detail(category:str,s:Session=Depends(db)):
    guide=s.scalar(select(GrievanceGuide).where(GrievanceGuide.slug==category,GrievanceGuide.active.is_(True),GrievanceGuide.category!='rights'))
    if not guide: raise HTTPException(404,'Guidance category not found')
    return {'slug':guide.slug,'title':guide.title,**guide.content,'notice':'Use current official channels published by the relevant organization. This assistant does not file a complaint.'}
@app.post('/api/feedback')
def feedback(data:FeedbackInput,u=Depends(current_user),s:Session=Depends(db)):
    item=Feedback(user_id=u.id,category=data.category,message=data.message);s.add(item);s.flush();record_audit(s,u.id,'feedback.created','feedback',item.id);s.commit();return {'received':True,'id':item.id}
@app.get('/api/notifications')
def notifications(u=Depends(current_user),s:Session=Depends(db)):
    rows=s.scalars(select(Notification).where(Notification.user_id==u.id,Notification.deleted_at.is_(None)).order_by(Notification.created_at.desc()).limit(50)).all()
    return [{'id':n.id,'title':n.title,'body':n.body,'read':bool(n.read_at),'created_at':n.created_at.isoformat()} for n in rows]
@app.patch('/api/notifications/{notification_id}/read')
def mark_notification(notification_id:str,data:NotificationReadInput,u=Depends(current_user),s:Session=Depends(db)):
    item=s.scalar(select(Notification).where(Notification.id==notification_id,Notification.user_id==u.id,Notification.deleted_at.is_(None)))
    if not item: raise HTTPException(404,'Notification not found')
    item.read_at=datetime.now(timezone.utc) if data.read else None;s.commit();return {'updated':True}
def require_admin(u=Depends(current_user),s:Session=Depends(db)):
    if u.role=='admin' or s.scalar(select(user_roles.c.user_id).join(Role,user_roles.c.role_id==Role.id).where(user_roles.c.user_id==u.id,Role.name=='admin')): return u
    raise HTTPException(403,'Administrator access is required')

def _read_platform_content():
    try: return json.loads(PLATFORM_DATA_FILE.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError): return []

def _write_platform_content(items):
    PLATFORM_DATA_FILE.parent.mkdir(parents=True,exist_ok=True)
    PLATFORM_DATA_FILE.write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

@app.post('/api/admin/platforms')
def admin_add_platform(data:OfficialPlatformInput,_=Depends(require_admin)):
    items=_read_platform_content()
    if any(item.get('id')==data.id for item in items): raise HTTPException(status_code=409,detail='Platform id already exists.')
    items.append(data.model_dump());_write_platform_content(items);return data.model_dump()

@app.put('/api/admin/platforms/{platform_id}')
def admin_update_platform(platform_id:str,data:OfficialPlatformInput,_=Depends(require_admin)):
    items=_read_platform_content();index=next((i for i,item in enumerate(items) if item.get('id')==platform_id),None)
    if index is None: raise HTTPException(status_code=404,detail='Platform entry not found.')
    if data.id!=platform_id and any(item.get('id')==data.id for item in items): raise HTTPException(status_code=409,detail='Platform id already exists.')
    items[index]=data.model_dump();_write_platform_content(items);return items[index]

@app.delete('/api/admin/platforms/{platform_id}')
def admin_delete_platform(platform_id:str,_=Depends(require_admin)):
    items=_read_platform_content();remaining=[item for item in items if item.get('id')!=platform_id]
    if len(items)==len(remaining): raise HTTPException(status_code=404,detail='Platform entry not found.')
    _write_platform_content(remaining);return {'deleted':platform_id}

@app.get('/api/admin/overview')
def admin_overview(_=Depends(require_admin),s:Session=Depends(db)):
    return {'users':s.query(User).count(),'analyses':s.query(Analysis).filter(Analysis.deleted_at.is_(None)).count(),'lessons':s.query(EducationModule).count(),'feedback':s.query(Feedback).filter(Feedback.deleted_at.is_(None)).count()}
@app.get('/api/admin/audit')
def admin_audit(limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0),_=Depends(require_admin),s:Session=Depends(db)):
    rows=s.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)).all()
    return {'items':[{'id':r.id,'user_id':r.user_id,'action':r.action,'entity_type':r.entity_type,'entity_id':r.entity_id,'outcome':r.outcome,'created_at':r.created_at.isoformat()} for r in rows],'limit':limit,'offset':offset}
@app.get('/api/admin/feedback')
def admin_feedback(limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0),_=Depends(require_admin),s:Session=Depends(db)):
    rows=s.scalars(select(Feedback).order_by(Feedback.created_at.desc()).offset(offset).limit(limit)).all()
    return {'items':[{'id':r.id,'user_id':r.user_id,'category':r.category,'message':r.message,'status':r.status,'created_at':r.created_at.isoformat()} for r in rows],'limit':limit,'offset':offset}
@app.put('/api/admin/guides/{slug}')
def admin_update_guide(slug:str,data:GuideUpdate,_=Depends(require_admin),s:Session=Depends(db)):
    guide=s.scalar(select(GrievanceGuide).where(GrievanceGuide.slug==slug))
    if not guide: raise HTTPException(404,'Guidance content not found')
    guide.title=data.title;guide.category=data.category;guide.content=data.content;guide.official_url=data.official_url;guide.reviewed_at=datetime.now(timezone.utc)
    record_audit(s,_.id,'content.guide_updated','grievance_guide',guide.id);s.commit()
    return {'updated':True,'slug':guide.slug,'reviewed_at':guide.reviewed_at.isoformat()}
@app.post('/api/admin/videos')
def admin_add_video(data:OfficialVideoInput,u=Depends(require_admin),s:Session=Depends(db)):
    video=OfficialVideo(**data.model_dump())
    s.add(video)
    try: s.flush()
    except Exception:
        s.rollback(); raise HTTPException(409,'A video with this YouTube URL may already exist.')
    record_audit(s,u.id,'content.video_added','official_video',video.id);s.commit();s.refresh(video)
    return {'id':video.id,'title':video.title,'youtubeUrl':video.youtube_url}
@app.put('/api/admin/videos/{video_id}')
def admin_update_video(video_id:str,data:OfficialVideoInput,u=Depends(require_admin),s:Session=Depends(db)):
    video=s.get(OfficialVideo,video_id)
    if not video: raise HTTPException(404,'Video not found')
    for key,value in data.model_dump().items(): setattr(video,key,value)
    record_audit(s,u.id,'content.video_updated','official_video',video.id);s.commit()
    return {'updated':True,'id':video.id}
@app.delete('/api/admin/videos/{video_id}')
def admin_remove_video(video_id:str,u=Depends(require_admin),s:Session=Depends(db)):
    video=s.get(OfficialVideo,video_id)
    if not video: raise HTTPException(404,'Video not found')
    video.active=False;record_audit(s,u.id,'content.video_archived','official_video',video.id);s.commit()
    return {'deleted':True}
@app.get('/api/demo/examples')
def examples(): return [{'type':'WhatsApp','synthetic':True,'text':'Guaranteed 30% monthly return. Invest today. Limited slots. Send payment immediately.'},{'type':'Telegram','synthetic':True,'text':'Official advisor: send an OTP to unlock a guaranteed return. Invite friends for a bonus.'},{'type':'URL','synthetic':True,'text':'http://secure-example.invalid/login'}]

# Wrap the complete FastAPI stack so CORS headers also cover app-level error responses.
app=CORSMiddleware(app, allow_origins=allowed_origins, allow_credentials=False, allow_methods=['GET','POST','PATCH','PUT','DELETE','OPTIONS'], allow_headers=['Authorization','Content-Type'])
