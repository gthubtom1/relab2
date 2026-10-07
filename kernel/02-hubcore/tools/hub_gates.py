# -*- coding: utf-8 -*-
"""运行核门面。实现拆在 hub_flow / hub_wording / hub_ask，对外仍从这里 import。"""
from hub_flow import (
    load_contract, norm_key, _contract_schema, _mission_data, _mission_revision,
    contract_fingerprint, _mission_complete, _validate_phases, derive,
    loop_warnings, active_block, phase_epoch, artifact_phase_epoch, _candidate_live, candidate_pointers,
    _candidate_paths, _physical_spec_binding, _read_registry_status, _identity_check, _guard_identity, _baseline_drift,
    is_legacy_four_exe, legacy_four_void_phase,
    physical_checks, phase_physical_checks, physical_receipt_missing, physical_receipt_missing_before, physical_receipts_for,
    release_role_min_phase, _red_receipt_for, NO_BASELINE_GREEN,
)
from hub_wording import (
    _usable_claim, _require_claim, _confirm_usable, _explicit_skip, _strip_independent_skip,
    _phase_receipt_text, confirm_multi_stop, confirm_wording_error,
    test_record_error, road_stop_lines,
)
from hub_ask import (
    _PACK_ASK_STOPS, _orig_asked, _ui_ask_hold, _pack_ask_gap,
    _missing_required_artifacts, _latest_ask_conflict,
)
from hub_io import (
    CANDIDATE_BOUND_ARTIFACTS, ARTIFACT_REQUIRED_FIELDS, PRODUCT_EVIDENCE,
)

