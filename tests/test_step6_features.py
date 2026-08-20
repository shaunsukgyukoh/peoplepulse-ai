from peoplepulse.ml.features import INTENT_PROXY_COLUMNS, feature_columns


def test_privacy_safe_feature_set_excludes_direct_intent_proxies():
    safe = set(feature_columns("privacy_safe"))
    assert safe.isdisjoint(INTENT_PROXY_COLUMNS)
    assert "work_strain_delta_7d_30d" in safe
    assert "document_usage_events" in safe
