# src/prevent_outage_edge_testing/gates/reporter.py
"""
Report generators for gate results.

Produces:
- JSON reports under .poet/reports/<timestamp>.json
- HTML report at .poet/reports/latest.html
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from prevent_outage_edge_testing.gates.models import GateReport, GateStatus


class ReportGenerator:
    """Generates JSON and HTML reports from gate results."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path(".poet/reports")
    
    def ensure_output_dir(self) -> None:
        """Create output directory if it doesn't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def save_json(self, report: GateReport) -> Path:
        """
        Save report as JSON.
        
        Returns path to the saved file.
        """
        self.ensure_output_dir()
        
        # Timestamp-based filename
        ts = report.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
        
        # Also save as latest.json
        latest = self.output_dir / "latest.json"
        with open(latest, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
        
        return filepath
    
    def save_html(self, report: GateReport) -> Path:
        """
        Generate and save HTML report.
        
        Returns path to the saved file.
        """
        self.ensure_output_dir()
        
        html = self._generate_html(report)
        filepath = self.output_dir / "latest.html"
        
        with open(filepath, "w") as f:
            f.write(html)
        
        return filepath
    
    def _status_color(self, status: GateStatus) -> str:
        """Get color for status."""
        return {
            GateStatus.PASSED: "#22c55e",
            GateStatus.FAILED: "#ef4444",
            GateStatus.SKIPPED: "#eab308",
            GateStatus.ERROR: "#f97316",
        }.get(status, "#6b7280")
    
    def _status_icon(self, status: GateStatus) -> str:
        """Get icon for status."""
        return {
            GateStatus.PASSED: "&#10003;",
            GateStatus.FAILED: "&#10007;",
            GateStatus.SKIPPED: "&#8722;",
            GateStatus.ERROR: "&#9888;",
        }.get(status, "?")
    
    def _generate_html(self, report: GateReport) -> str:
        """Generate HTML report content."""
        overall_color = self._status_color(report.overall_status)
        overall_icon = self._status_icon(report.overall_status)
        
        # Build gates HTML
        gates_html = ""
        for gate in report.gates:
            gate_color = self._status_color(gate.status)
            gate_icon = self._status_icon(gate.status)
            
            # Build checks HTML
            checks_html = ""
            for check in gate.checks:
                check_color = self._status_color(check.status)
                check_icon = self._status_icon(check.status)
                checks_html += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">
                        <span style="color: {check_color}; margin-right: 8px;">{check_icon}</span>
                        {check.name}
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid #e5e7eb; color: {check_color};">
                        {check.status.value.upper()}
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid #e5e7eb; color: #6b7280; font-size: 0.875rem;">
                        {check.message[:100]}{'...' if len(check.message) > 100 else ''}
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid #e5e7eb; text-align: right; color: #6b7280;">
                        {check.duration_ms:.1f}ms
                    </td>
                </tr>
                """
            
            gates_html += f"""
            <div style="margin-bottom: 24px; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
                <div style="background: #f9fafb; padding: 16px; border-bottom: 1px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="color: {gate_color}; font-size: 1.25rem; margin-right: 8px;">{gate_icon}</span>
                        <strong style="font-size: 1.125rem;">{gate.gate_name}</strong>
                        <span style="color: #6b7280; margin-left: 8px;">({gate.gate_id})</span>
                    </div>
                    <div style="text-align: right;">
                        <span style="color: {gate_color}; font-weight: 600;">{gate.status.value.upper()}</span>
                        <span style="color: #6b7280; margin-left: 16px;">{gate.duration_ms:.1f}ms</span>
                    </div>
                </div>
                <table style="width: 100%; border-collapse: collapse;">
                    <thead>
                        <tr style="background: #f3f4f6;">
                            <th style="padding: 8px; text-align: left; font-weight: 500;">Check</th>
                            <th style="padding: 8px; text-align: left; font-weight: 500; width: 100px;">Status</th>
                            <th style="padding: 8px; text-align: left; font-weight: 500;">Message</th>
                            <th style="padding: 8px; text-align: right; font-weight: 500; width: 80px;">Duration</th>
                        </tr>
                    </thead>
                    <tbody>
                        {checks_html}
                    </tbody>
                </table>
                <div style="padding: 8px 16px; background: #f9fafb; font-size: 0.875rem; color: #6b7280;">
                    {gate.passed_count} passed, {gate.failed_count} failed, {gate.skipped_count} skipped
                </div>
            </div>
            """
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>POET Gate Report - {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6; color: #1f2937; line-height: 1.5; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
        h1 {{ font-size: 1.5rem; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <header style="margin-bottom: 32px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <h1>POET Release Gate Report</h1>
                <span style="color: #6b7280;">{report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</span>
            </div>
            
            <div style="background: white; border-radius: 8px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 4px;">Overall Status</div>
                        <div style="font-size: 2rem; font-weight: 700; color: {overall_color};">
                            <span style="margin-right: 8px;">{overall_icon}</span>
                            {report.overall_status.value.upper()}
                        </div>
                    </div>
                    <div style="display: flex; gap: 32px; text-align: center;">
                        <div>
                            <div style="font-size: 2rem; font-weight: 700; color: #22c55e;">{report.passed_gates}</div>
                            <div style="font-size: 0.875rem; color: #6b7280;">Passed</div>
                        </div>
                        <div>
                            <div style="font-size: 2rem; font-weight: 700; color: #ef4444;">{report.failed_gates}</div>
                            <div style="font-size: 0.875rem; color: #6b7280;">Failed</div>
                        </div>
                        <div>
                            <div style="font-size: 2rem; font-weight: 700; color: #6b7280;">{len(report.gates)}</div>
                            <div style="font-size: 0.875rem; color: #6b7280;">Total</div>
                        </div>
                        <div>
                            <div style="font-size: 2rem; font-weight: 700; color: #6b7280;">{report.total_duration_ms:.0f}</div>
                            <div style="font-size: 0.875rem; color: #6b7280;">ms</div>
                        </div>
                    </div>
                </div>
            </div>
        </header>
        
        <main>
            <h2 style="font-size: 1.25rem; font-weight: 600; margin-bottom: 16px;">Gate Results</h2>
            {gates_html}
        </main>
        
        <footer style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 0.875rem;">
            Generated by POET (Prevent Outage Edge Testing)
        </footer>
    </div>
</body>
</html>
"""
        return html
    
    def save_all(self, report: GateReport) -> tuple[Path, Path]:
        """
        Save both JSON and HTML reports.
        
        Returns tuple of (json_path, html_path).
        """
        json_path = self.save_json(report)
        html_path = self.save_html(report)
        return json_path, html_path
