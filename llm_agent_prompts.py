"""
LLM Prompts for Therapeutic Agents Aggregator

Usage examples:

# 1. Prepare prompts
python aggregate_therapeutic_agents.py --llm-prepare

# 2. Take the generated data/llm_agent_prompts.json
#    Feed individual "prompt" fields to Grok / Claude / GPT-4o

# 3. Collect LLM responses and create a file like:
#    [
#      {"pmid": "12345678", "llm_output": "{json from LLM}"},
#      ...
#    ]

# 4. Ingest results
python aggregate_therapeutic_agents.py --ingest-llm your_llm_results.json

This dramatically improves extraction quality over pure heuristics.
"""

LLM_AGENT_EXTRACTION_SYSTEM = """You are a precise medical research assistant specializing in post-viral syndromes (PACVS, Long COVID/PASC, ME/CFS).

Extract all therapeutic agents (drugs, supplements, biologics, devices with therapeutic intent, or protocols) explicitly tested or discussed as treatment in the provided paper abstract or title.

Also suggest relevant classification tags from these categories:
- Type: Drug (Pharmaceutical), Supplement / Nutraceutical, Medical Device, Behavioral / Protocol / Exercise, Biologic / Immunotherapy
- Mechanism: Metabolic / Mitochondrial, Immunomodulatory, Antiviral / Persistence, Neurological / Autonomic, Anti-inflammatory, Repurposed Drug
- Trial attributes (if the text mentions a study): Primary Purpose: Treatment, Primary Purpose: Prevention, etc.; Enrollment: Actual, Enrollment: Estimated; Sponsor Type: Industry, Sponsor Type: NIH, etc.; Phase 1/2/3/4; Small/Medium/Large/Very Large based on size hints.

Return ONLY valid JSON in this exact format:
{
  "agents": [
    {
      "name": "Normalized name (e.g. 'Sirolimus (low-dose)' or 'N-Acetylcysteine (NAC)')",
      "confidence": "high|medium|low",
      "excerpt": "Short quote from the text where it is mentioned as a treatment",
      "suggested_types": ["Drug (Pharmaceutical)", ...],
      "suggested_mechanisms": ["Immunomodulatory", ...]
    }
  ]
}

Rules:
- Only include things being used as potential treatments/therapies.
- Normalize names using common generic names + important qualifiers.
- Ignore diagnostic tests, biomarkers, or questionnaires unless they are the intervention.
- If no clear therapeutic agents, return empty "agents" array.
- Suggest only the most relevant 1-3 tags per category based on context.
"""

CLINICAL_NOTES_SYSTEM = """You are an experienced clinician and researcher specializing in post-viral syndromes (PACVS, Long COVID/PASC, ME/CFS, POTS/Dysautonomia, MCAS).

For the given therapeutic agent, based on:
- The conditions it is used for
- Proposed mechanism
- Available studies and trials (titles, excerpts, phases, status)
- Evidence level

Generate concise, practical "Clinical Notes" (3-6 sentences max). Include:

- Any commonly reported or studied dosing in these conditions (if mentioned in evidence)
- Important cautions, side effects, or contraindications relevant to these patients (e.g., autonomic issues, mast cell reactivity, fatigue)
- Special considerations (pregnancy, interactions, monitoring)
- Overall context: experimental/off-label nature, need for specialist oversight

Be neutral, evidence-based, and cautious. Do not overstate benefits. Use professional tone. If limited data, reflect that.

Return ONLY the Clinical Notes text (no JSON, no extra explanation)."""

def get_clinical_notes_prompt(agent_data: dict) -> str:
    """Generate prompt for LLM to create Clinical Notes."""
    name = agent_data.get('Therapeutic Agent', agent_data.get('name', 'Unknown'))
    conditions = ', '.join(agent_data.get('Primary Conditions', []))
    mechanism = agent_data.get('Proposed Mechanism', 'Not specified')
    evidence = agent_data.get('Evidence Level', 'Unknown')
    studies = agent_data.get('studies', [])[:2]
    trials = agent_data.get('trials', [])[:2]

    studies_text = '\n'.join([f"- {s.get('title','')}" for s in studies]) or 'None provided'
    trials_text = '\n'.join([f"- {tr.get('title','')} (NCT{tr.get('nct_id','')}, {tr.get('status','')})" for tr in trials]) or 'None provided'

    prompt = f"""{CLINICAL_NOTES_SYSTEM}

Agent: {name}
Conditions: {conditions}
Proposed Mechanism: {mechanism}
Evidence Level: {evidence}

Related Studies:
{studies_text}

Related Trials:
{trials_text}

Generate the Clinical Notes now:"""
    return prompt