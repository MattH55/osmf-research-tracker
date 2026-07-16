import os

# Get the directory of this script
DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(DIR, 'index.html')

# HTML that loads external CSS + JS
html = r"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MedFreedom Arbitrage Map</title>
<meta name="description" content="Medical procedure access by jurisdiction. For informational purposes only.">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<link rel="stylesheet" href="css/style.css" />
</head>
<body>

<div class="disc" id="db">
<p><strong>⚠ INFORMATIONAL PURPOSES ONLY.</strong> Not medical, legal, or travel advice. Verify with official sources.
<button class="btnsm btn2" onclick="document.getElementById('db').style.display='none'" style="margin-left:.5rem">Dismiss</button></p>
</div>

<header class="hdr">
<div><h1>🗺 MedFreedom Arbitrage Map</h1></div>
<nav>
<button class="btn2" onclick="sv('public')" id="np">Public View</button>
<button class="btn2" onclick="sv('admin')" id="na">Admin Panel</button>
<button class="btn2" onclick="expCSV()">📥 CSV</button>
<button class="thm" onclick="toggleTheme()" id="tb">🌙</button>
</nav>
</header>

<div id="vp">

<section class="hero"><div class="hi">
<h2>Medical Procedure Access Worldwide</h2>
<p>Compare legal pathways, costs, oversight, and eligibility across 16 jurisdictions for 21 procedures.</p>
<div class="sbox">
<input type="text" id="si" placeholder="Search procedures, conditions..." onkeydown="if(event.key==='Enter')af()">
<button class="btn1" onclick="af()">🔍 Search</button>
</div></div></section>

<div class="fbar">
<div class="fg"><label>Modality</label><select id="fm" onchange="af()"><option value="">All</option></select></div>
<div class="fg"><label>Therapeutic Area</label><select id="ft" onchange="af()"><option value="">All</option></select></div>
<div class="fg"><label>Legal Status</label><select id="fl" onchange="af()"><option value="">All</option></select></div>
<div class="fg"><label>Oversight</label><select id="fo" onchange="af()"><option value="">All</option></select></div>
<div class="fa"><button class="btnsm btn2" onclick="cf()">Clear</button></div>
</div>

<div class="main">
<div class="mp"><div id="map"></div>
<div class="msel hidden" id="mb"><span class="badge" id="ml"></span></div>
<div class="mleg"><h4>Oversight</h4>
<div style="display:flex;align-items:center;gap:.375rem;margin-bottom:.25rem"><span style="width:12px;height:12px;border-radius:50%;background:#059669;display:inline-block"></span>High</div>
<div style="display:flex;align-items:center;gap:.375rem;margin-bottom:.25rem"><span style="width:12px;height:12px;border-radius:50%;background:#d97706;display:inline-block"></span>Medium</div>
<div style="display:flex;align-items:center;gap:.375rem;margin-bottom:.25rem"><span style="width:12px;height:12px;border-radius:50%;background:#dc2626;display:inline-block"></span>Low</div>
<div style="display:flex;align-items:center;gap:.375rem;margin-bottom:.25rem"><span style="width:12px;height:12px;border-radius:50%;background:#7c3aed;display:inline-block"></span>Variable</div>
</div></div>
<div class="tp"><div class="tt"><span id="rc">Loading...</span>
<div style="display:flex;gap:.375rem"><button class="btnsm btn2" onclick="expCSV()">📥 CSV</button><button class="btnsm btn2" onclick="expJSON()">📋 JSON</button></div>
</div>
<div class="tscr"><table><thead><tr>
<th onclick="st('procedure_name')">Procedure ▾</th>
<th onclick="st('jurisdiction_name')">Jurisdiction ▾</th>
<th onclick="st('legal_status')">Legal Status ▾</th>
<th onclick="st('oversight_quality')">Oversight ▾</th>
<th onclick="st('estimated_cost_range_usd')">Cost ▾</th>
<th onclick="st('modality')">Modality ▾</th>
<th>Detail</th>
</tr></thead>
<tbody id="tbdy"><tr><td colspan="7" class="loading">Loading data...</td></tr></tbody></table></div></div>
</div>
</div>

<div id="va" class="hidden"><div class="ac">
<div class="atabs">
<button class="atab active" onclick="sat('records')" id="tr">Access Records</button>
<button class="atab" onclick="sat('procedures')" id="tp2">Procedures</button>
<button class="atab" onclick="sat('jurisdictions')" id="tj">Jurisdictions</button>
<button class="atab" onclick="sat('import')" id="ti">Bulk Import</button>
</div>

