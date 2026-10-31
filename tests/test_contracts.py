import pytest
from dataclasses import replace
from qualityrelay17.contracts import Evidence,sign_evidence,signature_valid
from qualityrelay17.ledger import EvidenceLedger

def make():return Evidence('id','part','s1','PHONE_IMAGE','TEST_FIXTURE','r1',123,'clear',{},calibration_id='cal')

def test_signature_accepts_correct_key():
    a=sign_evidence(make(),'secret');assert signature_valid(a,{'s1':'secret'})

def test_signature_rejects_wrong_key():
    a=sign_evidence(make(),'secret');assert not signature_valid(a,{'s1':'bad'})

def test_payload_tamper():
    a=sign_evidence(make(),'secret');bad=replace(a,payload={'defect':'no'});assert not signature_valid(bad,{'s1':'secret'})

def test_signature_not_proof_of_real_photo():
    a=sign_evidence(make(),'secret');assert a.origin=='TEST_FIXTURE'

def test_ledger_write_and_acl():
    l=EvidenceLedger();l.append(sign_evidence(make(),'secret'))
    assert len(l.get_specimen('part',requester='inspector',allowed_stations={'s1'}))==1
    assert l.get_specimen('part',requester='inspector',allowed_stations=set())==[]

def test_ledger_no_anonymous_reads():
    l=EvidenceLedger();l.append(sign_evidence(make(),'secret'))
    with pytest.raises(PermissionError):l.get_specimen('part')

def test_ledger_duplicate_is_rejected():
    l=EvidenceLedger();e=sign_evidence(make(),'secret');l.append(e)
    with pytest.raises(ValueError):l.append(e)

def test_ledger_summary_redacts():
    l=EvidenceLedger();a=sign_evidence(replace(make(),payload={'private_raw_image':'binary','validated':True}),'secret');l.append(a)
    data=l.get_specimen('part',requester='chief_readonly',allowed_stations={'s1'})
    assert 'private_raw_image' not in data[0]['payload']
