"""Create synthetic vectors without importing the prototype under test."""
from pathlib import Path
import base64
import json

HERE = Path(__file__).resolve().parent
cases = []

def add(name, left, right, raw, canonical, semantic, *, ls="VALID", rs="VALID", lc="AVAILABLE", rc="AVAILABLE", lw=None, rw=None, settings=None, background=None, cl=None, cr=None):
    if isinstance(left, str): left = left.encode("utf-8")
    if isinstance(right, str): right = right.encode("utf-8")
    row = {"id": name, "synthetic": True, "left_b64": base64.b64encode(left).decode(), "right_b64": base64.b64encode(right).decode(), "settings": settings or {}, "expected": {"raw": raw, "canonical": canonical, "semantic": semantic, "left_status": ls, "right_status": rs, "left_canonical_status": lc, "right_canonical_status": rc, "left_warnings": lw or [], "right_warnings": rw or []}}
    if background: row["background"] = background
    if cl is not None: row["canonical_utf8_left"] = cl
    if cr is not None: row["canonical_utf8_right"] = cr
    cases.append(row)

add("identical_object", '{"b":2,"a":1}', '{"b":2,"a":1}', True, True, True, cl='{"a":1,"b":2}', cr='{"a":1,"b":2}')
add("key_order", '{"b":2,"a":1}', '{"a":1,"b":2}', False, True, True, cl='{"a":1,"b":2}', cr='{"a":1,"b":2}')
add("whitespace_newline", '{\n "a" : 1\n}\n', '{"a":1}', False, True, True, cl='{"a":1}', cr='{"a":1}')
add("unicode_escape", '{"x":"\\u65e5"}', '{"x":"日"}', False, True, True, cl='{"x":"日"}', cr='{"x":"日"}')
add("unicode_no_NFC", '"é"', '"e\u0301"', False, False, False, cl='"é"', cr='"e\u0301"')
add("BG_B_NUMERIC_01", '{"n":1}', '{"n":1.0}', False, False, True, background="SYNTHETIC_NUMERIC_REPRESENTATION_NOT_REAL_RECORD", cl='{"n":1}', cr='{"n":1.0}')
add("BG_B_NUMERIC_02", '{"n":1e-7}', '{"n":0.0000001}', False, True, True, background="SYNTHETIC_NUMERIC_REPRESENTATION_NOT_REAL_RECORD", cl='{"n":1e-07}', cr='{"n":1e-07}')
for i, (a,b,c) in enumerate([
    ('{"2":"two","10":"ten"}', '{"10":"ten","2":"two"}', '{"10":"ten","2":"two"}'),
    ('{"12":12,"1":1,"0":0}', '{"0":0,"1":1,"12":12}', '{"0":0,"1":1,"12":12}'),
    ('{"x":{"2":2,"10":10},"1":true}', '{"1":true,"x":{"10":10,"2":2}}', '{"1":true,"x":{"10":10,"2":2}}'),
    ('{"meta":"synth","2":2,"01":1,"1":1}', '{"1":1,"2":2,"meta":"synth","01":1}', '{"01":1,"1":1,"2":2,"meta":"synth"}')], 1):
    add("BG_A_DIGIT_KEYS_0"+str(i), a,b,False,True,True,background="SYNTHETIC_DIGIT_KEY_ORDER_NOT_REAL_RECORD",cl=c,cr=c)
add("numeric_exponent_integer", '1', '1e0', False, False, True, cl='1', cr='1.0')
add("negative_zero", '-0.0', '0.0', False, False, True, cl='-0.0', cr='0.0')
add("bool_is_not_number", 'true', '1', False, False, False, cl='true', cr='1')
add("bool_false", 'false', 'false', True, True, True, cl='false', cr='false')
add("null_is_not_string", 'null', '"null"', False, False, False, cl='null', cr='"null"')
add("list_order", '[1,2]', '[2,1]', False, False, False, cl='[1,2]', cr='[2,1]')
add("list_length", '[]', '[null]', False, False, False, cl='[]', cr='[null]')
add("container_type", '[]', '{}', False, False, False, cl='[]', cr='{}')
add("nested_values", '{"a":[true,null,{"x":1}]}', '{"a":[true,null,{"x":1.0}]}', False, False, True, cl='{"a":[true,null,{"x":1}]}', cr='{"a":[true,null,{"x":1.0}]}')
add("tampered_value", '{"a":1}', '{"a":2}', False, False, False, cl='{"a":1}', cr='{"a":2}')
add("different_object_keys", '{"a":1}', '{"b":1}', False, False, False, cl='{"a":1}', cr='{"b":1}')
for name,left in [("duplicate_key",'{"a":1,"a":2}'),("duplicate_nested",'{"x":{"a":1,"a":1}}'),("duplicate_escaped_key",'{"a":1,"\\u0061":1}')]:
    add(name,left,'{}',False,None,None,ls="DUPLICATE_KEY",lc="UNAVAILABLE_INPUT",cr='{}')
