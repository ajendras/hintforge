"""Neo-brutalist web dashboard for HintForge.

Provides a chunky, high-contrast Flask UI for creating, listing, monitoring
and launching recovery jobs. Reuses core job orchestration, SessionState
and Config models. Matches the loud visual language of the Rich CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, redirect, render_template_string, request, url_for

from .core import create_job, get_job, start_job_in_background
from .models import Job
from .utils import load_jobs

app = Flask(__name__)

BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>HINTFORGE DASHBOARD</title>
    <style>
        :root {
            --pink: #ff0044;
            --green: #00ff9f;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 40px;
            background: #0a0a0a;
            color: var(--green);
            font-family: monospace;
            line-height: 1.6;
        }
        .container {
            max-width: 1100px;
            margin: 0 auto;
        }
        .header {
            border: 12px solid var(--pink);
            background: #111;
            padding: 30px 40px;
            text-align: center;
            margin-bottom: 40px;
            box-shadow: 8px 8px 0 #000;
        }
        .header h1 {
            margin: 0 0 10px 0;
            font-size: 42px;
            color: white;
            text-shadow: 4px 4px 0 var(--pink);
        }
        .panel {
            border: 8px solid var(--pink);
            background: #111;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 6px 6px 0 #000;
        }
        h2 {
            color: white;
            border-bottom: 6px solid var(--green);
            padding-bottom: 10px;
            margin-top: 0;
        }
        table {
            width: 100%;
            border: 6px solid var(--green);
            border-collapse: collapse;
            background: #1a1a1a;
        }
        th, td {
            padding: 15px;
            border: 3px solid var(--green);
            text-align: left;
        }
        th {
            background: var(--pink);
            color: white;
            font-weight: normal;
        }
        tr:nth-child(even) {
            background: #222;
        }
        a {
            color: var(--green);
            text-decoration: none;
        }
        a:hover {
            color: white;
            text-decoration: underline;
        }
        button, input[type="submit"] {
            background: var(--pink);
            color: white;
            border: 6px solid var(--green);
            padding: 12px 24px;
            font-family: monospace;
            font-size: 16px;
            cursor: pointer;
            box-shadow: 4px 4px 0 #000;
        }
        button:hover, input[type="submit"]:hover {
            background: var(--green);
            color: #111;
        }
        input[type="text"] {
            background: #222;
            border: 4px solid var(--green);
            color: var(--green);
            padding: 12px;
            font-family: monospace;
            width: 100%;
            margin-bottom: 15px;
        }
        .status {
            padding: 4px 12px;
            border: 3px solid;
            display: inline-block;
            font-size: 13px;
        }
        .pending { border-color: #ff0; color: #ff0; }
        .running { border-color: var(--green); color: var(--green); animation: pulse 2s infinite; }
        .done { border-color: #0f0; color: #0f0; }
        .failed { border-color: var(--pink); color: var(--pink); }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        .success {
            color: var(--green);
            font-size: 18px;
            padding: 20px;
            border: 6px solid var(--green);
            background: #001a00;
            margin: 15px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>█ HINTFORGE █</h1>
            <div style="color:#ff0044; font-size:18px;">NEO-BRUTALIST RECOVERY DASHBOARD</div>
        </div>
        {{ content|safe }}
    </div>
</body>
</html>
"""


def _get_jobs_table() -> str:
    """Render HTML table of all jobs using data from load_jobs()."""
    jobs: list[Job] = load_jobs()
    if not jobs:
        return '<p style="color:#666; font-size:15px;">NO ACTIVE JOBS. CREATE ONE BELOW.</p>'

    rows = []
    for job in jobs:
        status_html = f'<span class="status {job.status}">{job.status.upper()}</span>'
        progress = f"{job.progress * 100:.0f}%"
        actions = f'<a href="/job/{job.id}">DETAILS</a>'
        if job.status == "pending":
            actions += f' | <a href="/start/{job.id}">▶ START</a>'
        if job.status == "done" and job.result:
            actions += f' | <span class="success">✓ {job.result}</span>'
        rows.append(f"""
        <tr>
            <td><strong>{job.id}</strong></td>
            <td>{Path(job.archive_path).name}</td>
            <td title="{job.hint}">{job.hint[:35]}{'...' if len(job.hint) > 35 else ''}</td>
            <td>{status_html}</td>
            <td>{progress}</td>
            <td>{actions}</td>
        </tr>
        """)
    return f"""
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>ARCHIVE</th>
                <th>HINT</th>
                <th>STATUS</th>
                <th>PROGRESS</th>
                <th>ACTIONS</th>
            </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
    </table>
    """


