import os, hashlib, secrets, string, io, base64
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, UniqueConstraint
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook, load_workbook

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Vercel's application directory is read-only.
if os.environ.get("VERCEL") == "1":
    INSTANCE = "/tmp/cbe_pms/instance"
else:
    INSTANCE = os.path.join(BASE_DIR, "instance")

os.makedirs(INSTANCE, exist_ok=True)

UPLOADS = os.path.join(INSTANCE, "uploads")
os.makedirs(UPLOADS, exist_ok=True)
app=Flask(__name__)
SECRET_KEY=os.environ.get('SECRET_KEY')
if not SECRET_KEY and (os.environ.get('FLASK_ENV')=='production' or os.environ.get('VERCEL')=='1'): raise RuntimeError('SECRET_KEY must be set in production and on Vercel')
app.secret_key=SECRET_KEY or secrets.token_hex(32)
app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1)
cookie_secure=os.environ.get('COOKIE_SECURE','1' if os.environ.get('FLASK_ENV')=='production' or os.environ.get('VERCEL')=='1' else '0')=='1'
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=cookie_secure,PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
db_url=os.environ.get('DATABASE_URL')
if not db_url and os.environ.get('VERCEL')=='1': raise RuntimeError('DATABASE_URL is required on Vercel. Connect a managed PostgreSQL database before deployment.')
if not db_url: db_url='sqlite:///'+os.path.join(INSTANCE,'cbe_pms.db')
if db_url.startswith('postgres://'): db_url=db_url.replace('postgres://','postgresql://',1)
app.config.update(SQLALCHEMY_DATABASE_URI=db_url,SQLALCHEMY_TRACK_MODIFICATIONS=False,MAX_CONTENT_LENGTH=16*1024*1024)
db=SQLAlchemy(app)
LEARNING_AREAS=['Mathematics','English','Kiswahili','Integrated Science','Pre-technical Studies','Agriculture','Social Studies','C.R.E','Creative Arts and Sports']
CLASSES=[str(i) for i in range(1,10)]; STREAMS=['East','West','North','South','A','B','C','D']; TERMS=['Term 1','Term 2','Term 3']; YEARS=[str(y) for y in range(2026,2051)]
ASSESSMENT_TYPES=['Opener Assessment','Mid-Term Assessment','End Term Assessment','End Year Assessment','Continuous Assessment']; ASSESSMENT_GRADES=CLASSES+['Primary School','Junior School','All']
LEVELS=[('EE1',90),('EE2',75),('ME1',58),('ME2',41),('AE1',31),('AE2',21),('BE1',11),('BE2',1)]
class User(db.Model):
 __tablename__='user'
 id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(100),unique=True,nullable=False); password=db.Column(db.String(255),nullable=False); role=db.Column(db.String(30),nullable=False); password_display=db.Column(db.String(100),default='')
class Teacher(db.Model):
 __tablename__='teacher'
 id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(150),nullable=False); teacher_no=db.Column(db.String(100)); username=db.Column(db.String(100),unique=True)
class Learner(db.Model):
 __tablename__='learner'
 id=db.Column(db.Integer,primary_key=True); admission_no=db.Column(db.String(80),unique=True,nullable=False); name=db.Column(db.String(200),nullable=False); class_name=db.Column(db.String(30)); stream=db.Column(db.String(50)); parent_phone=db.Column(db.String(50)); assessment_no=db.Column(db.String(80)); status=db.Column(db.String(30),nullable=False,default='Active'); graduating_class=db.Column(db.String(120)); graduation_year=db.Column(db.Integer); gender=db.Column(db.String(20))
class Assessment(db.Model):
 __tablename__='assessment'
 id=db.Column(db.Integer,primary_key=True); grade=db.Column(db.String(50),nullable=False); term=db.Column(db.String(30),nullable=False); year=db.Column(db.Integer,nullable=False); assessment_type=db.Column(db.String(80),nullable=False); deadline=db.Column(db.String(80)); analyzed=db.Column(db.Boolean,default=False); analyzed_at=db.Column(db.DateTime); analysis_count=db.Column(db.Integer,default=0); created_at=db.Column(db.DateTime,default=datetime.utcnow); deleted=db.Column(db.Boolean,default=False); deleted_at=db.Column(db.DateTime)
 __table_args__=(UniqueConstraint('grade','term','year','assessment_type',name='uq_assessment'),)
class Score(db.Model):
 __tablename__='score'
 id=db.Column(db.Integer,primary_key=True); learner_id=db.Column(db.Integer,db.ForeignKey('learner.id'),nullable=False); assessment_id=db.Column(db.Integer,db.ForeignKey('assessment.id'),nullable=False); learning_area=db.Column(db.String(100),nullable=False); score=db.Column(db.Float,nullable=False); max_score=db.Column(db.Float,nullable=False,default=100); term=db.Column(db.String(30)); year=db.Column(db.Integer); assessment_type=db.Column(db.String(80)); grade_at_assessment=db.Column(db.String(30)); stream_at_assessment=db.Column(db.String(50))
class Assignment(db.Model):
 __tablename__='assignment'
 id=db.Column(db.Integer,primary_key=True); teacher_id=db.Column(db.Integer,db.ForeignKey('teacher.id'),nullable=False); learning_area=db.Column(db.String(100),nullable=False); class_name=db.Column(db.String(30),nullable=False); stream=db.Column(db.String(50),nullable=False)
class ClassTeacherAssignment(db.Model):
 __tablename__='class_teacher_assignment'
 id=db.Column(db.Integer,primary_key=True); teacher_id=db.Column(db.Integer,db.ForeignKey('teacher.id'),nullable=False); class_name=db.Column(db.String(30),nullable=False); stream=db.Column(db.String(50),nullable=False); __table_args__=(UniqueConstraint('class_name','stream',name='uq_class_teacher'),)
class GraduatingClass(db.Model):
 __tablename__='graduating_class'
 id=db.Column(db.Integer,primary_key=True); label=db.Column(db.String(120),unique=True,nullable=False); graduation_year=db.Column(db.Integer,nullable=False); created_at=db.Column(db.DateTime,default=datetime.utcnow)