add("duplicate_both_identical",'{"a":1,"a":1}','{"a":1,"a":1}',True,None,None,ls="DUPLICATE_KEY",rs="DUPLICATE_KEY",lc="UNAVAILABLE_INPUT",rc="UNAVAILABLE_INPUT")
for name,left in [("invalid_json",'{"a":}'),("trailing_content",'{} x'),("empty_input",''),("BOM_not_stripped",b'\xef\xbb\xbf{}'),("invalid_number_syntax",'.5')]:
    add(name,left,'{}',False,None,None,ls="INVALID_JSON",lc="UNAVAILABLE_INPUT",cr='{}')
add("invalid_UTF8",b'\xff',b'{}',False,None,None,ls="INVALID_UTF8",lc="UNAVAILABLE_INPUT",cr='{}')
for token in ['NaN','Infinity','-Infinity']:
    add("nonfinite_"+token,token,'null',False,None,None,ls="NON_FINITE_LITERAL",lc="UNAVAILABLE_INPUT",cr='null')
add("finite_decimal_float_overflow",'1e400','10e399',False,None,True,lc="UNAVAILABLE_FLOAT_RANGE",rc="UNAVAILABLE_FLOAT_RANGE")
add("float_underflow",'1e-400','0.0',False,True,False,lw=["CANONICAL_DECIMAL_ROUNDING"],cl='0.0',cr='0.0')
add("float_rounding_collision",'0.10000000000000001','0.1',False,True,False,lw=["CANONICAL_DECIMAL_ROUNDING"],cl='0.1',cr='0.1')
add("large_integer_value_changed",'9007199254740993','9007199254740992',False,False,False,cl='9007199254740993',cr='9007199254740992')
add("unpaired_surrogate",'"\\ud800"','null',False,None,None,ls="INVALID_UNICODE_SCALAR",lc="UNAVAILABLE_INPUT",cr='null')
add("unpaired_surrogate_key",'{"\\udfff":1}','{}',False,None,None,ls="INVALID_UNICODE_SCALAR",lc="UNAVAILABLE_INPUT",cr='{}')
add("valid_surrogate_pair",'"\\ud83d\\ude80"','"🚀"',False,True,True,cl='"🚀"',cr='"🚀"')
add("byte_budget",'{"a":1}','{}',False,None,None,ls="RESOURCE_LIMIT",lc="UNAVAILABLE_INPUT",settings={"max_bytes":2},cr='{}')
add("depth_budget",'[[0]]','[0]',False,None,None,ls="RESOURCE_LIMIT",lc="UNAVAILABLE_INPUT",settings={"max_depth":1},cr='[0]')
add("number_token_budget",'1'*257,'1',False,None,None,ls="RESOURCE_LIMIT",lc="UNAVAILABLE_INPUT",cr='1')
add("parser_recursion_budget",'['*1500+'0'+']'*1500,'null',False,None,None,ls="RESOURCE_LIMIT",lc="UNAVAILABLE_INPUT",cr='null')
add("decimal_exponent_limit",'1e999999999999999999999999999999','1',False,None,None,ls="RESOURCE_LIMIT",lc="UNAVAILABLE_INPUT",cr='1')
(HERE / 'fixtures.json').write_text(json.dumps({"classification":"SYNTHETIC_ONLY_NO_REAL_EVENTS", "cases":cases},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({"synthetic_cases":len(cases),"real_records_received":0}))
