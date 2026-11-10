import copy
import io
import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from foundation_refrigeration import (
    plant_model,
    process_safety,
    projection,
    safety_limits,
    thermo,
)
from foundation_refrigeration.projection import ProjectionError
from foundation_refrigeration.tools import run
from foundation_refrigeration_bridge import server
from foundation_refrigeration_bridge.server import (
    MAX_ID_CHARS,
    MAX_ID_INTEGER,
    MAX_OUTPUT_BYTES,
    PROTOCOL,
    Bridge,
    encode_response,
    serve,
)

INIT = {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": {"protocolVersion": PROTOCOL}}
CONVERT = {"name": "convert_temperature", "arguments": {"temperature": {"value": 0, "unit": "degC"}, "to_unit": "K"}}


def ready():
    bridge = Bridge()
    if "result" not in bridge.dispatch(INIT):
        raise AssertionError("Bridge did not initialise")
    return bridge


def shipped(name, schema):
    data, sha = projection.load(name, schema)
    return copy.deepcopy(data), sha


def frame(response):
    raw = encode_response(response)
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        raise AssertionError("Response is not a single newline-terminated frame")
    return json.loads(raw)


class BrokenSink:
    def __init__(self, error):
        self.error = error

    def write(self, data):
        raise self.error

    def flush(self):
        raise self.error


class GapRef001OutputLimitTests(unittest.TestCase):
    def test_gap_ref_001_oversized_response_is_withheld_with_32002(self):
        oversized = {"jsonrpc": "2.0", "id": 41, "result": {"blob": "x" * (MAX_OUTPUT_BYTES + 1)}}
        reply = frame(oversized)
        self.assertEqual(reply, {"jsonrpc": "2.0", "id": 41, "error": {
            "code": -32002, "message": "Output frame exceeds bridge byte limit; result withheld"}})
        self.assertLess(len(encode_response(oversized)), 512)

    def test_gap_ref_001_response_at_the_limit_is_sent(self):
        envelope = {"jsonrpc": "2.0", "id": 1, "result": {"blob": ""}}
        overhead = len(encode_response(envelope)) - 1
        exact = {"jsonrpc": "2.0", "id": 1, "result": {"blob": "x" * (MAX_OUTPUT_BYTES - overhead)}}
        self.assertEqual(len(encode_response(exact)), MAX_OUTPUT_BYTES + 1)
        self.assertEqual(frame(exact)["result"], exact["result"])
        over = {"jsonrpc": "2.0", "id": 1, "result": {"blob": "x" * (MAX_OUTPUT_BYTES - overhead + 1)}}
        self.assertEqual(frame(over)["error"]["code"], -32002)

    def test_gap_ref_001_serve_withholds_an_oversized_tool_result(self):
        payload = b"".join(json.dumps(f).encode() + b"\n" for f in (
            INIT, {"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": CONVERT}))
        huge = {"isError": False, "structuredContent": {"blob": "x" * (MAX_OUTPUT_BYTES + 1)}}
        sink = io.BytesIO()
        with mock.patch.object(server, "_tool_result", return_value=huge):
            self.assertEqual(serve(io.BytesIO(payload), sink), 0)
        reply = json.loads(sink.getvalue().splitlines()[1])
        self.assertEqual((reply["id"], reply["error"]["code"]), (9, -32002))
        self.assertNotIn("result", reply)


class GapRef002InternalErrorTests(unittest.TestCase):
    def test_gap_ref_002_unexpected_exception_becomes_32603(self):
        bridge = ready()
        with mock.patch.object(server, "run", side_effect=RuntimeError("boom /secret/path")):
            reply = bridge.dispatch({"jsonrpc": "2.0", "id": "x", "method": "tools/call", "params": CONVERT})
        self.assertEqual(reply, {"jsonrpc": "2.0", "id": "x", "error": {
            "code": -32603, "message": "Internal bridge error; no evidence result is available"}})
        self.assertNotIn("secret", json.dumps(reply))
        follow = bridge.dispatch({"jsonrpc": "2.0", "id": "y", "method": "tools/call", "params": CONVERT})
        self.assertFalse(follow["result"]["isError"])

    def test_gap_ref_002_unencodable_result_becomes_32603(self):
        for value in (math.nan, math.inf, -math.inf, object(), {1, 2}, b"bytes"):
            with self.subTest(value=repr(value)):
                reply = frame({"jsonrpc": "2.0", "id": 5, "result": {"value": value}})
                self.assertEqual(reply, {"jsonrpc": "2.0", "id": 5, "error": {
                    "code": -32603, "message": "Result cannot be represented; evidence withheld"}})

    def test_gap_ref_002_serve_continues_after_an_unencodable_result(self):
        payload = b"".join(json.dumps(f).encode() + b"\n" for f in (
            INIT, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": CONVERT},
            {"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}}))
        bad = {"isError": False, "structuredContent": {"value": object()}}
        sink = io.BytesIO()
        with mock.patch.object(server, "_tool_result", return_value=bad):
            self.assertEqual(serve(io.BytesIO(payload), sink), 0)
        replies = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual(len(replies), 3)
        self.assertEqual((replies[1]["id"], replies[1]["error"]["code"]), (1, -32603))
        self.assertEqual(replies[2], {"jsonrpc": "2.0", "id": 2, "result": {}})


class GapRef003EnvelopeTests(unittest.TestCase):
    def assertRefused(self, message, text=None):
        reply = Bridge().dispatch(message)
        self.assertEqual(reply["id"], None)
        self.assertEqual(reply["error"]["code"], -32600)
        self.assertNotIn("result", reply)
        if text is not None:
            self.assertIn(text, reply["error"]["message"])

    def test_gap_ref_003_batches_and_non_objects_are_refused(self):
        for message in ([INIT], [], [{"jsonrpc": "2.0", "id": 1, "method": "ping"}], "ping", 3, None):
            with self.subTest(message=message):
                self.assertRefused(message, "batches")
        reply = Bridge().handle(json.dumps([INIT, INIT]).encode())
        self.assertEqual((reply["id"], reply["error"]["code"]), (None, -32600))

    def test_gap_ref_003_extra_envelope_fields_are_refused(self):
        for extra in ({"result": {}}, {"error": {}}, {"meta": 1}, {"Method": "ping"}):
            with self.subTest(extra=extra):
                self.assertRefused({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}, **extra}, "extra fields")

    def test_gap_ref_003_wrong_jsonrpc_or_method_is_refused(self):
        for envelope in ({"jsonrpc": "1.0", "id": 1, "method": "ping"}, {"jsonrpc": 2.0, "id": 1, "method": "ping"},
                         {"id": 1, "method": "ping"}, {"jsonrpc": "2.0", "id": 1},
                         {"jsonrpc": "2.0", "id": 1, "method": ""}, {"jsonrpc": "2.0", "id": 1, "method": 7}):
            with self.subTest(envelope=envelope):
                self.assertRefused(envelope, "envelope")

    def test_gap_ref_003_bad_id_types_are_refused(self):
        for identifier in (None, 1.0, 1.5, "x" * (MAX_ID_CHARS + 1), MAX_ID_INTEGER + 1, -MAX_ID_INTEGER - 1,
                           True, False, [], {}):
            with self.subTest(identifier=repr(identifier)[:20]):
                self.assertRefused({"jsonrpc": "2.0", "id": identifier, "method": "ping"}, "Request id")

    def test_gap_ref_003_bounded_ids_are_accepted(self):
        for identifier in ("", "x" * MAX_ID_CHARS, 0, MAX_ID_INTEGER, -MAX_ID_INTEGER):
            with self.subTest(identifier=repr(identifier)[:20]):
                reply = Bridge().dispatch({"jsonrpc": "2.0", "id": identifier, "method": "ping"})
                self.assertEqual(reply, {"jsonrpc": "2.0", "id": identifier, "result": {}})

    def test_gap_ref_003_refused_envelope_over_the_wire(self):
        payload = b'{"jsonrpc":"2.0","id":null,"method":"ping"}\n{"jsonrpc":"2.0","id":1.5,"method":"ping"}\n'
        sink = io.BytesIO()
        self.assertEqual(serve(io.BytesIO(payload), sink), 0)
        replies = [json.loads(line) for line in sink.getvalue().splitlines()]
        self.assertEqual([(r["id"], r["error"]["code"]) for r in replies], [(None, -32600), (None, -32600)])


class GapRef004PingTests(unittest.TestCase):
    def test_gap_ref_004_ping_with_empty_params_returns_empty_object(self):
        for bridge in (Bridge(), ready()):
            self.assertEqual(bridge.dispatch({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}),
                             {"jsonrpc": "2.0", "id": 1, "result": {}})
            self.assertEqual(bridge.dispatch({"jsonrpc": "2.0", "id": 2, "method": "ping"}),
                             {"jsonrpc": "2.0", "id": 2, "result": {}})

    def test_gap_ref_004_ping_does_not_initialise_the_bridge(self):
        bridge = Bridge()
        bridge.dispatch({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}})
        self.assertFalse(bridge.initialized)
        listed = bridge.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual(listed["error"]["code"], -32000)

    def test_gap_ref_004_ping_with_params_is_refused(self):
        for params in ({"x": 1}, [], None, "x"):
            with self.subTest(params=params):
                reply = Bridge().dispatch({"jsonrpc": "2.0", "id": 3, "method": "ping", "params": params})
                self.assertEqual((reply["id"], reply["error"]["code"]), (3, -32602))

    def test_gap_ref_004_ping_notification_has_no_reply(self):
        self.assertIsNone(Bridge().dispatch({"jsonrpc": "2.0", "method": "ping", "params": {}}))


class GapRef005ProjectionLoaderTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        patcher = mock.patch.object(projection, "DATA_DIR", Path(self.dir.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, name, text):
        (Path(self.dir.name) / name).write_text(text, encoding="utf-8")

    def envelope(self, **overrides):
        document = {"schema": "test/1", "version": "1.0.0", "owner": "o", "generatedBy": "g", "data": {"k": 1}}
        document.update(overrides)
        return document

    def test_gap_ref_005_valid_projection_loads(self):
        self.write("ok.json", json.dumps(self.envelope()))
        data, sha = projection.load("ok.json", "test/1")
        self.assertEqual(data, {"k": 1})
        self.assertEqual(len(sha), 64)

    def test_gap_ref_005_path_like_names_are_refused(self):
        self.write("ok.json", json.dumps(self.envelope()))
        for name in ("../ok.json", "sub/ok.json", "sub\\ok.json", ".ok.json", "..", "/etc/passwd", ".hidden"):
            with self.subTest(name=name), self.assertRaises(ProjectionError) as caught:
                projection.load(name, "test/1")
            self.assertEqual(str(caught.exception), "Projection names are fixed file names")

    def test_gap_ref_005_duplicate_keys_are_refused(self):
        for text in ('{"schema":"test/1","schema":"test/1","version":"1.0.0","owner":"o","generatedBy":"g","data":{}}',
                     '{"schema":"test/1","version":"1.0.0","owner":"o","generatedBy":"g","data":{"k":1,"k":2}}'):
            with self.subTest(text=text[:60]):
                self.write("dup.json", text)
                with self.assertRaises(ProjectionError) as caught:
                    projection.load("dup.json", "test/1")
                self.assertEqual(str(caught.exception), "Duplicate key in projection")

    def test_gap_ref_005_nan_and_infinity_are_refused(self):
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                self.write("nan.json", '{"schema":"test/1","version":"1.0.0","owner":"o","generatedBy":"g",'
                                       '"data":{"k":' + token + '}}')
                with self.assertRaises(ProjectionError) as caught:
                    projection.load("nan.json", "test/1")
                self.assertEqual(str(caught.exception), "Nonfinite number in projection")

    def test_gap_ref_005_envelope_and_schema_mismatches_are_refused(self):
        base = self.envelope()
        missing = dict(base)
        del missing["owner"]
        cases = (self.envelope(schema="other/1"), self.envelope(version="1.0"), self.envelope(version=1),
                 self.envelope(version="1.0.0-rc1"), self.envelope(data=[]), self.envelope(extra=True),
                 missing, [base], "text")
        for document in cases:
            with self.subTest(document=repr(document)[:60]):
                self.write("bad.json", json.dumps(document))
                with self.assertRaises(ProjectionError) as caught:
                    projection.load("bad.json", "test/1")
                self.assertEqual(str(caught.exception), "Projection envelope or schema mismatch: bad.json")


class GapRef006LoadTimeValidationTests(unittest.TestCase):
    def assertThermoRefuses(self, data, sha):
        with mock.patch.object(thermo, "load", return_value=(data, sha)), self.assertRaises(thermo.ThermoError) as caught:
            thermo._table("nh3")
        self.assertEqual(caught.exception.code, "projection_invalid")

    def test_gap_ref_006_shipped_saturation_rows_reload(self):
        data, sha = shipped("refrigerant-saturation.nh3.json", thermo.SCHEMA)
        with mock.patch.object(thermo, "load", return_value=(data, sha)):
            self.assertEqual(thermo._table("nh3"), thermo.TABLES["NH3"])

    def test_gap_ref_006_saturation_rows_are_validated_at_load(self):
        data, sha = shipped("refrigerant-saturation.nh3.json", thermo.SCHEMA)
        mutations = (
            lambda d: d.__setitem__("units", ["degF", "kPa(a)", "kPa(a)", "J/kg", "J/kg"]),
            lambda d: d.__setitem__("rows", d["rows"][:1]),
            lambda d: d["rows"][3].pop(),
            lambda d: d["rows"][3].__setitem__(1, "38.1"),
            lambda d: d["rows"][3].__setitem__(1, None),
            lambda d: d["rows"][3].__setitem__(1, True),
            lambda d: d["rows"][3].__setitem__(1, math.nan),
            lambda d: d["rows"][3].__setitem__(2, math.inf),
            lambda d: d["rows"][3].__setitem__(0, d["rows"][2][0]),
            lambda d: d["rows"].reverse(),
            lambda d: d["rows"][3].__setitem__(1, d["rows"][2][1]),
            lambda d: d["rows"][3].__setitem__(2, d["rows"][2][2] - 1),
            lambda d: d["rows"][0].__setitem__(1, 0.0),
            lambda d: d["rows"][0].__setitem__(2, -1.0),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                bad = copy.deepcopy(data)
                mutate(bad)
                self.assertThermoRefuses(bad, sha)

    def assertLimitsRefuse(self, data, sha):
        with mock.patch.object(safety_limits, "load", return_value=(data, sha)), \
                self.assertRaises(safety_limits.SafetyLimitError):
            safety_limits._load()

    def test_gap_ref_006_shipped_exposure_limits_reload(self):
        data, sha = shipped("exposure-limits.json", safety_limits.SCHEMA)
        with mock.patch.object(safety_limits, "load", return_value=(data, sha)):
            self.assertEqual(safety_limits._load()[0], safety_limits.AMMONIA_LIMITS)

    def test_gap_ref_006_exposure_limit_rows_are_validated_at_load(self):
        data, sha = shipped("exposure-limits.json", safety_limits.SCHEMA)
        policy = {"basis": {"kind": "policy", "setBy": "Committee", "scope": "plant", "reason": "Plan"},
                  "status": "CHECK"}
        mutations = (
            lambda row: row.__setitem__("value_kind", "policy_set_point"),
            lambda row: row["concentration"].__setitem__("unit", "mg/m3"),
            lambda row: row.__setitem__("issuer", "AIHA"),
            lambda row: row.__setitem__("legal_status", "binding"),
            lambda row: row.__setitem__("evidence", policy),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                bad = copy.deepcopy(data)
                mutate(bad["limits"][0])
                self.assertLimitsRefuse(bad, sha)

    def assertTaxonomyRefuses(self, data, sha, message):
        with mock.patch.object(plant_model, "load", return_value=(data, sha)), \
                self.assertRaises(plant_model.PlantModelError) as caught:
            plant_model._load()
        self.assertEqual(str(caught.exception), message)

    def test_gap_ref_006_shipped_taxonomy_reloads(self):
        data, sha = shipped("plant-taxonomy.json", plant_model.SCHEMA)
        with mock.patch.object(plant_model, "load", return_value=(data, sha)):
            self.assertEqual(plant_model._load()[1], plant_model.KINDS)

    def test_gap_ref_006_taxonomy_aliases_and_parents_are_validated_at_load(self):
        data, sha = shipped("plant-taxonomy.json", plant_model.SCHEMA)
        alias_message = "Alias table is not normalised or names an unknown kind"
        bad = copy.deepcopy(data)
        bad["aliases"]["Screw Package"] = bad["aliases"][next(iter(bad["aliases"]))]
        self.assertTaxonomyRefuses(bad, sha, alias_message)
        bad = copy.deepcopy(data)
        bad["aliases"]["warp-core"] = "warp-core"
        self.assertTaxonomyRefuses(bad, sha, alias_message)
        bad = copy.deepcopy(data)
        bad["kinds"][0]["parent"] = "no-such-kind"
        self.assertTaxonomyRefuses(bad, sha, "Kind parent is not a canonical kind")
        bad = copy.deepcopy(data)
        bad["kinds"].append(dict(bad["kinds"][0]))
        self.assertTaxonomyRefuses(bad, sha, "Duplicate canonical kind")
        bad = copy.deepcopy(data)
        bad["line_services"].append(dict(bad["line_services"][0]))
        self.assertTaxonomyRefuses(bad, sha, "Duplicate line-service code")

    def assertThresholdsRefuse(self, data, sha, message=None):
        with mock.patch.object(process_safety, "load", return_value=(data, sha)), \
                self.assertRaises(process_safety.ProcessSafetyError) as caught:
            process_safety._load()
        if message is not None:
            self.assertEqual(str(caught.exception), message)

    def test_gap_ref_006_shipped_thresholds_reload(self):
        data, sha = shipped("psm-thresholds.json", process_safety.SCHEMA)
        with mock.patch.object(process_safety, "load", return_value=(data, sha)):
            self.assertEqual(set(process_safety._load()[0]), set(process_safety.RULES))

    def test_gap_ref_006_psm_threshold_quotes_are_validated_at_load(self):
        data, sha = shipped("psm-thresholds.json", process_safety.SCHEMA)
        index = {row["framework"]: i for i, row in enumerate(data["rules"])}
        osha, epa = index["osha-psm"], index["epa-rmp"]
        cases = (
            (osha, lambda r: r["threshold_evidence"]["basis"].__setitem__("quoted", "Ammonia, Anhydrous 7664-41-7 5000"),
             "Cited quote does not contain the threshold"),
            (osha, lambda r: r.__setitem__("threshold_lb", 15000), "Cited quote does not contain the threshold"),
            (osha, lambda r: r["comparison_evidence"]["basis"].__setitem__("quoted", "a quantity of ammonia"),
             "At-or-above comparison is not in the cited text"),
            (epa, lambda r: r["comparison_evidence"]["basis"].__setitem__("quoted", "a quantity of ammonia"),
             "Above comparison is not in the cited text"),
            (osha, lambda r: r["threshold_evidence"]["basis"].__setitem__("url", "https://example.com/1910.119"),
             "A threshold citation must be an eCFR URL"),
            (osha, lambda r: r["threshold_evidence"].update(status="APPROVED", approvedBy="Reviewer",
                                                            approvedOn="2026-10-25"),
             "A threshold needs cited CHECK evidence"),
            (epa, lambda r: r["comparison_evidence"].update(basis={"kind": "practice", "note": "Common practice"}),
             "A threshold needs cited CHECK evidence"),
            (osha, lambda r: r.__setitem__("citations", ["https://example.com/"]), "Unusable threshold rule"),
            (osha, lambda r: r.__setitem__("threshold_lb", 10000.0), "Unusable threshold rule"),
            (osha, lambda r: r.__setitem__("cas", "0000-00-0"), "Unusable threshold rule"),
            (osha, lambda r: r.__setitem__("comparison", "below"), "Unusable threshold rule"),
            (osha, lambda r: r.pop("threshold_evidence"), None),
        )
        for number, (row, mutate, message) in enumerate(cases):
            with self.subTest(case=number):
                bad = copy.deepcopy(data)
                mutate(bad["rules"][row])
                self.assertThresholdsRefuse(bad, sha, message)
        bad = copy.deepcopy(data)
        bad["rules"].pop(epa)
        self.assertThresholdsRefuse(bad, sha, "Threshold table must name osha-psm and epa-rmp")
        bad = copy.deepcopy(data)
        bad["result_kind"] = "determination"
        self.assertThresholdsRefuse(bad, sha, "Threshold projection must be labeled as a screen")
        with mock.patch.object(process_safety, "load", side_effect=ProjectionError("Duplicate key in projection")), \
                self.assertRaises(process_safety.ProcessSafetyError):
            process_safety._load()


class GapRef007ToolErrorCodeTests(unittest.TestCase):
    def assertToolError(self, name, arguments, code):
        failed, assessment, receipt = run(name, arguments)
        self.assertTrue(failed)
        self.assertEqual(assessment, "tool_error")
        self.assertEqual(receipt["status"], "error")
        self.assertEqual(receipt["error"]["code"], code)
        self.assertIsNone(receipt["result"])
        self.assertEqual(receipt["evidence"], [])
        self.assertEqual(len(receipt["input_sha256"]), 64)
        self.assertTrue(receipt["boundary"]["observation_only"])
        self.assertFalse(receipt["boundary"]["safety_determination"])

    def test_gap_ref_007_invalid_issuer(self):
        for issuer in ("AIHA", "osha", "", 3, False):
            with self.subTest(issuer=issuer):
                self.assertToolError("exposure_limits", {"substance": "ammonia", "issuer": issuer}, "invalid_issuer")

    def test_gap_ref_007_invalid_vocabulary(self):
        for vocabulary in ("pipe_colour", "", "EQUIPMENT_KIND", None, 1):
            with self.subTest(vocabulary=vocabulary):
                self.assertToolError("resolve_equipment_kind", {"term": "compressor", "vocabulary": vocabulary},
                                     "invalid_vocabulary")

    def test_gap_ref_007_invalid_term(self):
        for arguments in ({"term": ""}, {"term": "   "}, {"term": 7}, {"term": None}, {"term": "x" * 129},
                          {"term": "", "vocabulary": "line_service"}, {"term": "x" * 17, "vocabulary": "line_service"},
                          {"term": ["HPL"], "vocabulary": "line_service"}):
            with self.subTest(arguments=repr(arguments)[:40]):
                self.assertToolError("resolve_equipment_kind", arguments, "invalid_term")

    def test_gap_ref_007_codes_reach_the_bridge_as_tool_errors(self):
        bridge = ready()
        reply = bridge.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "exposure_limits", "arguments": {"substance": "ammonia", "issuer": "AIHA"}}})
        self.assertTrue(reply["result"]["isError"])
        self.assertEqual(reply["result"]["structuredContent"]["receipt"]["error"]["code"], "invalid_issuer")


class GapRef008OutputPipeTests(unittest.TestCase):
    PAYLOAD = (json.dumps(INIT) + "\n").encode()

    def test_gap_ref_008_broken_pipe_ends_session_with_exit_2(self):
        for error in (BrokenPipeError(32, "Broken pipe"), OSError(5, "Input/output error"),
                      ConnectionResetError(104, "reset")):
            with self.subTest(error=type(error).__name__):
                self.assertEqual(serve(io.BytesIO(self.PAYLOAD * 3), BrokenSink(error)), 2)

    def test_gap_ref_008_input_oserror_ends_session_with_exit_2(self):
        source = mock.Mock()
        source.readline.side_effect = OSError(5, "Input/output error")
        self.assertEqual(serve(source, io.BytesIO()), 2)

    def test_gap_ref_008_closed_os_pipe_ends_session_with_exit_2(self):
        read_fd, write_fd = os.pipe()
        os.close(read_fd)
        with io.FileIO(write_fd, "wb", closefd=True) as sink:
            self.assertEqual(serve(io.BytesIO(self.PAYLOAD * 3), sink), 2)


if __name__ == "__main__":
    unittest.main()