class GraduatingClassMember(db.Model):
 __tablename__='graduating_class_member'
 id=db.Column(db.Integer,primary_key=True); graduating_class_id=db.Column(db.Integer,db.ForeignKey('graduating_class.id'),nullable=False); learner_id=db.Column(db.Integer,db.ForeignKey('learner.id'),nullable=False); original_grade=db.Column(db.String(30)); original_stream=db.Column(db.String(50)); __table_args__=(UniqueConstraint('graduating_class_id','learner_id',name='uq_graduating_member'),)
class Setting(db.Model):
 __tablename__='setting'
 key=db.Column(db.String(100),primary_key=True); value=db.Column(db.Text)
def hp(p): return generate_password_hash(p, method='scrypt')
def verify_password(stored, candidate):
 try:
  if stored.startswith(('scrypt:','pbkdf2:','argon2:')): return check_password_hash(stored,candidate)
 except Exception: pass
 return secrets.compare_digest(stored, hashlib.sha256(candidate.encode()).hexdigest())

def current_user(): return User.query.filter_by(username=session.get('username')).first() if session.get('username') else None
def login_required(f):
 @wraps(f)
 def w(*a,**kw):
  if not current_user(): return redirect(url_for('login'))
  return f(*a,**kw)
 return w
def admin_required(f):
 @wraps(f)
 def w(*a,**kw):
  u=current_user()
  if not u: return redirect(url_for('login'))
  if u.role!='Administrator': flash('Administrator access required.','danger'); return redirect(url_for('dashboard'))
  return f(*a,**kw)
 return w
def eligible(a,g): return a.grade in ('All',g,'Primary School' if g in CLASSES[:6] else 'Junior School')
def setting(k,d=''): s=Setting.query.get(k); return s.value if s else d
def cbe_level(p):
 for code,minp in LEVELS:
  if p>=minp: return code, ('Exceeding Expectations' if code.startswith('EE') else 'Meeting Expectations' if code.startswith('ME') else 'Approaching Expectations' if code.startswith('AE') else 'Below Expectations')
 return 'BE2','Below Expectations'
def cbe_points(p):
 for index,(code,minp) in enumerate(LEVELS):
  if p>=minp: return 8-index
 return 0
def parse_deadline(v):
 if not v: return None
 for fmt in ('%Y-%m-%dT%H:%M','%Y-%m-%d %H:%M','%d/%m/%Y %H:%M'):
  try:return datetime.strptime(v,fmt)
  except:pass
 try:return datetime.strptime(v,'%d/%m/%Y')+timedelta(hours=23,minutes=59)
 except:pass
 return None
def locked(a): return bool(a and a.analyzed and a.deadline and parse_deadline(a.deadline) and datetime.now()>parse_deadline(a.deadline))
def assignment_ok(u,area,g,s):
 if u.role=='Administrator': return True
 t=Teacher.query.filter_by(username=u.username).first(); return bool(t and Assignment.query.filter_by(teacher_id=t.id,learning_area=area,class_name=g,stream=s).first())
def init():
 with app.app_context():
  db.create_all()
  if os.environ.get('BOOTSTRAP_DEMO_USERS','0')=='1':
   if not User.query.filter_by(username='admin').first():
    admin_pw=os.environ.get('ADMIN_INITIAL_PASSWORD','admin123')
    db.session.add(User(username=os.environ.get('ADMIN_INITIAL_USERNAME','admin'),password=hp(admin_pw),role='Administrator',password_display=''))
   if not User.query.filter_by(username='teacher').first():
    teacher_pw=os.environ.get('TEACHER_INITIAL_PASSWORD','teacher123')
    db.session.add(User(username='teacher',password=hp(teacher_pw),role='Teacher',password_display=''))
   if not Teacher.query.filter_by(username='teacher').first(): db.session.add(Teacher(name='Default Teacher',username='teacher'))
  db.session.commit()
@app.after_request
def security_headers(response):
 response.headers['X-Content-Type-Options']='nosniff'
 response.headers['X-Frame-Options']='SAMEORIGIN'
 response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
 response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
 if request.is_secure or os.environ.get('FLASK_ENV')=='production': response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
 return response

@app.context_processor
def globals_(): return dict(areas=LEARNING_AREAS,classes=CLASSES,streams=STREAMS,terms=TERMS,years=YEARS,assessment_types=ASSESSMENT_TYPES,assessment_grades=ASSESSMENT_GRADES,current_user=current_user(),setting=setting)
@app.route('/',methods=['GET','POST'])
def login():
 if request.method=='POST':
  u=User.query.filter_by(username=request.form.get('username','').strip()).first()
  if u and verify_password(u.password,request.form.get('password','')):
   # Upgrade legacy SHA-256 passwords on successful login.
   if not u.password.startswith(('scrypt:','pbkdf2:','argon2:')):
    u.password=hp(request.form.get('password','')); u.password_display=''; db.session.commit()
   session.clear(); session['username']=u.username; session.permanent=True; return redirect(url_for('dashboard'))
  flash('Invalid username or password.','danger')
 return render_template('login.html')
