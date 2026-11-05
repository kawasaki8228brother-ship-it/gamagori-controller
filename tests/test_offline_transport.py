"""Hermetic final-response accounting with invented HTTPX transport streams."""
import asyncio
import datetime as dt
import gzip
import json
from unittest.mock import AsyncMock
import httpx
import pytest
from models import JST
from official import OfficialDataFetcher
from raceindex_status import IndexFailure


class Chunks(httpx.AsyncByteStream):
    def __init__(self, parts, error=None):self.parts,self.error=parts,error
    async def __aiter__(self):
        for part in self.parts:yield part
        if self.error is not None:raise self.error


def index_html():
    return ('<html><table><tr><th>レース</th><th>投票締切</th></tr>'+
            ''.join(f'<tr><td>{n}R</td><td>13:{n:02d} 投票</td></tr>' for n in range(1,13))+'</table></html>').encode()


async def make(handler, retries=1):
    obj=OfficialDataFetcher(max_retries=retries,backoff_seconds=0)
    await obj.client.aclose()
    obj.client=httpx.AsyncClient(transport=httpx.MockTransport(handler),follow_redirects=True,
                               event_hooks={'response':[obj._observe_transport_headers]})
    return obj


@pytest.mark.asyncio
@pytest.mark.parametrize('encoding',['identity','gzip'])
async def test_encoded_and_decoded_body_bytes_are_distinct_and_exact(encoding):
    plain=b'<html>synthetic body</html>'
    wire=gzip.compress(plain) if encoding=='gzip' else plain
    obj=await make(lambda request:httpx.Response(200,headers={'Content-Length':str(len(wire)),'Content-Encoding':encoding},stream=Chunks([wire[:3],wire[3:]])))
    try:
        text,when=await obj._get_text('https://synthetic.invalid/example')
        record=obj.last_transport_observation
        assert text==plain.decode() and dt.datetime.fromisoformat(when).tzinfo is not None
        assert record['http_status']==200 and record['wire_bytes']==len(wire) and record['decoded_bytes']==len(plain)
        assert record['body_read_complete'] and record['transport_complete'] is True
        assert record['content_length_check']=='MATCH' and record['ascii_html_end_marker_observed'] is True
        assert not obj._transport_tokens
    finally:await obj.close()


@pytest.mark.asyncio
async def test_partial_body_preserves_status_but_never_counts_decoded_as_wire():
    obj=await make(lambda request:httpx.Response(200,headers={'Content-Length':'99'},stream=Chunks([b'part'],httpx.ReadError('PRIVATE_READ_MESSAGE'))))
    try:
        with pytest.raises(IndexFailure):await obj._get_text('https://synthetic.invalid/')
        record=obj.last_transport_observation
        assert record['http_status']==200 and record['wire_bytes']==4
        assert record['decoded_bytes'] is None and record['body_read_complete'] is False and record['transport_complete'] is False
        assert record['content_length_check']=='PARTIAL_NOT_COMPLETE'
        assert not obj._transport_tokens
    finally:await obj.close()


@pytest.mark.asyncio
async def test_content_length_mismatch_cannot_enter_parser():
    obj=await make(lambda request:httpx.Response(200,headers={'Content-Length':'100'},stream=Chunks([index_html()])))
    try:
        with pytest.raises(IndexFailure) as caught:await obj.fetch_race_index(dt.datetime(2099,1,7,12,tzinfo=JST))
        assert caught.value.kind=='HTTP_FETCH_FAILED'
        assert obj.last_transport_observation['content_length_check']=='MISMATCH'
        assert obj.last_raceindex_diagnostic['html_parse_status']=='NOT_ATTEMPTED_TRANSPORT_FAILURE'
    finally:await obj.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('status',[403,404,500])
async def test_http_status_does_not_mean_parse_success(status):
    obj=await make(lambda request:httpx.Response(status,stream=Chunks([b'PRIVATE_HTTP_BODY'])))
    try:
        with pytest.raises(IndexFailure):await obj.fetch_race_index(dt.datetime(2099,1,7,12,tzinfo=JST))
        record=obj.last_transport_observation
        assert record['http_status']==status and record['body_read_complete'] is True
        assert obj.last_raceindex_diagnostic['html_parse_status']=='NOT_ATTEMPTED_TRANSPORT_FAILURE'
    finally:await obj.close()


@pytest.mark.asyncio
async def test_complete_transfer_with_missing_html_end_is_not_parse_success():
    obj=await make(lambda request:httpx.Response(200,stream=Chunks([b'<html>PRIVATE_EMPTY_TABLE'])))
    try:
        with pytest.raises(IndexFailure):await obj.fetch_race_index(dt.datetime(2099,1,7,12,tzinfo=JST))
        d=obj.last_raceindex_diagnostic
        assert d['transport']['transport_complete'] is True and d['transport']['ascii_html_end_marker_observed'] is False
        assert d['html_parse_status']=='REJECTED' and d['official_authenticity']=='UNVERIFIED'
    finally:await obj.close()


