from pathlib import Path


def test_monthly_upload_form_keeps_submit_actionable_and_explains_auth() -> None:
    dashboard = Path("dashboard/app/page.tsx").read_text(encoding="utf-8")

    assert 'id="report-admin-token"' in dashboard
    assert 'placeholder="ACTIVITY_ADMIN_TOKEN 값"' in dashboard
    assert "필수 항목을 확인하세요" in dashboard
    assert 'disabled={uploading}' in dashboard
    assert "disabled={!adminToken || !jobFile" not in dashboard
    assert dashboard.count('type="file" accept=".xls,.xlsx" required') == 3
    assert 'id="report-month"' not in dashboard
    assert 'data.append("report_month"' not in dashboard
    assert "분석 기간은 엑셀 상단의 표시 기간에서 자동으로 읽으며" in dashboard