@app.get('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
@app.get('/dashboard')
@login_required
def dashboard():
 u=current_user()
 if u.role=='Teacher': return redirect(url_for('teacher_home'))
 return render_template('dashboard.html',learners=Learner.query.count(),assessments=Assessment.query.filter_by(deleted=False).count(),scores=Score.query.count(),teachers=Teacher.query.count())
@app.route('/learners',methods=['GET','POST'])
@admin_required
def learners():
 if request.method=='POST':
  try: db.session.add(Learner(admission_no=request.form['admission_no'].strip(),name=request.form['name'].strip(),class_name=request.form['class_name'],stream=request.form['stream'],parent_phone=request.form.get('parent_phone','').strip(),assessment_no=request.form.get('assessment_no','').strip(),gender=request.form.get('gender','').strip(),status='Active')); db.session.commit(); flash('Learner saved.','success')
  except: db.session.rollback(); flash('Could not save learner. Admission number may already exist.','danger')
 q=request.args.get('q','').strip(); query=Learner.query
 if q: query=query.filter(or_(Learner.name.ilike(f'%{q}%'),Learner.admission_no.ilike(f'%{q}%')))
 return render_template('learners.html',rows=query.order_by(Learner.name).all(),q=q)
@app.post('/learners/<int:id>/delete')
@admin_required
def delete_learner(id):
 l=Learner.query.get_or_404(id); Score.query.filter_by(learner_id=id).delete(); GraduatingClassMember.query.filter_by(learner_id=id).delete(); db.session.delete(l); db.session.commit(); flash('Learner permanently deleted.','success'); return redirect(url_for('learners'))
@app.route('/assessments',methods=['GET','POST'])
@admin_required
def assessments():
 if request.method=='POST':
  v={k:request.form.get(k,'').strip() for k in ['grade','term','year','assessment_type','deadline']}
  if any(v[k]=='-' for k in ['grade','term','year','assessment_type']) or not all(v[k] for k in ['grade','term','year','assessment_type']): flash('Select all assessment fields.','warning')
  else:
   a=Assessment.query.filter_by(grade=v['grade'],term=v['term'],year=int(v['year']),assessment_type=v['assessment_type']).first()
   if not a: a=Assessment(grade=v['grade'],term=v['term'],year=int(v['year']),assessment_type=v['assessment_type']); db.session.add(a)
   a.deleted=False;a.deleted_at=None;a.deadline=v['deadline'];db.session.commit();flash('Assessment created/restored successfully.','success')
 return render_template('assessments.html',active=Assessment.query.filter_by(deleted=False).order_by(Assessment.year.desc(),Assessment.id.desc()).all(),deleted=Assessment.query.filter_by(deleted=True).order_by(Assessment.deleted_at.desc()).all())

@app.post('/assessments/<int:id>/edit')
@admin_required
def edit_assessment(id):
    a=Assessment.query.get_or_404(id)
    grade=request.form.get('grade',a.grade).strip(); term=request.form.get('term',a.term).strip(); year=request.form.get('year',str(a.year)).strip(); atype=request.form.get('assessment_type',a.assessment_type).strip(); deadline=request.form.get('deadline','').strip()
    try:
        conflict=Assessment.query.filter(Assessment.id!=a.id,Assessment.grade==grade,Assessment.term==term,Assessment.year==int(year),Assessment.assessment_type==atype).first()
        if conflict: raise ValueError('Another assessment already uses this grade, term, year and type.')
        a.grade=grade; a.term=term; a.year=int(year); a.assessment_type=atype; a.deadline=deadline
        a.analyzed=False; a.analyzed_at=None; a.analysis_count=0
        db.session.commit(); flash('Assessment details updated. Existing scores remain linked to the same assessment ID.','success')
    except Exception as exc:
        db.session.rollback(); flash(f'Assessment was not updated: {exc}','danger')
    return redirect(url_for('assessments'))

@app.post('/assessments/<int:id>/delete')
@admin_required
def delete_assessment(id): a=Assessment.query.get_or_404(id);a.deleted=True;a.deleted_at=datetime.utcnow();db.session.commit();flash('Assessment moved to Deleted Assessments.','success');return redirect(url_for('assessments'))
@app.post('/assessments/<int:id>/restore')
@admin_required
def restore_assessment(id): a=Assessment.query.get_or_404(id);a.deleted=False;a.deleted_at=None;db.session.commit();return redirect(url_for('assessments'))
@app.post('/assessments/<int:id>/permanent')
@admin_required
def permanent_assessment(id): a=Assessment.query.get_or_404(id);Score.query.filter_by(assessment_id=id).delete();db.session.delete(a);db.session.commit();flash('Assessment permanently deleted.','success');return redirect(url_for('assessments'))
@app.route('/scores',methods=['GET','POST'])
@login_required
def scores():
 u=current_user(); aid=request.values.get('assessment_id',type=int); area=request.values.get('learning_area','-'); grade=request.values.get('grade','-'); stream=request.values.get('stream','-'); selected=Assessment.query.get(aid) if aid else None
 if request.method=='POST' and request.form.get('save'):
  if not selected or area=='-' or grade=='-' or stream=='-' or not eligible(selected,grade): flash('Select a valid assessment, learning area, grade and stream.','warning')
  elif locked(selected) and u.role!='Administrator': flash('Scores are locked after the deadline because the assessment has been analysed.','danger')
  elif not assignment_ok(u,area,grade,stream): flash('You are not assigned to this learning area, grade and stream.','danger')
  else:
   try:
    for k,v in request.form.items():
     if k.startswith('score_') and v.strip()!='':
      mark=float(v); lid=int(k[6:])
      if mark<0 or mark>100: raise ValueError('Scores must be between 0 and 100.')
      learner=Learner.query.filter_by(id=lid,class_name=grade,stream=stream,status='Active').first()
      if not learner: raise ValueError('A submitted learner does not belong to the selected grade and stream.')
      s=Score.query.filter_by(learner_id=lid,assessment_id=aid,learning_area=area).first()
      if s:s.score=mark;s.term=selected.term;s.year=selected.year;s.assessment_type=selected.assessment_type;s.grade_at_assessment=grade;s.stream_at_assessment=stream
      else:db.session.add(Score(learner_id=lid,assessment_id=aid,learning_area=area,score=mark,max_score=100,term=selected.term,year=selected.year,assessment_type=selected.assessment_type,grade_at_assessment=grade,stream_at_assessment=stream))
    db.session.commit();flash('Scores saved.','success')
   except Exception as exc: db.session.rollback();flash(f'Scores were not saved: {exc}','danger')
 learners=[]; existing={}
 if selected and grade!='-' and stream!='-' and area!='-':
  if assignment_ok(u,area,grade,stream):
   learners=Learner.query.filter_by(class_name=grade,stream=stream,status='Active').order_by(Learner.name).all(); existing={s.learner_id:s.score for s in Score.query.filter_by(assessment_id=aid,learning_area=area).all()}
  else: flash('You are not assigned to this learning area, grade and stream.','danger')
 return render_template('scores.html',assessments=Assessment.query.filter_by(deleted=False).order_by(Assessment.year.desc(),Assessment.id.desc()).all(),selected=selected,learners=learners,existing=existing,selected_area=area,selected_grade=grade,selected_stream=stream)
def filtered_learners(a,stream='-',grade='-'):
 q=Learner.query
 if grade!='-': q=q.filter(Learner.class_name.in_([grade] if grade in CLASSES else (CLASSES[:6] if grade=='Primary School' else CLASSES[6:] if grade=='Junior School' else CLASSES)))
 if stream!='-': q=q.filter_by(stream=stream)
 return [l for l in q.all() if eligible(a,l.class_name)]
def report_rows(a,stream='-',grade='-'):
 out=[]
 for l in filtered_learners(a,stream,grade):
  ss=Score.query.filter_by(learner_id=l.id,assessment_id=a.id).all(); total_points=0; area=[]
  for s in ss:
   pct=(s.score*100/s.max_score) if s.max_score else 0; pts=cbe_points(pct);code,_=cbe_level(pct); total_points+=pts;area.append((s.learning_area,s.score,s.max_score,pct,code,pts))
  if not area: continue
  avg=sum(x[3] for x in area)/len(area); total_marks=sum(x[1] for x in area)
  out.append(dict(learner=l,total_points=total_points,total_marks=total_marks,avg=avg,level=cbe_level(avg)[0],areas=area))
 rank_by=request.args.get('rank_by','Total Marks')
 if rank_by=='Total Points': out.sort(key=lambda x:(-x['total_points'],-x['total_marks'],x['learner'].name))
 else: out.sort(key=lambda x:(-x['total_marks'],-x['total_points'],x['learner'].name))
 return out
@app.get('/reports/merit')
@login_required
def merit():
 aid=request.args.get('assessment_id',type=int); a=Assessment.query.get(aid) if aid else None
 rows=report_rows(a,request.args.get('stream','-'),request.args.get('grade','-')) if a else []
 return render_template('merit.html',assessments=Assessment.query.filter_by(deleted=False).all(),selected=a,rows=rows,rank_by=request.args.get('rank_by','Total Marks'))

def previous_assessment(a):
 if not a: return None
 return Assessment.query.filter(Assessment.deleted==False,Assessment.grade==a.grade,Assessment.id<a.id).order_by(Assessment.id.desc()).first()

def build_pdf(title,meta,headers,rows,filename):
 path=os.path.join(INSTANCE,filename); doc=SimpleDocTemplate(path,pagesize=landscape(A4),rightMargin=30,leftMargin=30,topMargin=28,bottomMargin=24); st=getSampleStyleSheet(); center=ParagraphStyle('c',parent=st['Normal'],alignment=TA_CENTER,fontSize=8); story=[]
 logo=setting('school_logo','')
 if logo:
  from reportlab.platypus import Image
  try:
   if logo.startswith('data:image/') and ',' in logo: story.append(Image(io.BytesIO(base64.b64decode(logo.split(',',1)[1])),width=90,height=90))
   elif os.path.exists(logo): story.append(Image(logo,width=90,height=90))
  except Exception: pass
 story += [Paragraph(setting('school_name','CBE PERFORMANCE MANAGEMENT SYSTEM').upper(),ParagraphStyle('school',parent=st['Title'],alignment=TA_CENTER,fontName='Times-Bold',fontSize=16)),Paragraph(meta,ParagraphStyle('meta',parent=st['Normal'],alignment=TA_CENTER,fontName='Times-Roman',fontSize=9)),Paragraph(title,ParagraphStyle('title',parent=st['Heading2'],alignment=TA_CENTER,fontName='Times-Bold',fontSize=13)),Spacer(1,8)]
 data=[headers]+rows;t=Table(data,repeatRows=1);t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.35,colors.black),('FONTNAME',(0,0),(-1,0),'Times-Bold'),('FONTNAME',(0,1),(-1,-1),'Times-Roman'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('ALIGN',(0,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('FONTSIZE',(0,0),(-1,-1),7),('BACKGROUND',(0,0),(-1,0),colors.lightgrey)]));story.append(t)
 def page_number(canvas, document):
  canvas.saveState(); canvas.setFont('Times-Roman',8); canvas.drawRightString(landscape(A4)[0]-18,12,f'Page {document.page}'); canvas.restoreState()
 doc.build(story,onFirstPage=page_number,onLaterPages=page_number);return path