@pytest.mark.asyncio
async def test_prebuffered_mock_body_has_unknown_wire_counter():
    obj=await make(lambda request:httpx.Response(200,content=b'example'))
    try:
        await obj._get_text('https://synthetic.invalid/')
        r=obj.last_transport_observation
        assert r['wire_bytes'] is None and r['decoded_bytes']==7 and r['transport_complete'] is None
        assert r['wire_count_status']=='UNVERIFIED_NOT_OBSERVED'
    finally:await obj.close()


@pytest.mark.asyncio
async def test_empty_stream_can_be_complete_without_being_html():
    obj=await make(lambda request:httpx.Response(200,headers={'Content-Length':'0'},stream=Chunks([])))
    try:
        text,_=await obj._get_text('https://synthetic.invalid/')
        r=obj.last_transport_observation
        assert text=='' and r['wire_bytes']==r['decoded_bytes']==0 and r['transport_complete'] is True
        assert r['ascii_html_end_marker_observed'] is False
    finally:await obj.close()


@pytest.mark.asyncio
async def test_redirect_counter_scope_is_only_final_response():
    def handler(request):
        if request.url.path=='/first':return httpx.Response(302,headers={'Location':'/last'},stream=Chunks([b'first']))
        return httpx.Response(200,headers={'Content-Length':'4'},stream=Chunks([b'last']))
    obj=await make(handler)
    try:
        text,_=await obj._get_text('https://synthetic.invalid/first')
        r=obj.last_transport_observation
        assert text=='last' and r['http_status']==200 and r['wire_bytes']==4
        assert r['response_hooks_observed']==2 and r['response_scope'].startswith('FINAL_RESPONSE_ONLY')
    finally:await obj.close()


@pytest.mark.asyncio
async def test_invalid_length_and_unknown_encoding_are_unverified_safe_scalars():
    obj=await make(lambda request:httpx.Response(200,headers={'Content-Length':'PRIVATE_LENGTH','Content-Encoding':'PRIVATE_ENCODING'},stream=Chunks([b'body'])))
    try:
        await obj._get_text('https://synthetic.invalid/')
        r=obj.last_transport_observation
        assert r['content_length'] is None and r['length_declaration']=='INVALID_OR_MULTIPLE_UNVERIFIED'
        assert r['content_encoding']=='OTHER_UNVERIFIED' and r['transport_complete'] is None
        assert 'PRIVATE' not in json.dumps(r)
    finally:await obj.close()


@pytest.mark.asyncio
async def test_safe_logs_and_retries_never_echo_url_body_proxy_or_header(caplog):
    obj=await make(lambda request:(_ for _ in ()).throw(httpx.ProxyError('PRIVATE_PROXY_CREDENTIAL')) ,retries=2)
    try:
        with caplog.at_level('INFO'),pytest.raises(IndexFailure):
            await obj._get_text('https://PRIVATE_USER:PRIVATE_PASSWORD@synthetic.invalid/PRIVATE_PATH')
        assert 'PRIVATE_' not in caplog.text and 'https://' not in caplog.text
        assert obj.last_transport_observation['http_status'] is None
        assert obj.last_transport_observation['error_kind']=='TRANSPORT_ERROR'
        assert not obj._transport_tokens
    finally:await obj.close()


@pytest.mark.asyncio
async def test_successful_parse_has_separate_transport_and_parse_fields():
    body=index_html()
    obj=await make(lambda request:httpx.Response(200,headers={'Content-Length':str(len(body))},stream=Chunks([body])))
    try:
        result=await obj.fetch_race_index(dt.datetime(2099,1,7,12,tzinfo=JST))
        d=obj.last_raceindex_diagnostic
        assert len(result.races)==12 and d['transport']['http_status']==200
        assert d['html_parse_status']=='SUCCEEDED' and d['parsed_race_count']==12
        assert d['official_authenticity']=='UNVERIFIED' and d['production_go'] is False
    finally:await obj.close()


@pytest.mark.asyncio
async def test_mocked_get_retry_api_is_compatible():
    obj=OfficialDataFetcher(max_retries=2,backoff_seconds=0)
    obj.client.get=AsyncMock(side_effect=httpx.ProxyError('PRIVATE_PROXY'))
    try:
        with pytest.raises(IndexFailure):await obj._get_text('https://synthetic.invalid/')
        assert obj.client.get.await_count==2 and obj.last_transport_observation['http_status'] is None
    finally:await obj.close()


@pytest.mark.asyncio
async def test_contexts_do_not_attach_concurrent_other_body_to_race_parse():
    body=index_html()
    async def handler(request):
        if request.url.path.endswith('raceindex'):await asyncio.sleep(0)
        data=body if request.url.path.endswith('raceindex') else b'x'
        return httpx.Response(200,headers={'Content-Length':str(len(data))},stream=Chunks([data]))
    obj=await make(handler)
    try:
        await asyncio.gather(obj.fetch_race_index(dt.datetime(2099,1,7,12,tzinfo=JST)),obj._get_text('https://synthetic.invalid/other'))
        assert obj.last_raceindex_diagnostic['transport']['decoded_bytes']==len(body)
        assert obj.last_raceindex_diagnostic['html_parse_status']=='SUCCEEDED'
        assert not obj._transport_tokens
    finally:await obj.close()


