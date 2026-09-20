"""Fixed postday result evidence; no withdrawal classification or scheduler."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
import httpx


def capture(out: Path) -> list[dict]:
    if dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date() <= dt.date(2026, 9, 18):
        raise RuntimeError('TARGET_DATE_NOT_ELAPSED')
    out.mkdir(parents=True, exist_ok=False)
    reports = []
    for race in range(1, 13):
        url = f'https://www.boatrace.jp/owpc/pc/race/raceresult?hd=20260918&jcd=07&rno={race}'
        item = {'target_date':'2026-09-18','venue_code':'07','race_no':race,
                'requested_url':url,'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),
                'original_incident_response':False,'review_only':True,
                'withdrawal_classification':'NOT_PERFORMED','body_complete':False,
                'source_effective_at':None,'body_filename':None,'error':None}
        # Exclusive per-attempt START on disk before requesting. This is not
        # proof of a later successful HTTP request or of physical durability.
        start = out / f'{race:02d}_start.json'
        with start.open('x',encoding='utf-8') as file:
            json.dump(item,file,ensure_ascii=False,sort_keys=True)
        chunks = bytearray()
        received = False
        before = time.monotonic()
        try:
            with httpx.Client(timeout=12.0,trust_env=False,follow_redirects=False,
                    headers={'User-Agent':'GamagoriCompletionReview/1.1','Accept-Encoding':'identity'}) as client:
                with client.stream('GET',url) as response:
                    received = True
                    item.update(http_status=response.status_code,response_url=str(response.url),
                        received_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                        headers={k:response.headers[k][:1024] for k in
                            ('content-type','content-encoding','content-length','date','etag','last-modified')
                            if k in response.headers})
                    for chunk in response.iter_raw():
                        room=1_000_000-len(chunks)
                        chunks.extend(chunk[:room])
                        if len(chunk)>room:
                            item['error']='BODY_LIMIT_EXCEEDED'
                            break
                    else:
                        item['body_complete']=True
        except Exception as exc:
            item['error']=type(exc).__name__
        if received:
            filename=f'20260918_{race:02d}_raceresult.html'
            body=bytes(chunks)
            with (out/filename).open('xb') as file:
                file.write(body)
            item.update(body_filename=filename,body_sha256=hashlib.sha256(body).hexdigest(),
                        stored_body_bytes=len(body))
            item['body_readback_match']=hashlib.sha256((out/filename).read_bytes()).hexdigest()==item['body_sha256']
        item.update(finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                    elapsed_seconds=time.monotonic()-before)
        reports.append(item)
        with (out/f'{race:02d}_end.json').open('x',encoding='utf-8') as file:
            json.dump(item,file,ensure_ascii=False,sort_keys=True)
    with (out/'manifest.json').open('x',encoding='utf-8') as file:
        json.dump(reports,file,ensure_ascii=False,indent=2,allow_nan=False)
    return reports


if __name__=='__main__':
    result=capture(Path('review_artifacts/stage14_results'))
    print(json.dumps({'planned':12,'received':sum('http_status' in x for x in result),
        'http200':sum(x.get('http_status')==200 for x in result),
        'complete':sum(x['body_complete'] for x in result),'review_only':True}))
