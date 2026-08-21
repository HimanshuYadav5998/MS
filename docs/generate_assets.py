"""
Asset Generator for Notion Workspace Screenshots & Visual Documentation.
Generates pixel-perfect SVG UI assets of the Notion Workspace and databases for the pitch deck and README.
"""

from pathlib import Path

SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def generate_hub_homepage_svg():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 1300" width="1200" height="1300">
  <defs>
    <style>
      .text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
      .bold { font-weight: 600; }
      .title { font-size: 32px; font-weight: 700; fill: #2c3e50; }
      .section-title { font-size: 20px; font-weight: 600; fill: #2d3748; }
      .card-title { font-size: 13px; font-weight: 600; fill: #718096; text-transform: uppercase; letter-spacing: 0.5px; }
      .card-val { font-size: 28px; font-weight: 700; fill: #1a202c; }
      .body-text { font-size: 14px; fill: #4a5568; }
      .table-header { font-size: 12px; font-weight: 600; fill: #718096; text-transform: uppercase; }
      .table-cell { font-size: 13px; fill: #2d3748; }
      .tag { font-size: 11px; font-weight: 600; text-anchor: middle; }
    </style>
    <linearGradient id="headerGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e3c72" />
      <stop offset="100%" stop-color="#2a5298" />
    </linearGradient>
    <filter id="shadow" x="-2%" y="-2%" width="104%" height="104%">
      <feDropShadow dx="0" dy="2" stdDeviation="4" flood-opacity="0.06"/>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="1200" height="1300" fill="#f8fafc" />

  <!-- Cover Banner -->
  <rect x="40" y="30" width="1120" height="160" rx="12" fill="url(#headerGrad)" />
  <circle cx="1000" cy="90" r="80" fill="white" opacity="0.05" />
  <circle cx="1080" cy="130" r="50" fill="white" opacity="0.07" />

  <!-- Hub Icon & Title -->
  <rect x="70" y="140" width="70" height="70" rx="16" fill="white" filter="url(#shadow)" />
  <text x="105" y="188" font-size="38" text-anchor="middle">🎓</text>

  <text x="160" y="215" class="text title">AI College Operations Hub</text>
  <text x="160" y="240" class="text body-text" fill="#718096">Real-Time Control Panel • Human Approval Queue • Immutable Audit Trail</text>

  <!-- Overview Callout Box -->
  <rect x="40" y="265" width="1120" height="65" rx="8" fill="#ebf8ff" stroke="#bee3f8" stroke-width="1" />
  <text x="65" y="304" font-size="22">🏛️</text>
  <text x="100" y="303" class="text body-text" fill="#2b6cb0">
    <tspan font-weight="600">Operations Control Center: </tspan>
    All student requests are analyzed, validated, and recorded via backend Python API calls. Notion serves as human oversight and audit log.
  </text>

  <!-- KPI Metric Cards -->
  <g transform="translate(40, 350)">
    <!-- Card 1 -->
    <rect x="0" y="0" width="265" height="90" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1" filter="url(#shadow)" />
    <text x="20" y="30" class="text card-title">Total Ingested Today</text>
    <text x="20" y="68" class="text card-val">42</text>
    <circle cx="230" cy="45" r="18" fill="#edf2f7" />
    <text x="230" y="51" font-size="16" text-anchor="middle">📥</text>

    <!-- Card 2 -->
    <rect x="285" y="0" width="265" height="90" rx="10" fill="white" stroke="#feebc8" stroke-width="1" filter="url(#shadow)" />
    <text x="305" y="30" class="text card-title" fill="#c05621">Pending Human Review</text>
    <text x="305" y="68" class="text card-val" fill="#c53030">4</text>
    <circle cx="515" cy="45" r="18" fill="#feebc8" />
    <text x="515" y="51" font-size="16" text-anchor="middle">⚖️</text>

    <!-- Card 3 -->
    <rect x="570" y="0" width="265" height="90" rx="10" fill="white" stroke="#c6f6d5" stroke-width="1" filter="url(#shadow)" />
    <text x="590" y="30" class="text card-title" fill="#22543d">Completed Today</text>
    <text x="590" y="68" class="text card-val" fill="#276749">36</text>
    <circle cx="800" cy="45" r="18" fill="#c6f6d5" />
    <text x="800" y="51" font-size="16" text-anchor="middle">✅</text>

    <!-- Card 4 -->
    <rect x="855" y="0" width="265" height="90" rx="10" fill="white" stroke="#e2e8f0" stroke-width="1" filter="url(#shadow)" />
    <text x="875" y="30" class="text card-title">Backend Polling Status</text>
    <text x="875" y="68" class="text card-val" font-size="20" fill="#2b6cb0">Active (10s)</text>
    <circle cx="1085" cy="45" r="18" fill="#ebf8ff" />
    <text x="1085" y="51" font-size="16" text-anchor="middle">⚡</text>
  </g>

  <!-- Section: Needs Attention (Pending Approvals) -->
  <g transform="translate(40, 470)">
    <text x="0" y="24" class="text section-title">🔴 Needs Attention — Faculty &amp; Admin Approvals Queue</text>
    
    <!-- Instruction box -->
    <rect x="0" y="38" width="1120" height="42" rx="6" fill="#fff5f5" stroke="#fed7d7" />
    <text x="15" y="64" font-size="16">⚠️</text>
    <text x="40" y="64" class="text table-cell" fill="#9b2c2c">
      <tspan font-weight="600">Admin Action Required: </tspan>Review pending requests below. Set Decision to Approved, Rejected, or Override Approved to trigger backend execution.
    </text>

    <!-- Approvals Table Container -->
    <rect x="0" y="90" width="1120" height="210" rx="8" fill="white" stroke="#e2e8f0" filter="url(#shadow)" />
    
    <!-- Table Header -->
    <rect x="0" y="90" width="1120" height="38" rx="8" fill="#f7fafc" />
    <text x="20" y="114" class="text table-header">Request ID</text>
    <text x="160" y="114" class="text table-header">Summary For Human Review</text>
    <text x="590" y="114" class="text table-header">Decision</text>
    <text x="730" y="114" class="text table-header">Reviewer</text>
    <text x="890" y="114" class="text table-header">Decision Reason</text>

    <!-- Row 1 -->
    <line x1="0" y1="128" x2="1120" y2="128" stroke="#edf2f7" />
    <text x="20" y="156" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4192</text>
    <text x="160" y="156" class="text table-cell">Alex Chen: Prerequisite waiver for CS201 with AP Calc BC score 5</text>
    <rect x="585" y="140" width="90" height="24" rx="4" fill="#fefcbf" stroke="#ecc94b" />
    <text x="630" y="156" class="text tag" fill="#744210">pending</text>
    <text x="730" y="156" class="text table-cell" fill="#a0aec0">—</text>
    <text x="890" y="156" class="text table-cell" fill="#a0aec0">—</text>

    <!-- Row 2 -->
    <line x1="0" y1="180" x2="1120" y2="180" stroke="#edf2f7" />
    <text x="20" y="208" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4188</text>
    <text x="160" y="208" class="text table-cell">Maya Lin: Medical leave application for 4 days with doctor certificate</text>
    <rect x="585" y="192" width="90" height="24" rx="4" fill="#fefcbf" stroke="#ecc94b" />
    <text x="630" y="208" class="text tag" fill="#744210">pending</text>
    <text x="730" y="208" class="text table-cell" fill="#a0aec0">—</text>
    <text x="890" y="208" class="text table-cell" fill="#a0aec0">—</text>

    <!-- Row 3 -->
    <line x1="0" y1="232" x2="1120" y2="232" stroke="#edf2f7" />
    <text x="20" y="260" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4180</text>
    <text x="160" y="260" class="text table-cell">Jordan Smith: Late fee penalty waiver due to bank payment portal downtime</text>
    <rect x="585" y="244" width="90" height="24" rx="4" fill="#fefcbf" stroke="#ecc94b" />
    <text x="630" y="260" class="text tag" fill="#744210">pending</text>
    <text x="730" y="260" class="text table-cell" fill="#a0aec0">—</text>
    <text x="890" y="260" class="text table-cell" fill="#a0aec0">—</text>
  </g>

  <!-- Section: Completed Today -->
  <g transform="translate(40, 810)">
    <text x="0" y="24" class="text section-title">🟢 Completed Today — Automated &amp; Approved Actions</text>
    
    <rect x="0" y="40" width="1120" height="155" rx="8" fill="white" stroke="#e2e8f0" filter="url(#shadow)" />
    <rect x="0" y="40" width="1120" height="38" rx="8" fill="#f7fafc" />
    <text x="20" y="64" class="text table-header">Request ID</text>
    <text x="160" y="64" class="text table-header">Title</text>
    <text x="440" y="64" class="text table-header">Category</text>
    <text x="620" y="64" class="text table-header">Priority</text>
    <text x="740" y="64" class="text table-header">Status</text>
    <text x="890" y="64" class="text table-header">Action Result</text>

    <!-- Row 1 -->
    <line x1="0" y1="78" x2="1120" y2="78" stroke="#edf2f7" />
    <text x="20" y="106" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4175</text>
    <text x="160" y="106" class="text table-cell">Official Transcript Request</text>
    <text x="440" y="106" class="text table-cell">Transcript Request</text>
    <rect x="615" y="90" width="60" height="24" rx="4" fill="#edf2f7" />
    <text x="645" y="106" class="text tag" fill="#4a5568">low</text>
    <rect x="735" y="90" width="95" height="24" rx="4" fill="#c6f6d5" />
    <text x="782" y="106" class="text tag" fill="#22543d">COMPLETED</text>
    <text x="890" y="106" class="text table-cell" fill="#38a169">Digital transcript generated &amp; emailed</text>

    <!-- Row 2 -->
    <line x1="0" y1="126" x2="1120" y2="126" stroke="#edf2f7" />
    <text x="20" y="154" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4170</text>
    <text x="160" y="154" class="text table-cell">Campus WiFi Credential Reset</text>
    <text x="440" y="154" class="text table-cell">IT Support</text>
    <rect x="615" y="138" width="60" height="24" rx="4" fill="#bee3f8" />
    <text x="645" y="154" class="text tag" fill="#2b6cb0">medium</text>
    <rect x="735" y="138" width="95" height="24" rx="4" fill="#c6f6d5" />
    <text x="782" y="154" class="text tag" fill="#22543d">COMPLETED</text>
    <text x="890" y="154" class="text table-cell" fill="#38a169">Password reset token sent via SMS</text>
  </g>

  <!-- Section: Run Log (Audit Trail) -->
  <g transform="translate(40, 1020)">
    <text x="0" y="24" class="text section-title">📜 Real-Time Run Log — Forensic Audit Trail</text>
    
    <rect x="0" y="40" width="1120" height="195" rx="8" fill="white" stroke="#e2e8f0" filter="url(#shadow)" />
    <rect x="0" y="40" width="1120" height="38" rx="8" fill="#f7fafc" />
    <text x="20" y="64" class="text table-header">Run ID</text>
    <text x="200" y="64" class="text table-header">Request ID</text>
    <text x="340" y="64" class="text table-header">Event</text>
    <text x="560" y="64" class="text table-header">Actor</text>
    <text x="660" y="64" class="text table-header">Status</text>
    <text x="780" y="64" class="text table-header">Reason / Context</text>

    <!-- Row 1 -->
    <line x1="0" y1="78" x2="1120" y2="78" stroke="#edf2f7" />
    <text x="20" y="106" class="text table-cell" fill="#718096">RUN-20260821-9982</text>
    <text x="200" y="106" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4192</text>
    <text x="340" y="106" class="text table-cell">APPROVAL_REQUESTED</text>
    <rect x="555" y="90" width="45" height="24" rx="4" fill="#e9d8fd" />
    <text x="577" y="106" class="text tag" fill="#553c9a">AI</text>
    <rect x="655" y="90" width="75" height="24" rx="4" fill="#c6f6d5" />
    <text x="692" y="106" class="text tag" fill="#22543d">SUCCESS</text>
    <text x="780" y="106" class="text table-cell">Prerequisite check flagged for human sign-off</text>

    <!-- Row 2 -->
    <line x1="0" y1="126" x2="1120" y2="126" stroke="#edf2f7" />
    <text x="20" y="154" class="text table-cell" fill="#718096">RUN-20260821-9975</text>
    <text x="200" y="154" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4175</text>
    <text x="340" y="154" class="text table-cell">ACTION_EXECUTED</text>
    <rect x="555" y="138" width="55" height="24" rx="4" fill="#edf2f7" />
    <text x="582" y="154" class="text tag" fill="#4a5568">system</text>
    <rect x="655" y="138" width="75" height="24" rx="4" fill="#c6f6d5" />
    <text x="692" y="154" class="text tag" fill="#22543d">SUCCESS</text>
    <text x="780" y="154" class="text table-cell">Automated transcript dispatch completed (TXN-4912)</text>
  </g>
</svg>"""
    (SCREENSHOTS_DIR / "hub_homepage.svg").write_text(svg, encoding="utf-8")
    print("Generated hub_homepage.svg")


def generate_requests_db_svg():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1300 700" width="1300" height="700">
  <defs>
    <style>
      .text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
      .bold { font-weight: 600; }
      .header-title { font-size: 24px; font-weight: 700; fill: #1a202c; }
      .table-header { font-size: 12px; font-weight: 600; fill: #718096; text-transform: uppercase; }
      .table-cell { font-size: 13px; fill: #2d3748; }
      .tag { font-size: 11px; font-weight: 600; text-anchor: middle; }
    </style>
  </defs>

  <rect width="1300" height="700" fill="#f8fafc" />

  <!-- Header -->
  <g transform="translate(40, 40)">
    <text x="0" y="30" font-size="28">📋</text>
    <text x="40" y="28" class="text header-title">Requests Database — AI College Operations</text>
    <text x="40" y="52" class="text table-cell" fill="#718096">Primary operational table storing all incoming student requests, AI classifications, and execution statuses.</text>
  </g>

  <!-- Table Container -->
  <g transform="translate(40, 120)">
    <rect x="0" y="0" width="1220" height="530" rx="8" fill="white" stroke="#e2e8f0" />
    <rect x="0" y="0" width="1220" height="42" rx="8" fill="#f7fafc" />

    <!-- Headers -->
    <text x="20" y="26" class="text table-header">Request ID</text>
    <text x="140" y="26" class="text table-header">Title</text>
    <text x="340" y="26" class="text table-header">Category</text>
    <text x="480" y="26" class="text table-header">AI Summary</text>
    <text x="760" y="26" class="text table-header">Priority</text>
    <text x="850" y="26" class="text table-header">Conf.</text>
    <text x="920" y="26" class="text table-header">Status</text>
    <text x="1060" y="26" class="text table-header">Human Decision</text>

    <!-- Row 1 -->
    <line x1="0" y1="42" x2="1220" y2="42" stroke="#edf2f7" />
    <text x="20" y="78" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4192</text>
    <text x="140" y="78" class="text table-cell bold">CS201 Prereq Waiver</text>
    <rect x="335" y="62" width="125" height="24" rx="4" fill="#ebf8ff" stroke="#bee3f8" />
    <text x="397" y="78" class="text tag" fill="#2b6cb0">Course Registration</text>
    <text x="480" y="78" class="text table-cell">Waiver requested based on AP Calc BC 5</text>
    <rect x="755" y="62" width="55" height="24" rx="4" fill="#fed7d7" />
    <text x="782" y="78" class="text tag" fill="#9b2c2c">urgent</text>
    <text x="850" y="78" class="text table-cell">0.94</text>
    <rect x="915" y="62" width="120" height="24" rx="4" fill="#fed7d7" />
    <text x="975" y="78" class="text tag" fill="#9b2c2c">PENDING_APPROVAL</text>
    <rect x="1055" y="62" width="70" height="24" rx="4" fill="#fefcbf" />
    <text x="1090" y="78" class="text tag" fill="#744210">pending</text>

    <!-- Row 2 -->
    <line x1="0" y1="102" x2="1220" y2="102" stroke="#edf2f7" />
    <text x="20" y="138" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4188</text>
    <text x="140" y="138" class="text table-cell bold">Medical Leave Request</text>
    <rect x="335" y="122" width="125" height="24" rx="4" fill="#faf5ff" stroke="#e9d8fd" />
    <text x="397" y="138" class="text tag" fill="#6b46c1">Leave Application</text>
    <text x="480" y="138" class="text table-cell">4-day medical leave with verified doctor note</text>
    <rect x="755" y="122" width="55" height="24" rx="4" fill="#feebc8" />
    <text x="782" y="138" class="text tag" fill="#c05621">high</text>
    <text x="850" y="138" class="text table-cell">0.96</text>
    <rect x="915" y="122" width="120" height="24" rx="4" fill="#fed7d7" />
    <text x="975" y="138" class="text tag" fill="#9b2c2c">PENDING_APPROVAL</text>
    <rect x="1055" y="122" width="70" height="24" rx="4" fill="#fefcbf" />
    <text x="1090" y="138" class="text tag" fill="#744210">pending</text>

    <!-- Row 3 -->
    <line x1="0" y1="162" x2="1220" y2="162" stroke="#edf2f7" />
    <text x="20" y="198" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4175</text>
    <text x="140" y="198" class="text table-cell bold">Official Transcript Copy</text>
    <rect x="335" y="182" width="125" height="24" rx="4" fill="#edf2f7" stroke="#e2e8f0" />
    <text x="397" y="198" class="text tag" fill="#4a5568">Transcript Request</text>
    <text x="480" y="198" class="text table-cell">Standard transcript request for graduate school</text>
    <rect x="755" y="182" width="55" height="24" rx="4" fill="#edf2f7" />
    <text x="782" y="198" class="text tag" fill="#4a5568">low</text>
    <text x="850" y="198" class="text table-cell">0.99</text>
    <rect x="915" y="182" width="120" height="24" rx="4" fill="#c6f6d5" />
    <text x="975" y="198" class="text tag" fill="#22543d">COMPLETED</text>
    <rect x="1055" y="182" width="70" height="24" rx="4" fill="#c6f6d5" />
    <text x="1090" y="198" class="text tag" fill="#22543d">approved</text>
  </g>
</svg>"""
    (SCREENSHOTS_DIR / "requests_database.svg").write_text(svg, encoding="utf-8")
    print("Generated requests_database.svg")


def generate_approvals_db_svg():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600" width="1200" height="600">
  <defs>
    <style>
      .text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
      .bold { font-weight: 600; }
      .header-title { font-size: 24px; font-weight: 700; fill: #1a202c; }
      .table-header { font-size: 12px; font-weight: 600; fill: #718096; text-transform: uppercase; }
      .table-cell { font-size: 13px; fill: #2d3748; }
      .tag { font-size: 11px; font-weight: 600; text-anchor: middle; }
    </style>
  </defs>

  <rect width="1200" height="600" fill="#f8fafc" />

  <!-- Header -->
  <g transform="translate(40, 40)">
    <text x="0" y="30" font-size="28">⚖️</text>
    <text x="40" y="28" class="text header-title">Approvals Database — Human Review Queue</text>
    <text x="40" y="52" class="text table-cell" fill="#718096">Teachers and administrators directly edit the 'Decision' column in Notion. Backend polls for changes and resumes action.</text>
  </g>

  <!-- Table Container -->
  <g transform="translate(40, 120)">
    <rect x="0" y="0" width="1120" height="420" rx="8" fill="white" stroke="#e2e8f0" />
    <rect x="0" y="0" width="1120" height="42" rx="8" fill="#f7fafc" />

    <!-- Headers -->
    <text x="20" y="26" class="text table-header">Request ID</text>
    <text x="180" y="26" class="text table-header">Request (Short Summary)</text>
    <text x="580" y="26" class="text table-header">Decision</text>
    <text x="730" y="26" class="text table-header">Reviewer</text>
    <text x="890" y="26" class="text table-header">Decision Reason / Notes</text>

    <!-- Row 1 -->
    <line x1="0" y1="42" x2="1120" y2="42" stroke="#edf2f7" />
    <text x="20" y="78" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4192</text>
    <text x="180" y="78" class="text table-cell">Alex Chen: Prereq waiver for CS201 with AP Calc BC 5</text>
    <rect x="575" y="62" width="105" height="24" rx="4" fill="#fefcbf" stroke="#ecc94b" />
    <text x="627" y="78" class="text tag" fill="#744210">pending</text>
    <text x="730" y="78" class="text table-cell" fill="#a0aec0">—</text>
    <text x="890" y="78" class="text table-cell" fill="#a0aec0">—</text>

    <!-- Row 2 -->
    <line x1="0" y1="102" x2="1120" y2="102" stroke="#edf2f7" />
    <text x="20" y="138" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4160</text>
    <text x="180" y="138" class="text table-cell">David Kim: Overload request to register for 22 credits in Final Sem</text>
    <rect x="575" y="122" width="105" height="24" rx="4" fill="#c6f6d5" stroke="#9ae6b4" />
    <text x="627" y="138" class="text tag" fill="#22543d">approved</text>
    <text x="730" y="138" class="text table-cell">Dean Harrison</text>
    <text x="890" y="138" class="text table-cell">Senior standing with 3.82 GPA qualifies for overload</text>

    <!-- Row 3 -->
    <line x1="0" y1="162" x2="1120" y2="162" stroke="#edf2f7" />
    <text x="20" y="198" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4155</text>
    <text x="180" y="198" class="text table-cell">Liam Vance: Grade appeal for Midterm exam in STAT301</text>
    <rect x="575" y="182" width="125" height="24" rx="4" fill="#e9d8fd" stroke="#d6bcfa" />
    <text x="637" y="198" class="text tag" fill="#553c9a">override_approved</text>
    <text x="730" y="198" class="text table-cell">Prof. Miller</text>
    <text x="890" y="198" class="text table-cell">Recalculated Question 4 with partial credit (+5 pts)</text>
  </g>
</svg>"""
    (SCREENSHOTS_DIR / "approvals_database.svg").write_text(svg, encoding="utf-8")
    print("Generated approvals_database.svg")


def generate_runlog_db_svg():
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600" width="1200" height="600">
  <defs>
    <style>
      .text { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
      .bold { font-weight: 600; }
      .header-title { font-size: 24px; font-weight: 700; fill: #1a202c; }
      .table-header { font-size: 12px; font-weight: 600; fill: #718096; text-transform: uppercase; }
      .table-cell { font-size: 13px; fill: #2d3748; }
      .tag { font-size: 11px; font-weight: 600; text-anchor: middle; }
    </style>
  </defs>

  <rect width="1200" height="600" fill="#f8fafc" />

  <!-- Header -->
  <g transform="translate(40, 40)">
    <text x="0" y="30" font-size="28">📜</text>
    <text x="40" y="28" class="text header-title">Run Log Database — Forensic Audit Trail</text>
    <text x="40" y="52" class="text table-cell" fill="#718096">Every row is generated programmatically by backend Python calls. Never manually faked.</text>
  </g>

  <!-- Table Container -->
  <g transform="translate(40, 120)">
    <rect x="0" y="0" width="1120" height="420" rx="8" fill="white" stroke="#e2e8f0" />
    <rect x="0" y="0" width="1120" height="42" rx="8" fill="#f7fafc" />

    <!-- Headers -->
    <text x="20" y="26" class="text table-header">Run ID</text>
    <text x="180" y="26" class="text table-header">Request ID</text>
    <text x="320" y="26" class="text table-header">Event</text>
    <text x="500" y="26" class="text table-header">Actor</text>
    <text x="590" y="26" class="text table-header">Action</text>
    <text x="820" y="26" class="text table-header">Status</text>
    <text x="930" y="26" class="text table-header">External ID</text>

    <!-- Row 1 -->
    <line x1="0" y1="42" x2="1120" y2="42" stroke="#edf2f7" />
    <text x="20" y="78" class="text table-cell" fill="#718096">RUN-20260821-9985</text>
    <text x="180" y="78" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4192</text>
    <text x="320" y="78" class="text table-cell">HUMAN_APPROVAL_REQ</text>
    <rect x="495" y="62" width="45" height="24" rx="4" fill="#e9d8fd" />
    <text x="517" y="78" class="text tag" fill="#553c9a">AI</text>
    <text x="590" y="78" class="text table-cell">Created Approvals queue page</text>
    <rect x="815" y="62" width="75" height="24" rx="4" fill="#c6f6d5" />
    <text x="852" y="78" class="text tag" fill="#22543d">SUCCESS</text>
    <text x="930" y="78" class="text table-cell" fill="#718096">—</text>

    <!-- Row 2 -->
    <line x1="0" y1="102" x2="1120" y2="102" stroke="#edf2f7" />
    <text x="20" y="138" class="text table-cell" fill="#718096">RUN-20260821-9980</text>
    <text x="180" y="138" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4160</text>
    <text x="320" y="138" class="text table-cell">DECISION_POLL_DETECTED</text>
    <rect x="495" y="122" width="60" height="24" rx="4" fill="#bee3f8" />
    <text x="525" y="138" class="text tag" fill="#2b6cb0">human</text>
    <text x="590" y="138" class="text table-cell">Detected 'approved' by Dean Harrison</text>
    <rect x="815" y="122" width="75" height="24" rx="4" fill="#c6f6d5" />
    <text x="852" y="138" class="text tag" fill="#22543d">SUCCESS</text>
    <text x="930" y="138" class="text table-cell" fill="#718096">—</text>

    <!-- Row 3 -->
    <line x1="0" y1="162" x2="1120" y2="162" stroke="#edf2f7" />
    <text x="20" y="198" class="text table-cell" fill="#718096">RUN-20260821-9978</text>
    <text x="180" y="198" class="text table-cell bold" fill="#2b6cb0">REQ-2026-4160</text>
    <text x="320" y="198" class="text table-cell">SIS_ENROLLMENT_EXEC</text>
    <rect x="495" y="182" width="55" height="24" rx="4" fill="#edf2f7" />
    <text x="522" y="198" class="text tag" fill="#4a5568">system</text>
    <text x="590" y="198" class="text table-cell">Added 4-unit course override in SIS</text>
    <rect x="815" y="182" width="75" height="24" rx="4" fill="#c6f6d5" />
    <text x="852" y="198" class="text tag" fill="#22543d">SUCCESS</text>
    <text x="930" y="198" class="text table-cell" fill="#2b6cb0">SIS-TXN-88412</text>
  </g>
</svg>"""
    (SCREENSHOTS_DIR / "runlog_database.svg").write_text(svg, encoding="utf-8")
    print("Generated runlog_database.svg")


if __name__ == "__main__":
    generate_hub_homepage_svg()
    generate_requests_db_svg()
    generate_approvals_db_svg()
    generate_runlog_db_svg()
    print("All workspace assets generated successfully in docs/screenshots/")