@pytest.mark.asyncio
async def test_cancelled_body_records_observation_then_cleans_private_objects():
    started=asyncio.Event()
    captured=[]
    class Blocking(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'part'
            started.set()
            await asyncio.Event().wait()
    obj=await make(lambda request:httpx.Response(200,stream=Blocking()))
    async def capture(response):
        captured.append(obj._transport_tokens[response.request.extensions['health_observation_token']])
    obj.client.event_hooks['response'].append(capture)
    try:
        task=asyncio.create_task(obj._get_text('https://synthetic.invalid/'))
        await asyncio.wait_for(started.wait(),1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        r=obj.last_transport_observation
        assert r['error_kind']=='CANCELLED' and r['http_status']==200 and r['wire_bytes']==4
        assert r['body_read_complete'] is False and r['response_finality']=='UNVERIFIED'
        assert captured and captured[0]._response is None and not obj._transport_tokens
    finally:await obj.close()


@pytest.mark.asyncio
async def test_invalid_gzip_is_failure_not_successful_decoding():
    raw=b'PRIVATE_INVALID_GZIP'
    obj=await make(lambda request:httpx.Response(200,headers={'Content-Encoding':'gzip','Content-Length':str(len(raw))},stream=Chunks([raw])))
    try:
        with pytest.raises(IndexFailure):await obj._get_text('https://synthetic.invalid/')
        r=obj.last_transport_observation
        assert r['http_status']==200 and r['decoded_bytes'] is None
        assert r['body_read_complete'] is False and r['transport_complete'] is False
        assert 'PRIVATE' not in json.dumps(r)
    finally:await obj.close()


@pytest.mark.asyncio
async def test_unknown_charset_is_not_echoed_and_httpx_fallback_remains_explicit():
    body='合成'.encode()
    obj=await make(lambda request:httpx.Response(200,headers={'Content-Type':'text/html; charset=PRIVATE_UNKNOWN_CHARSET'},stream=Chunks([body])))
    try:
        text,_=await obj._get_text('https://synthetic.invalid/')
        r=obj.last_transport_observation
        assert text=='合成' and r['decoded_bytes']==len(body)
        assert r['text_charset_declaration']=='DECLARED_UNSUPPORTED_HTTPX_FALLBACK'
        assert 'PRIVATE' not in json.dumps(r)
    finally:await obj.close()


@pytest.mark.asyncio
async def test_timeout_before_headers_has_no_fabricated_status_or_body():
    obj=await make(lambda request:(_ for _ in ()).throw(httpx.ReadTimeout('PRIVATE_TIMEOUT')))
    try:
        with pytest.raises(IndexFailure):await obj._get_text('https://synthetic.invalid/')
        r=obj.last_transport_observation
        assert r['error_kind']=='TIMEOUT' and r['http_status'] is None
        assert r['wire_bytes'] is None and r['decoded_bytes'] is None
    finally:await obj.close()


@pytest.mark.asyncio
async def test_success_diagnostic_namespace_has_no_secret_url_header_or_body(caplog):
    obj=await make(lambda request:httpx.Response(200,headers={'X-Private':'PRIVATE_HEADER'},stream=Chunks([b'PRIVATE_BODY'])))
    try:
        with caplog.at_level('INFO'):
            await obj._get_text('https://PRIVATE_USER:PRIVATE_PASSWORD@synthetic.invalid/PRIVATE_PATH')
        diagnostics=[r.getMessage() for r in caplog.records if r.name=='gamagori-controller']
        assert diagnostics and all('PRIVATE_' not in text and 'https://' not in text for text in diagnostics)
        assert 'PRIVATE_' not in json.dumps(obj.last_transport_observation)
        # HTTPX's pre-existing Request logger is a separate logging-policy scope.
    finally:await obj.close()


@pytest.mark.asyncio
async def test_duplicate_content_length_is_unverified_not_silently_normalized():
    obj=await make(lambda request:httpx.Response(200,headers=[('Content-Length','4'),('Content-Length','4')],stream=Chunks([b'body'])))
    try:
        await obj._get_text('https://synthetic.invalid/')
        r=obj.last_transport_observation
        assert r['wire_bytes']==4 and r['content_length'] is None
        assert r['length_declaration']=='INVALID_OR_MULTIPLE_UNVERIFIED' and r['transport_complete'] is None
    finally:await obj.close()


@pytest.mark.asyncio
async def test_html_end_marker_absence_does_not_assert_parse_failure_or_completeness():
    body=index_html().replace(b'</html>',b'')
    obj=await make(lambda request:httpx.Response(200,stream=Chunks([body])))
    try:
        await obj.fetch_race_index(dt.datetime(2099,1,7,12,tzinfo=JST))
        r=obj.last_raceindex_diagnostic
        assert r['html_parse_status']=='SUCCEEDED'
        assert r['transport']['ascii_html_end_marker_observed'] is False
        assert r['transport']['document_complete']=='UNVERIFIED_MARKER_IS_NOT_COMPLETENESS'
    finally:await obj.close()