@app.get('/reports/merit.pdf')
@login_required
def merit_pdf_route():
 a=Assessment.query.get_or_404(request.args.get('assessment_id',type=int)); rows=report_rows(a,request.args.get('stream','-'),request.args.get('grade','-')); data=[[i+1,r['learner'].name,r['learner'].admission_no,r['learner'].class_name,r['learner'].stream,f"{r['total_marks']:g}",r['total_points'],f"{r['avg']:.1f}%"] for i,r in enumerate(rows)];path=build_pdf('MERIT LIST',f'GRADE: {a.grade}   |   TERM: {a.term.replace("Term ","")}   |   YEAR: {a.year}   |   TYPE OF ASSESSMENT: {a.assessment_type}', ['Position','Learner','ADM NO.','Grade','Stream','Total Marks','Points','Average'],data,f'merit_{a.id}.pdf');return send_file(path,as_attachment=True,download_name=f'Merit_List_{a.year}.pdf')
@app.get('/reports/analysis')
@login_required
def analysis():
 aid=request.args.get('assessment_id',type=int);a=Assessment.query.get(aid) if aid else None
 grade=request.args.get('grade','-'); stream=request.args.get('stream','-')
 rows=report_rows(a,stream,grade) if a else []
 prev=previous_assessment(a); prevrows={r['learner'].id:r['avg'] for r in report_rows(prev)} if prev else {}
 summary=[]
 if a:
  for area in LEARNING_AREAS:
   vals=[x for r in rows for x in r['areas'] if x[0]==area]
   avg=sum(v[3] for v in vals)/len(vals) if vals else 0;code,level=cbe_level(avg)
   best=max((r for r in rows if any(x[0]==area for x in r['areas'])), key=lambda r: next(x[3] for x in r['areas'] if x[0]==area), default=None)
   summary.append(dict(area=area,avg=avg,code=code,level=level,points=cbe_points(avg),best=best['learner'].name if best else '-'))
 stream_summary=[]
 if a:
  groups={}
  for r in rows:
   groups.setdefault(r['learner'].stream,[]).append(r)
  for st,rs in groups.items(): stream_summary.append(dict(stream=st,count=len(rs),avg=sum(x['avg'] for x in rs)/len(rs),points=round(sum(x['total_points'] for x in rs)/len(rs),1)))
  stream_summary.sort(key=lambda x:-x['avg'])
 for r in rows:
  r['level']=cbe_level(r['avg'])[0]; r['deviation']=round(r['avg']-prevrows.get(r['learner'].id,r['avg']),1) if prev else '-'
 return render_template('analysis.html',assessments=Assessment.query.filter_by(deleted=False).all(),selected=a,rows=rows,summary=summary,stream_summary=stream_summary)

