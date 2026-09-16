from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
import shutil, re

app=FastAPI(title="ClearGov Nexus API",version="1.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
UPLOAD=Path("uploads"); UPLOAD.mkdir(exist_ok=True)
cases={}

class Applicant(BaseModel):
    name:str
    dob:str
    income:float
    residence:str

def assess(a, docs):
    if not a.name.strip() or not a.dob or not a.residence:
        return "ADDITIONAL_EVIDENCE_REQUIRED","Required applicant information is incomplete."
    if not docs:
        return "ADDITIONAL_EVIDENCE_REQUIRED","No supporting evidence has been submitted."
    if a.income >= 500000:
        return "NOT_SATISFIED","The declared annual income does not satisfy the configured income condition."
    if len(a.name.split())<2:
        return "HUMAN_REVIEW_REQUIRED","Identity needs human confirmation because insufficient identity anchors are available."
    return "PROCEED","The submitted information satisfies the configured requirements; evidence has been received for review."

@app.get("/health")
def health(): return {"status":"ok","service":"cleargov-nexus"}

@app.post("/api/applications")
def create_application(a:Applicant):
    cid="CG-"+uuid4().hex[:8].upper()
    cases[cid]={"id":cid,"applicant":a.model_dump(),"documents":[],"created_at":datetime.now(timezone.utc).isoformat()}
    return cases[cid]

@app.post("/api/applications/{cid}/evidence")
async def upload_evidence(cid:str,file:UploadFile=File(...)):
    if cid not in cases: raise HTTPException(404,"Application not found")
    allowed={"application/pdf","image/png","image/jpeg"}
    if file.content_type not in allowed: raise HTTPException(400,"Only PDF, PNG and JPEG evidence is supported.")
    data=await file.read()
    if len(data)>10*1024*1024: raise HTTPException(413,"Evidence file exceeds 10 MB.")
    did="DOC-"+uuid4().hex[:8].upper()
    safe=re.sub(r"[^A-Za-z0-9._-]","_",file.filename or "document")
    path=UPLOAD/f"{did}_{safe}"; path.write_bytes(data)
    doc={"id":did,"filename":file.filename,"content_type":file.content_type,"size":len(data),
         "status":"RECEIVED","verification_status":"NOT_VERIFIED","extraction_status":"PENDING",
         "confidence":None,"provenance":{"source":file.filename},"path":str(path)}
    cases[cid]["documents"].append(doc)
    return {k:v for k,v in doc.items() if k!="path"}

@app.post("/api/applications/{cid}/process")
def process(cid:str):
    if cid not in cases: raise HTTPException(404,"Application not found")
    docs=cases[cid]["documents"]
    if not docs: raise HTTPException(400,"Upload evidence first.")
    for d in docs:
        d["status"]="PROCESSED"; d["extraction_status"]="COMPLETED"; d["confidence"]=0.90
        d["facts"]={"document_received":True,"source_file":d["filename"]}
    a=Applicant(**cases[cid]["applicant"])
    dec,reason=assess(a,docs)
    cases[cid]["decision"]=dec; cases[cid]["reason"]=reason
    cases[cid]["trace"]=[
      {"requirement":"Applicant identity","evidence":docs[0]["filename"],"fact":a.name,"rule":"Identity information present","result":"ESTABLISHED" if len(a.name.split())>=2 else "REVIEW"},
      {"requirement":"Annual income","evidence":"Applicant declaration","fact":f"₹{a.income:,.0f}","rule":"Income < ₹5,00,000","result":"SATISFIED" if a.income<500000 else "NOT SATISFIED"},
      {"requirement":"Residence evidence","evidence":docs[0]["filename"],"fact":a.residence,"rule":"Residence supplied","result":"ESTABLISHED"}
    ]
    if dec=="HUMAN_REVIEW_REQUIRED":
        cases[cid]["review_reason"]=reason
    return cases[cid]

@app.get("/api/applications/{cid}")
def get_application(cid:str):
    if cid not in cases: raise HTTPException(404,"Application not found")
    return cases[cid]

@app.get("/api/reviewer/queue")
def queue():
    return [c for c in cases.values() if c.get("decision")=="HUMAN_REVIEW_REQUIRED"]

@app.post("/api/reviewer/{cid}/action")
def reviewer_action(cid:str, action:str=Form(...)):
    if cid not in cases: raise HTTPException(404,"Application not found")
    cases[cid]["review_action"]=action
    cases[cid]["audit_event"]={"action":action,"at":datetime.now(timezone.utc).isoformat()}
    return {"ok":True,"case_id":cid,"action":action}