@app.route("/")
def index():
    """Dashboard home — list of jobs + form to create new ones."""
    content = f"""
    <div class="panel">
        <h2>RECOVERY JOBS</h2>
        {_get_jobs_table()}
    </div>
    <div class="panel">
        <h2>CREATE NEW JOB</h2>
        <form method="POST" action="/create">
            <label style="display:block;margin:10px 0 5px;">ARCHIVE PATH</label>
            <input type="text" name="archive_path" value="examples/protected.rar" required><br><br>
            <label style="display:block;margin:10px 0 5px;">HINT / MEMORY</label>
            <input type="text" name="hint" value="family vacation in greece with max the dog 2019" required><br><br>
            <input type="submit" value="LAUNCH RECOVERY JOB">
        </form>
    </div>
    <div style="text-align:center; margin-top:40px; color:#444; font-size:12px;">
        HintForge v0.1.0 • Powered by local LLM + GPU hashcat • Press START to begin testing
    </div>
    """
    return render_template_string(BASE_TEMPLATE, content=content)


@app.route("/create", methods=["POST"])
def create():
    """Create a new Job from form data and redirect to dashboard."""
    archive_path = request.form.get("archive_path", "").strip()
    hint = request.form.get("hint", "").strip()
    if not archive_path or not hint:
        return "ERROR: Archive path and hint are required", 400
    create_job(archive_path=archive_path, hint=hint)
    return redirect(url_for("index"))


@app.route("/job/<job_id>")
def job_detail(job_id: str):
    """Detailed view of a single job including result or error."""
    job = get_job(job_id)
    if not job:
        return "JOB NOT FOUND", 404

    result_html = ""
    if job.result:
        result_html = f'<div class="success">PASSWORD FOUND: <strong>{job.result}</strong></div>'
    elif job.error:
        result_html = f'<div style="color:#ff0044; border:4px solid #ff0044; padding:15px;">ERROR: {job.error}</div>'

    content = f"""
    <div class="panel">
        <h2>JOB DETAILS: {job.id}</h2>
        <p><strong>Archive:</strong> {job.archive_path}</p>
        <p><strong>Hint:</strong> {job.hint}</p>
        <p><strong>Status:</strong> <span class="status {job.status}">{job.status.upper()}</span></p>
        <p><strong>Progress:</strong> {job.progress*100:.1f}%</p>
        <p><strong>Created:</strong> {job.created_at}</p>
        {result_html}
        <br>
        <a href="/" style="border:4px solid #00ff9f; padding:10px 20px; display:inline-block;">← RETURN TO DASHBOARD</a>
        {'<br><br><a href="/start/' + job.id + '" style="background:#ff0044;color:white;padding:15px 30px;border:6px solid #00ff9f;">START JOB NOW</a>' if job.status == "pending" else ''}
    </div>
    """
    return render_template_string(BASE_TEMPLATE, content=content)


@app.route("/start/<job_id>")
def start(job_id: str):
    """Start a pending job in the background and return to dashboard."""
    job = get_job(job_id)
    if job and job.status == "pending":
        start_job_in_background(job_id)
    return redirect(url_for("index"))


def run_dashboard(port: int = 5000, debug: bool = False) -> None:
    """Run the neo-brutalist Flask dashboard server."""
    host = "0.0.0.0"
    print(f"\n→ Starting HintForge Dashboard on http://{host}:{port}")
    print("   Open the URL above in your browser.\n")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_dashboard()