@app.post('/reports/analysis/<int:id>/reanalyze')
@admin_required
def reanalyze(id):
 a=Assessment.query.get_or_404(id);a.analyzed=True;a.analyzed_at=datetime.utcnow();a.analysis_count=(a.analysis_count or 0)+1;db.session.commit();flash('Assessment analysed successfully.','success');return redirect(url_for('analysis',assessment_id=id))

@app.get('/reports/analysis.pdf')
@login_required
def analysis_pdf():
 a=Assessment.query.get_or_404(request.args.get('assessment_id',type=int)); rows=report_rows(a,request.args.get('stream','-'),request.args.get('grade','-'))
 prev=previous_assessment(a); prevrows={r['learner'].id:r['avg'] for r in report_rows(prev)} if prev else {}
 data=[]
 for i,r in enumerate(rows):
  avg=r['avg'];data.append([i+1,r['learner'].name,r['learner'].admission_no,r['learner'].class_name,r['learner'].stream,f'{avg:.1f}%',cbe_level(avg)[0],r['total_points'],('-' if not prev else f'{avg-prevrows.get(r["learner"].id,avg):+.1f}%')])
 meta=f'GRADE: {a.grade}   |   TERM: {a.term.replace("Term ","")}   |   YEAR: {a.year}   |   TYPE OF ASSESSMENT: {a.assessment_type}'
 path=build_pdf('ASSESSMENT ANALYSIS',meta,['Pos','Learner','ADM NO.','Grade','Stream','Average','Level','Points','Deviation'],data,f'analysis_{a.id}.pdf');return send_file(path,as_attachment=True,download_name=f'Assessment_Analysis_{a.year}.pdf')

@app.get('/reports/learner/<int:id>.pdf')
@login_required
def learner_pdf(id):
 l=Learner.query.get_or_404(id); aid=request.args.get('assessment_id',type=int); a=Assessment.query.get(aid) if aid else Assessment.query.filter_by(deleted=False).order_by(Assessment.year.desc(),Assessment.id.desc()).first();ss=Score.query.filter_by(learner_id=id,assessment_id=a.id).all() if a else []; rows=[]
 for s in ss:
  pct=s.score*100/s.max_score if s.max_score else 0;code,level=cbe_level(pct);rows.append([s.learning_area,f'{s.score:g}',f'{pct:.1f}%',code,cbe_points(pct),level])
 ct=ClassTeacherAssignment.query.filter_by(class_name=l.class_name,stream=l.stream).first(); ct_name=Teacher.query.get(ct.teacher_id).name if ct and Teacher.query.get(ct.teacher_id) else '-'
 path=build_pdf('LEARNER PERFORMANCE REPORT',f'LEARNER: {l.name}   |   ADM NO.: {l.admission_no}   |   GRADE: {l.class_name}   |   STREAM: {l.stream}   |   CLASS TEACHER: {ct_name}   |   TERM: {a.term.replace("Term ","") if a else "-"}   |   YEAR: {a.year if a else "-"}', ['Learning Area','Score','Percent','Level','Points','Performance'],rows,f'learner_{id}_{a.id if a else 0}.pdf');return send_file(path,as_attachment=True,download_name=f'{secure_filename(l.name)}_Report.pdf')
@app.get('/reports/raw.pdf')
@login_required
def raw_pdf():
 a=Assessment.query.get_or_404(request.args.get('assessment_id',type=int));rows=[]
 for l in filtered_learners(a,request.args.get('stream','-'),request.args.get('grade','-')):
  ss={s.learning_area:s for s in Score.query.filter_by(learner_id=l.id,assessment_id=a.id).all()};total=sum((s.score for s in ss.values()),0);rows.append([l.admission_no,l.name,l.class_name,l.stream,*[ss[x].score if x in ss else '-' for x in LEARNING_AREAS]])
 path=build_pdf('RAW UNANALYZED ASSESSMENT SCORES',f'GRADE: {a.grade}   |   TERM: {a.term.replace("Term ","")}   |   YEAR: {a.year}   |   TYPE OF ASSESSMENT: {a.assessment_type}', ['ADM NO.','Learner','Grade','Stream',*LEARNING_AREAS],rows,f'raw_{a.id}.pdf');return send_file(path,as_attachment=True,download_name=f'Raw_Scores_{a.year}.pdf')
@app.get('/reports/learner/<int:id>')
@login_required
def learner_detail(id):
 l=Learner.query.get_or_404(id);return render_template('learner_detail.html',learner=l,assessments=Assessment.query.filter_by(deleted=False).order_by(Assessment.year.desc()).all())
@app.get('/reports/learners')
@login_required
def learner_reports():
 q=request.args.get('q','').strip();qset=Learner.query
 if q:qset=qset.filter(or_(Learner.name.ilike(f'%{q}%'),Learner.admission_no.ilike(f'%{q}%')))
 return render_template('learner_reports.html',rows=qset.order_by(Learner.name).all(),assessments=Assessment.query.filter_by(deleted=False).all(),q=q)
@app.get('/teachers')
@admin_required
def teachers(): return render_template('teachers.html',rows=Teacher.query.order_by(Teacher.name).all())
@app.post('/teachers')
@admin_required
def create_teacher():
 name=request.form['name'].strip();school=setting('school_name','school').split()[0];base=name.split()[0].lower()+'@'+school.lower();username=base;n=1
 while User.query.filter_by(username=username).first():n+=1;username=base+str(n)
 temp=''.join(secrets.choice(string.digits) for _ in range(6));db.session.add(User(username=username,password=hp(temp),role='Teacher',password_display=''));db.session.add(Teacher(name=name,teacher_no=request.form.get('teacher_no',''),username=username));db.session.commit();flash(f'Teacher created. Username: {username} | Temporary password: {temp}','success');return redirect(url_for('teachers'))
