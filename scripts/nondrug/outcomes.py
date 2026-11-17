"""Map a trial's PRIMARY outcome measures to outcome domains by keyword rules.

A trial can land in several domains (one per distinct primary outcome). Outcomes no rule
matches are counted as "unclassified" and shown as such; they are never silently dropped.
The rules are deliberately simple and auditable; their agreement with a hand-labelled sample
is reported by scripts/nondrug/check_outcome_rules.py.
"""
from __future__ import annotations

import re

DOMAINS = [
    ("fatigue", "Fatigue and energy",
     r"fatigue|tired|exhaust|energy level|vitality|\bfss\b|\bmfi\b|chalder|\bcfq\b|facit-?f|\bfas\b|checklist individual strength|\bcis\b"),
    ("pem", "Post-exertional symptoms",
     r"post-?exertion|\bpem\b|post-?exercise (symptom|malaise|fatigue)|dsq-?pem|exertional intolerance|crash"),
    ("cognition", "Cognition",
     r"cogniti|memory|attention|brain fog|executive function|\bmoca\b|\bmmse\b|processing speed|concentration|neuropsych|trail making|stroop|reaction time|verbal fluency"),
    ("mental", "Mood, anxiety and wellbeing",
     r"depress|anxiet|\bphq|\bgad-?7|\bhads\b|\bbdi\b|\bstai\b|mood|stress|ptsd|psycholog|mental health|well-?being|wellbeing|loneliness|resilience|suicid|panic|self-?efficacy|emotion|affect\b|distress|craving|motivation|coping|(disease|illness) acceptance|illness perception"),
    ("pain", "Pain",
     r"pain|\bvas\b|visual analog(ue)? scale|tender|headache|migraine (days|frequency|attacks)|\bbpi\b|mcgill|fibromyalgia impact|\bfiq\b|arthralgia|myalgia|neuropath"),
    ("sleep", "Sleep",
     r"sleep|insomnia|\bpsqi\b|\bisi\b|apnea|apnoea|\bahi\b|epworth|drowsi|circadian"),
    ("physical", "Physical function and exercise capacity",
     r"6[- ]?min(ute)? walk|\b6mwt\b|\b6mwd\b|walk(ing)? (test|distance|speed)|exercise (capacity|tolerance)|\bvo2|peak oxygen|aerobic capacity|cardiorespiratory fitness|grip|muscle (strength|power|mass)|physical (function|performance|activity|capacity)|mobility|gait|balance|sit[- ]to[- ]stand|\bsppb\b|functional (capacity|status|independence)|disability|activities of daily living|\badl\b|step(s| count)|timed up and go|\btug\b|posture|kyphosis|range of motion|flexibility|joint angle|chair rise|chair stand|step (target|goal)|endurance time|exercise testing"),
    ("autonomic", "Heart rate, blood pressure and autonomic",
     r"orthostatic|heart rate|blood pressure|cardiac output|cardiovascular|hemodynamic|haemodynamic|vascular|endothelial|arterial stiffness|hypertension|\bpots\b|tilt|autonomic|compass-?31|heart rate variability|\bhrv\b|syncope|palpitation|arrhythm|atrial fibrillation"),
    ("respiratory", "Breathing and lung function",
     r"dyspn|breathless|shortness of breath|lung function|\bfev1|\bfvc\b|spirometr|respiratory|asthma control|\bacq\b|\bact\b score|oxygen saturation|\bspo2\b|exacerbation of copd|\bcat\b score|mmrc|cough|airway|oscillometr|peak flow|\bpef\b"),
    ("qol", "Quality of life",
     r"quality of life|\bqol\b|\bhrqol\b|sf-?36|sf-?12|eq-?5d|promis|whoqol|health status|patient global impression|\bpgic\b|health-related"),
    ("metabolic", "Weight and metabolic markers",
     r"hba1c|glyc(at|em)|glucose|insulin|body weight|weight (loss|change)|\bbmi\b|body mass|waist|body fat|fat mass|adipos|lipid|cholesterol|triglycer|\bldl\b|\bhdl\b|metabolic|\bhoma\b|insulin resistance|lean mass|weight[- ]for[- ]|growth|anthropometr"),
    ("biomarker", "Inflammation and other biomarkers",
     r"inflammat|\bcrp\b|c-reactive|cytokine|interleukin|\bil-?\d|tnf|biomarker|immun|antibod|microbio|microbiome|oxidative|vitamin d level|serum|plasma|blood level|bone mineral density|\bbmd\b|\bdna\b|\brna\b|viral load|virolog|antigen|\bcd4\b|evoked potential|\beeg\b|\bmri\b|imaging|cell count|ferritin|hemoglobin|haemoglobin|cortisol|hormone|enzyme|gene expression|connectivity|histolog|biopsy|villous|ultrasonograph|elastograph|bone (mineral )?density|\bdxa\b|renal function|kidney function|\begfr\b|creatinine|albuminuria|liver function"),
    ("symptoms", "Symptom severity and disease activity",
     r"symptom|severity|disease activity|\bdas-?28\b|flare|relapse|remission|seizure|exacerbation|attack|(frequency|quantity|days) of (alcohol|drinking|smoking|use)|abstinen|clinical global|\bcgi\b|response rate|endoscopic|tinnitus|severity score|\bhaq\b|\bacr ?20\b|pasi|easi|scorad|itch|pruritus|nausea|bowel|\bibs-?sss\b|rating scale|activity score|\buas7?\b|incontinence|urgency"),
    ("events", "Clinical events, survival and healthcare use",
     r"surviv|mortality|death|hospitali|admission|readmission|length of (hospital )?stay|incidence|infection|composite (end ?point|outcome)|(cardiovascular|cardiac|vascular|thromboembolic|thrombotic|clinical|cerebrovascular|coronary|major) events?\b|\bmace\b|\bmarce\b|recurrence|progression|time to (first|recurrence|progression|event)|chest tube|emergency|intensive care|\bicu\b|amputation|fracture|stroke|myocardial infarction|reintervention|complete remission|overall response|(opioid|analgesic|medication) (consumption|use|requirement)"),
    ("feasibility", "Feasibility, adherence and safety",
     r"feasib|adherence|acceptab|recruitment|retention|attrition|compliance|completion rate|dropout|drop-out|safety|adverse|tolerab|usability|satisfaction|fidelity|uptake|engagement|sessions? (completed|attended)|attendance|number of sessions|frequency of use|\buse of\b|sustainment|implementation|working alliance|complication|usage|participants who completed|completed the (study|intervention|program)"),
]
DOMAIN_LABEL = {d: label for d, label, _ in DOMAINS}
DOMAIN_LABEL["unclassified"] = "Not classified by the rules"
_RX = [(d, re.compile(p, re.I)) for d, _, p in DOMAINS]


_PRIORITY = re.compile(r"adverse|safety|complication|tolerab|feasib|adherence|acceptab|retention|recruitment|attendance|sessions? (completed|attended)|frequency of use|usage|who completed", re.I)


def domains_for_outcome(measure: str, description: str = "") -> list[str]:
    """Domains for one outcome. The measure decides; the description is used only if the measure matches nothing.
    Safety, feasibility and adherence outcomes are labelled as such first, whatever else they mention."""
    if _PRIORITY.search(measure or ""):
        return ["feasibility"]
    hits = [d for d, rx in _RX if rx.search(measure or "")]
    if not hits and description:
        hits = [d for d, rx in _RX if rx.search(description[:300])]
    return hits[:2]  # an outcome rarely spans more than two domains; cap to avoid over-counting


def domains_for_trial(primary_outcomes: list[dict]) -> list[str]:
    seen: list[str] = []
    for o in primary_outcomes or []:
        ds = domains_for_outcome(o.get("measure", ""), o.get("description", ""))
        for d in ds or ["unclassified"]:
            if d not in seen:
                seen.append(d)
    if len(seen) > 1 and "unclassified" in seen:
        seen.remove("unclassified")
    return seen or ["unclassified"]