<div id="ar">
<div class="fsec"><h3 id="rt">Add Access Record</h3>
<form id="rf" onsubmit="saveR(event)"><input type="hidden" id="rid">
<div class="frow"><div class="fg2"><label>Procedure</label><select id="rpid" required></select></div>
<div class="fg2"><label>Jurisdiction</label><select id="rjid" required></select></div></div>
<div class="frow"><div class="fg2"><label>Legal Status</label><select id="rls" required></select></div>
<div class="fg2"><label>Oversight Quality</label><select id="roq"></select></div></div>
<div class="frow"><div class="fg2"><label>Cost Range (USD)</label><input id="rcr" placeholder="$X,XXX - $X,XXX"></div>
<div class="fg2"><label>Last Verified</label><input type="date" id="rlv"></div></div>
<div class="fg2"><label>Access Pathway</label><textarea id="rap" rows="2"></textarea></div>
<div class="fg2"><label>Eligibility</label><textarea id="rel" rows="2"></textarea></div>
<div class="fg2"><label>Provider Requirements</label><textarea id="rpr" rows="2"></textarea></div>
<div class="fg2"><label>Residency/Travel</label><textarea id="rrn" rows="2"></textarea></div>
<div class="fg2"><label>Risk Notes</label><textarea id="rrk" rows="2"></textarea></div>
<div class="fg2"><label>Arbitrage Summary</label><textarea id="ras" rows="2"></textarea></div>
<div class="fg2"><label>Oversight Notes</label><textarea id="ron" rows="2"></textarea></div>
<div class="fg2"><label>Cost Notes</label><textarea id="rcn" rows="2"></textarea></div>
<div style="display:flex;gap:.5rem;margin-top:.75rem"><button type="submit" class="btn1">Save</button><button type="button" class="btn2" onclick="resetRF()">Cancel</button></div>
</form></div>
<h3 style="margin-bottom:.75rem">Access Records</h3>
<table class="atbl"><thead><tr><th>Procedure</th><th>Jurisdiction</th><th>Legal Status</th><th>Oversight</th><th>Cost</th><th>Actions</th></tr></thead>
<tbody id="atb"><tr><td colspan="6" class="loading">Loading...</td></tr></tbody></table>
</div>

<div id="ap" class="hidden">
<div class="fsec"><h3 id="pt">Add Procedure</h3>
<form id="pf" onsubmit="saveP(event)"><input type="hidden" id="pid">
<div class="frow"><div class="fg2"><label>Name</label><input id="pn" required></div>
<div class="fg2"><label>Modality</label><select id="pm" required></select></div></div>
<div class="frow"><div class="fg2"><label>Subcategory</label><input id="ps"></div>
<div class="fg2"><label>Typical US Cost</label><input id="pc" placeholder="$X,XXX"></div></div>
<div class="fg2"><label>Therapeutic Areas (comma-separated)</label><input id="pta" placeholder="Mental_Health, Depression"></div>
<div class="fg2"><label>Description</label><textarea id="pd" rows="3"></textarea></div>
<div class="fg2"><label>Indications</label><textarea id="pin" rows="2"></textarea></div>
<div style="display:flex;gap:.5rem;margin-top:.75rem"><button type="submit" class="btn1">Save</button><button type="button" class="btn2" onclick="resetPF()">Cancel</button></div>
</form></div>
<h3 style="margin-bottom:.75rem">Procedures</h3>
<table class="atbl"><thead><tr><th>Name</th><th>Modality</th><th>Subcategory</th><th>Therapeutic Areas</th><th>Actions</th></tr></thead>
<tbody id="apb"><tr><td colspan="5" class="loading">Loading...</td></tr></tbody></table>
</div>

<div id="aj" class="hidden">
<div class="fsec"><h3 id="jt">Add Jurisdiction</h3>
<form id="jf" onsubmit="saveJ(event)"><input type="hidden" id="jid">
<div class="frow"><div class="fg2"><label>Name</label><input id="jn" required></div>
<div class="fg2"><label>Type</label><select id="jty" required></select></div></div>
<div class="frow"><div class="fg2"><label>Country Code</label><input id="jcc" required maxlength="3"></div></div>
<div class="frow"><div class="fg2"><label>Latitude</label><input type="number" step="any" id="jla"></div>
<div class="fg2"><label>Longitude</label><input type="number" step="any" id="jlo"></div></div>
<div class="fg2"><label>Notes</label><textarea id="jno" rows="2"></textarea></div>
<div style="display:flex;gap:.5rem;margin-top:.75rem"><button type="submit" class="btn1">Save</button><button type="button" class="btn2" onclick="resetJF()">Cancel</button></div>
</form></div>
<h3 style="margin-bottom:.75rem">Jurisdictions</h3>
<table class="atbl"><thead><tr><th>Name</th><th>Type</th><th>Country</th><th>Coordinates</th><th>Actions</th></tr></thead>
<tbody id="ajb"><tr><td colspan="5" class="loading">Loading...</td></tr></tbody></table>
</div>

<div id="ai" class="hidden">
<div class="fsec"><h3>Bulk Import JSON</h3>
<p style="font-size:.8125rem;color:var(--txt2);margin-bottom:1rem">Paste JSON to import jurisdictions, procedures, and access records.</p>
<textarea id="bit" rows="12" placeholder='{"jurisdictions":[...],"procedures":[...],"access_records":[...]}'></textarea>
<button class="btn1 mt1" onclick="bi()">Import</button>
<div id="bir" class="mt1" style="font-size:.8125rem"></div></div>
</div>
</div></div>

<div id="dm" class="modal-overlay hidden">
<div class="modal"><button class="mc" onclick="cd2()">&times;</button><div id="dc"></div></div>
</div>

<footer class="footer">
<p><strong>⚠ DISCLAIMER:</strong> For informational purposes only. Not medical, legal, or travel advice. Verify with official sources. Use at your own risk.</p>
<p>Data updated: July 2025 | <a href="https://github.com/MattH55/osmf-research-tracker" target="_blank" rel="noopener">Source Code</a> | v0.1.0</p>
</footer>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="js/app.js"></script>
</body>
</html>"""

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(html)

# Verify
size = os.path.getsize(HTML_PATH)
print(f"Written {HTML_PATH}: {size} bytes, {html.count(chr(10))} lines")