@app.route('/teachers/<int:id>/edit',methods=['GET','POST'])
@admin_required
def edit_teacher(id):
 t=Teacher.query.get_or_404(id);u=User.query.filter_by(username=t.username).first()
 if request.method=='POST': t.name=request.form['name'].strip();t.teacher_no=request.form.get('teacher_no','').strip();db.session.commit();flash('Teacher updated.','success');return redirect(url_for('teachers'))
 return render_template('edit_teacher.html',teacher=t)
@app.post('/teachers/<int:id>/reset')
@admin_required
def reset_teacher(id):
 t=Teacher.query.get_or_404(id);u=User.query.filter_by(username=t.username).first();temp=''.join(secrets.choice(string.digits) for _ in range(6));u.password=hp(temp);u.password_display='';db.session.commit();flash(f'New temporary password for {t.username}: {temp}','success');return redirect(url_for('teachers'))

@app.post('/teachers/<int:id>/make-admin')
@admin_required
def make_admin(id):
    t=Teacher.query.get_or_404(id); u=User.query.filter_by(username=t.username).first_or_404(); u.role='Administrator'; db.session.commit(); flash(f'{t.name} is now an Administrator.','success'); return redirect(url_for('teachers'))

@app.post('/teachers/<int:id>/delete')
@admin_required
def delete_teacher(id):
 t=Teacher.query.get_or_404(id);u=User.query.filter_by(username=t.username).first();Assignment.query.filter_by(teacher_id=id).delete();ClassTeacherAssignment.query.filter_by(teacher_id=id).delete();db.session.delete(t); 
 if u: db.session.delete(u)
 db.session.commit();flash('Teacher deleted.','success');return redirect(url_for('teachers'))
@app.route('/change-password',methods=['GET','POST'])
@login_required
def change_password():
 u=current_user()
 if request.method=='POST':
  if not verify_password(u.password,request.form.get('old','')): flash('Current password is incorrect.','danger')
  elif request.form.get('new','')!=request.form.get('confirm',''): flash('New passwords do not match.','danger')
  else: u.password=hp(request.form['new']);u.password_display='';db.session.commit();flash('Password changed successfully.','success');return redirect(url_for('dashboard'))
 return render_template('change_password.html')


@app.get('/teacher')
@login_required
def teacher_home():
    u=current_user()
    if u.role!='Teacher': return redirect(url_for('dashboard'))
    t=Teacher.query.filter_by(username=u.username).first()
    assignments=Assignment.query.filter_by(teacher_id=t.id).all() if t else []
    assigned_areas=sorted({x.learning_area for x in assignments})
    assigned_classes=sorted({x.class_name for x in assignments}, key=lambda x:int(x) if x.isdigit() else 99)
    assigned_streams=sorted({x.stream for x in assignments})
    active=Assessment.query.filter_by(deleted=False).order_by(Assessment.year.desc(),Assessment.id.desc()).all()
    return render_template('teacher_dashboard.html',teacher=t,assignments=assignments,assigned_areas=assigned_areas,assigned_classes=assigned_classes,assigned_streams=assigned_streams,assessments=active)

@app.get('/teacher/results/<int:assessment_id>.pdf')
@login_required
def teacher_results_pdf(assessment_id):
    u=current_user()
    if u.role!='Teacher': abort(403)
    t=Teacher.query.filter_by(username=u.username).first_or_404()
    a=Assessment.query.get_or_404(assessment_id)
    assignments=Assignment.query.filter_by(teacher_id=t.id).all()
    allowed={(x.learning_area,x.class_name,x.stream) for x in assignments}
    rows=[]
    for l in Learner.query.order_by(Learner.name).all():
        for area,g,s in allowed:
            if l.class_name==g and l.stream==s and eligible(a,g):
                sc=Score.query.filter_by(learner_id=l.id,assessment_id=a.id,learning_area=area).first()
                if sc:
                    pct=sc.score*100/sc.max_score if sc.max_score else 0
                    rows.append([l.admission_no,l.name,g,s,area,f'{sc.score:g}',f'{pct:.1f}%',cbe_level(pct)[0],cbe_points(pct)])
    meta=f'GRADE: {a.grade}   |   TERM: {a.term.replace("Term ","")}   |   YEAR: {a.year}   |   TYPE OF ASSESSMENT: {a.assessment_type}'
    path=build_pdf('TEACHER LEARNING AREA RESULTS',meta,['ADM NO.','Learner','Grade','Stream','Learning Area','Score','Percent','Level','Points'],rows,f'teacher_results_{t.id}_{a.id}.pdf')
    return send_file(path,as_attachment=True,download_name=f'Teacher_Results_{a.year}_{a.id}.pdf')

@app.post('/assessments/<int:id>/reanalyze')
@admin_required
def analyze_assessment(id):
    a=Assessment.query.get_or_404(id)
    a.analyzed=True; a.analyzed_at=datetime.utcnow(); a.analysis_count=(a.analysis_count or 0)+1
    db.session.commit(); flash('Assessment analysed/re-analysed successfully.','success')
    return redirect(url_for('analysis',assessment_id=id))

@app.get('/admin/backup')
@admin_required
def backup_database():
    if db_url.startswith('sqlite:///'):
        src=db_url.replace('sqlite:///','',1)
        if os.path.exists(src): return send_file(src,as_attachment=True,download_name=f'CBE_PMS_backup_{datetime.now():%Y%m%d_%H%M%S}.db')
    abort(400,description='Direct database download is available only for SQLite. Use your PostgreSQL provider backup facility in production.')

@app.route('/assignments',methods=['GET','POST'])
@admin_required
def assignments():
 if request.method=='POST':
  try:
   row=Assignment(teacher_id=int(request.form['teacher_id']),learning_area=request.form['learning_area'],class_name=request.form['class_name'],stream=request.form['stream'])
   db.session.add(row);db.session.commit();flash('Assignment saved.','success')
  except Exception as exc: db.session.rollback();flash(f'Assignment was not saved: {exc}','danger')
 grouped=[]
 for teacher in Teacher.query.order_by(Teacher.name).all():
  assigned=Assignment.query.filter_by(teacher_id=teacher.id).order_by(Assignment.class_name,Assignment.stream,Assignment.learning_area).all()
  grouped.append({'teacher':teacher,'assignments':assigned})
 return render_template('assignments.html',rows=grouped,teachers=Teacher.query.order_by(Teacher.name).all())

