"""Secret-safe observations of an HTTPX final response, not source authenticity.

Counters describe encoded HTTP entity-body bytes only, excluding headers/TLS
and preceding redirect bodies. Prebuffered responses cannot prove wire bytes.
"""
from __future__ import annotations
import re
import codecs
import httpx


def safe_error_kind(exc):
    if isinstance(exc,httpx.TimeoutException): return "TIMEOUT"
    if isinstance(exc,httpx.HTTPStatusError): return "HTTP_STATUS_ERROR"
    if isinstance(exc,httpx.TransportError): return "TRANSPORT_ERROR"
    if isinstance(exc,httpx.HTTPError): return "HTTP_ERROR"
    return "UNVERIFIED_ERROR"


class TransportObservation:
    def __init__(self):
        self._response=None
        self._wire_eligible=False
        self._hook_count=0
        self.http_status=None
        self.content_length=None
        self.length_declaration="UNOBSERVED"
        self.content_encoding="UNOBSERVED"
        self.text_charset_declaration="UNOBSERVED"
        self.header_observation="UNVERIFIED"
        self.wire_bytes=None
        self.decoded_bytes=None
        self.body_read_complete=False
        self.transport_complete=None
        self.content_length_check="UNVERIFIED"
        self.ascii_html_end_marker_observed=None
        self.error_kind=None

    def __repr__(self): return "TransportObservation(REDACTED)"

    def headers_received(self,response,*,via_hook=True):
        if self._response is response: return
        self._response=response
        self._hook_count+=int(via_hook)
        self._wire_eligible=bool(via_hook and not response.is_stream_consumed)
        try:
            status=response.status_code
            self.http_status=status if type(status) is int and 100<=status<=599 else None
            length=response.headers.get("content-length")
            if length is None:
                self.length_declaration="ABSENT"
                self.content_length=None
            elif re.fullmatch(r"[0-9]+",length) and len(length)<=20:
                self.content_length=int(length)
                self.length_declaration="SINGLE_VALID_NONNEGATIVE_INTEGER"
            else:
                self.content_length=None
                self.length_declaration="INVALID_OR_MULTIPLE_UNVERIFIED"
            encoding=response.headers.get("content-encoding", "identity").strip().lower()
            self.content_encoding=encoding if encoding in {"identity","gzip","deflate","br","zstd"} else "OTHER_UNVERIFIED"
            charset=response.charset_encoding
            if charset is None:self.text_charset_declaration="ABSENT_DEFAULT_HTTPX_POLICY"
            else:
                try:
                    codecs.lookup(charset)
                    self.text_charset_declaration="DECLARED_SUPPORTED_BY_LOCAL_CODEC"
                except (LookupError,TypeError):self.text_charset_declaration="DECLARED_UNSUPPORTED_HTTPX_FALLBACK"
            self.header_observation="SAFE_SCALARS_ONLY"
        except Exception:
            self.header_observation="UNVERIFIED"
            self.http_status=self.content_length=None
            self.content_encoding="UNOBSERVED"

    def finish(self,*,response=None,body_read_complete=False,error_kind=None):
        if response is not None and self._response is not response:
            self.headers_received(response,via_hook=False)
        current=self._response
        self.body_read_complete=bool(body_read_complete)
        self.error_kind=error_kind
        if current is not None:
            if self._wire_eligible:
                try:
                    count=current.num_bytes_downloaded
                    if type(count) is int and count>=0:self.wire_bytes=count
                except Exception:pass
            if body_read_complete:
                try:
                    data=current.content
                    self.decoded_bytes=len(data)
                    self.ascii_html_end_marker_observed=bool(re.search(br"</html\s*>",data,re.I))
                except Exception:pass
        if self.content_length is not None and self.wire_bytes is not None:
            self.content_length_check=("MATCH" if self.content_length==self.wire_bytes else
                                       "MISMATCH" if body_read_complete else "PARTIAL_NOT_COMPLETE")
        elif self.length_declaration=="ABSENT":self.content_length_check="ABSENT"
        else:self.content_length_check="UNVERIFIED"
        if not body_read_complete:self.transport_complete=False
        elif self.content_length_check=="MISMATCH":self.transport_complete=False
        elif self.wire_bytes is None or self.length_declaration=="INVALID_OR_MULTIPLE_UNVERIFIED":self.transport_complete=None
        else:self.transport_complete=True
        self._response=None  # Never retain URL/header/body-bearing objects.
        return self.safe_record()

    def release_private_response(self):
        self._response=None

    def safe_record(self):
        return {"schema":"HTTP_TRANSPORT_OBSERVATION_V001_CANDIDATE",
            "response_scope":("FINAL_RESPONSE_ONLY_ENCODED_BODY_NO_HEADERS_OR_TLS" if self.body_read_complete
                              else "LAST_OBSERVED_RESPONSE_NOT_CONFIRMED_FINAL"),
            "response_finality":("RETURNED_RESPONSE" if self.body_read_complete else "UNVERIFIED"),
            "http_status":self.http_status,"wire_bytes":self.wire_bytes,"decoded_bytes":self.decoded_bytes,
            "wire_count_status":"OBSERVED_HTTPX_COUNTER" if self.wire_bytes is not None else "UNVERIFIED_NOT_OBSERVED",
            "wire_count_extent":"COMPLETE_BODY" if self.body_read_complete else "PARTIAL_OR_UNOBSERVED",
            "body_read_complete":self.body_read_complete,"transport_complete":self.transport_complete,
            "content_length":self.content_length,"length_declaration":self.length_declaration,
            "content_encoding":self.content_encoding,"text_charset_declaration":self.text_charset_declaration,
            "content_decoding_integrity":"NOT_INDEPENDENTLY_VERIFIED_HTTPX_BEHAVIOR_ONLY",
            "content_length_check":self.content_length_check,
            "header_observation":self.header_observation,"response_hooks_observed":self._hook_count,
            "ascii_html_end_marker_observed":self.ascii_html_end_marker_observed,"error_kind":self.error_kind,
            "document_complete":"UNVERIFIED_MARKER_IS_NOT_COMPLETENESS",
            "official_authenticity":"UNVERIFIED","production_go":False}