@app.post('/assignments/<int:id>/delete')
@admin_required
def delete_assignment(id):
 row=Assignment.query.get_or_404(id); db.session.delete(row); db.session.commit(); flash('Learning-area assignment removed.','success'); return redirect(url_for('assignments'))
@app.route('/settings',methods=['GET','POST'])
@admin_required
def settings():
 if request.method=='POST':
  for k in ['school_name','school_address','school_phone','school_period','opening_date','closing_date','opening_day','closing_day']:
   s=Setting.query.get(k) or Setting(key=k);s.value=request.form.get(k,'');db.session.add(s)
  f=request.files.get('logo')
  if f and f.filename:
   name=secure_filename(f.filename);raw=f.read();mime=f.mimetype or 'image/png';encoded=base64.b64encode(raw).decode('ascii');s=Setting.query.get('school_logo') or Setting(key='school_logo');s.value=f'data:{mime};base64,{encoded}';db.session.add(s)
  db.session.commit();flash('School settings saved.','success')
 return render_template('settings.html',vals={s.key:s.value for s in Setting.query.all()})
@app.get('/template/learners.xlsx')
@admin_required
def template_xlsx():
 wb=Workbook();ws=wb.active;ws.title='Learners';ws.append(['Admission No.','First Name','Last Name','Surname','Grade','Stream','Parent Phone']);bio=io.BytesIO();wb.save(bio);bio.seek(0);return send_file(bio,as_attachment=True,download_name='CBE_PMS_Learner_Template.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
@app.post('/learners/import')
@admin_required
def import_learners():
 f=request.files.get('file')
 if not f or not f.filename:flash('Choose an Excel workbook.','warning');return redirect(url_for('learners'))
 try:
  wb=load_workbook(f,read_only=True,data_only=True);ws=wb.active;headers=[str(x.value or '').strip().lower() for x in next(ws.iter_rows())];idx={h:i for i,h in enumerate(headers)};added=0
  for row in ws.iter_rows(min_row=2,values_only=True):
   def g(k): return str(row[idx[k]] or '').strip() if k in idx else ''
   name=g('name') or ' '.join(x for x in [g('first name'),g('last name'),g('surname')] if x)
   adm=g('admission no.') or g('admission_no')
   if not adm or not name:continue
   if Learner.query.filter_by(admission_no=adm).first():continue
   grade=g('grade') or g('class') or g('class name');stream=g('stream') or '-';db.session.add(Learner(admission_no=adm,name=name,class_name=grade,stream=stream,parent_phone=g('parent phone'),assessment_no=g('assessment no.') or g('assessment_no'),gender=g('gender'),status='Active'));added+=1
  db.session.commit();flash(f'Imported {added} learners.','success')
 except Exception as e:db.session.rollback();flash(f'Could not import workbook: {e}','danger')
 return redirect(url_for('learners'))
@app.post('/learners/<int:id>/edit')
@admin_required
def edit_learner(id):
 l=Learner.query.get_or_404(id);l.name=request.form['name'].strip();l.class_name=request.form['class_name'];l.stream=request.form['stream'];l.parent_phone=request.form.get('parent_phone','').strip();l.assessment_no=request.form.get('assessment_no','').strip();l.gender=request.form.get('gender','').strip();db.session.commit();flash('Learner record updated.','success');return redirect(url_for('learners'))

@app.route('/class-teachers',methods=['GET','POST'])
@admin_required
def class_teachers():
    if request.method=='POST':
        tid=request.form.get('teacher_id',type=int); grade=request.form.get('class_name',''); stream=request.form.get('stream','')
        if not tid or not grade or grade=='-' or not stream or stream=='-': flash('Select teacher, grade and stream.','warning')
        else:
            existing=ClassTeacherAssignment.query.filter_by(class_name=grade,stream=stream).first()
            if existing: existing.teacher_id=tid
            else: db.session.add(ClassTeacherAssignment(teacher_id=tid,class_name=grade,stream=stream))
            db.session.commit(); flash('Class teacher assignment saved.','success')
        return redirect(url_for('class_teachers'))
    rows=ClassTeacherAssignment.query.order_by(ClassTeacherAssignment.class_name,ClassTeacherAssignment.stream).all()
    return render_template('class_teachers.html',rows=rows,teachers=Teacher.query.order_by(Teacher.name).all())

@app.post('/class-teachers/<int:id>/delete')
@admin_required
def delete_class_teacher(id):
    row=ClassTeacherAssignment.query.get_or_404(id); db.session.delete(row); db.session.commit(); flash('Class teacher assignment removed.','success'); return redirect(url_for('class_teachers'))

@app.get('/graduating-classes')
@admin_required
def graduating_classes():
    rows=GraduatingClass.query.order_by(GraduatingClass.graduation_year.desc()).all()
    return render_template('graduating_classes.html',rows=[{'id':r.id,'label':r.label,'graduation_year':r.graduation_year,'member_count':GraduatingClassMember.query.filter_by(graduating_class_id=r.id).count()} for r in rows])

def perform_annual_grade_transition(transition_year):
    last=Setting.query.get('last_grade_transition_year')
    if last and last.value==str(transition_year):
        return False, f'Grade transition for {transition_year} has already been completed.'
    graduation_year=transition_year-1
    label=f'Graduating Class of {graduation_year}'
    gc=GraduatingClass.query.filter_by(label=label).first()
    if not gc:
        gc=GraduatingClass(label=label,graduation_year=graduation_year); db.session.add(gc); db.session.flush()
    grade9=Learner.query.filter_by(class_name='9',status='Active').all()
    for learner in grade9:
        exists=GraduatingClassMember.query.filter_by(graduating_class_id=gc.id,learner_id=learner.id).first()
        if not exists: db.session.add(GraduatingClassMember(graduating_class_id=gc.id,learner_id=learner.id,original_grade=learner.class_name,original_stream=learner.stream))
        learner.status='Graduated'; learner.graduating_class=label; learner.graduation_year=graduation_year
    # Promote current active Grades 1–8 one grade, preserving each learner's stream.
    for old_grade in range(8,0,-1):
        for learner in Learner.query.filter_by(class_name=str(old_grade),status='Active').all():
            learner.class_name=str(old_grade+1)
    setting_row=Setting.query.get('last_grade_transition_year') or Setting(key='last_grade_transition_year')
    setting_row.value=str(transition_year); db.session.add(setting_row); db.session.commit()
    return True, f'Grade transition {transition_year} completed; {len(grade9)} Grade 9 learners archived as {label}.'

@app.post('/graduating-classes/transition')
@admin_required
def transition_graduating_class():
    year=request.form.get('year',type=int)
    if not year: flash('Enter the calendar year in which the transition is taking place.','warning'); return redirect(url_for('graduating_classes'))
    ok,message=perform_annual_grade_transition(year); flash(message,'success' if ok else 'warning'); return redirect(url_for('graduating_classes'))

@app.get('/api/cron/annual-grade-transition')
def annual_grade_transition_cron():
    secret=os.environ.get('CRON_SECRET')
    if not secret or request.headers.get('Authorization')!=f'Bearer {secret}': abort(401)
    year=datetime.utcnow().year
    ok,message=perform_annual_grade_transition(year)
    return jsonify(ok=ok,message=message,transition_year=year)

@app.get('/registered-learners.pdf')
@admin_required
def registered_learners_pdf():
    grade=request.args.get('grade','-'); stream=request.args.get('stream','-')
    query=Learner.query.filter_by(status='Active')
    if grade!='-': query=query.filter_by(class_name=grade)
    if stream!='-': query=query.filter_by(stream=stream)
    rows=query.all()
    def adm_key(learner):
        digits=''.join(ch for ch in (learner.admission_no or '') if ch.isdigit())
        return (0,int(digits)) if digits else (1,(learner.admission_no or '').lower())
    rows.sort(key=adm_key)
    data=[[i+1,l.admission_no,l.assessment_no or '-',l.name,l.gender or '-',l.class_name or '-',l.stream or '-',l.parent_phone or '-'] for i,l in enumerate(rows)]
    path=build_pdf('REGISTERED LEARNERS',f'GRADE: {grade}   |   STREAM: {stream}   |   TOTAL LEARNERS: {len(rows)}', ['S/NO.','ADM NO.','ASSESSMENT NO.','LEARNER NAME','GENDER','GRADE','STREAM','PHONE NUMBER'],data,f'registered_learners_{grade}_{stream}.pdf')
    return send_file(path,as_attachment=True,download_name='CBE_PMS_Registered_Learners.pdf')

@app.get('/score-sheet.pdf')
@login_required
def score_sheet_pdf():
    aid=request.args.get('assessment_id',type=int); area=request.args.get('learning_area','-'); grade=request.args.get('grade','-'); stream=request.args.get('stream','-')
    a=Assessment.query.get_or_404(aid)
    if grade=='-' or stream=='-' or area not in LEARNING_AREAS or not eligible(a,grade): abort(400)
    if not assignment_ok(current_user(),area,grade,stream): abort(403)
    learners=Learner.query.filter_by(class_name=grade,stream=stream,status='Active').all()
    learners.sort(key=lambda l:(0,int(''.join(c for c in (l.admission_no or '') if c.isdigit()))) if (l.admission_no or '').isdigit() else (1,l.admission_no or ''))
    rows=[[i+1,l.admission_no,l.name,'','','',''] for i,l in enumerate(learners)]
    meta=f'LEARNING AREA: {area}   |   GRADE: {grade}   |   STREAM: {stream}   |   ASSESSMENT: {a.assessment_type}   |   TERM: {a.term}   |   YEAR: {a.year}'
    ct=ClassTeacherAssignment.query.filter_by(class_name=grade,stream=stream).first(); teacher=Teacher.query.get(ct.teacher_id).name if ct and Teacher.query.get(ct.teacher_id) else '-'; meta += f'   |   CLASS TEACHER: {teacher}'
    path=build_pdf('LEARNING AREA SCORE SHEET',meta,['S/NO.','ADM NO.','LEARNER NAME','SCORE 1','SCORE 2','SCORE 3','SCORE 4'],rows,f'score_sheet_{a.id}_{grade}_{stream}.pdf')
    return send_file(path,as_attachment=True,download_name=f'Score_Sheet_{area.replace(" ","_")}_Grade_{grade}_{stream}.pdf')

@app.get('/score-sheet.xlsx')
@login_required
def score_sheet_xlsx():
    aid=request.args.get('assessment_id',type=int); area=request.args.get('learning_area','-'); grade=request.args.get('grade','-'); stream=request.args.get('stream','-')
    a=Assessment.query.get_or_404(aid)
    if grade=='-' or stream=='-' or area not in LEARNING_AREAS or not eligible(a,grade): abort(400)
    if not assignment_ok(current_user(),area,grade,stream): abort(403)
    learners=Learner.query.filter_by(class_name=grade,stream=stream,status='Active').all()
    learners.sort(key=lambda l:(0,int(l.admission_no)) if (l.admission_no or '').isdigit() else (1,l.admission_no or ''))
    wb=Workbook(); ws=wb.active; ws.title='Score Sheet'; ws.append(['S/NO.','ADM NO.','LEARNER NAME','SCORE 1','SCORE 2','SCORE 3','SCORE 4'])
    for i,l in enumerate(learners,1): ws.append([i,l.admission_no,l.name,'','','',''])
    bio=io.BytesIO(); wb.save(bio); bio.seek(0)
    return send_file(bio,as_attachment=True,download_name=f'Score_Sheet_{area.replace(" ","_")}_Grade_{grade}_{stream}.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.get('/style.css')
def public_stylesheet():
    return send_from_directory(os.path.join(BASE_DIR,'public'),'style.css',mimetype='text/css')

@app.get('/health')
def health():
 try:
  db.session.execute(db.text('SELECT 1'))
  return jsonify(status='ok',database='ok',version='CBE-PMS-WEB-PHASE9')
 except Exception:
  return jsonify(status='error'),503

# Initialize schema for the running web app. The migration utility disables this
# during import so its --dry-run never creates or changes destination tables.
if os.environ.get('CBE_PMS_SKIP_INIT') != '1':
 init()

if __name__=='__main__':
 app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=os.environ.get('FLASK_DEBUG','0')=='1')
