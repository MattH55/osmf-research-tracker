"""Non-drug intervention taxonomy shared by the non-drug evidence map, the evidence-gap
maps, the supplement safety pages and the condition briefs.

An intervention arm from ClinicalTrials.gov is assigned to a class from TWO signals:

1. The registry's own ``interventionType``.
   * DRUG, BIOLOGICAL, GENETIC, RADIATION, COMBINATION_PRODUCT -> never non-drug.
   * BEHAVIORAL, DEVICE, DIETARY_SUPPLEMENT -> non-drug; the name picks the class, and an
     unmatched name falls back to a broad "other ..." class for that type.
   * OTHER, PROCEDURE, DIAGNOSTIC_TEST -> included only when the NAME matches a class.
     (Registries type a fasting protocol as OTHER and acupuncture as PROCEDURE.)
2. The arm role. An intervention that only appears in PLACEBO_COMPARATOR, SHAM_COMPARATOR,
   NO_INTERVENTION or ACTIVE_COMPARATOR arms is a control, not the thing under study, and is
   excluded. This is the pair quality gate: saline used as a diluent or placebo never counts.

Names that describe assessments, sampling, imaging, usual care or a medicine are excluded
whatever their registry type. Nothing here grades efficacy: classes only say what was studied.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

NON_DRUG_TYPES = {"BEHAVIORAL", "DIETARY_SUPPLEMENT"}  # DEVICE needs a name match: unmatched devices are mostly surgical or hospital equipment
NAME_ONLY_TYPES = {"OTHER", "PROCEDURE", "DIAGNOSTIC_TEST", "UNKNOWN", ""}
DRUG_TYPES = {"DRUG", "BIOLOGICAL", "GENETIC", "RADIATION", "COMBINATION_PRODUCT"}
CONTROL_ROLES = {"PLACEBO_COMPARATOR", "SHAM_COMPARATOR", "NO_INTERVENTION", "ACTIVE_COMPARATOR"}


@dataclass(frozen=True)
class Klass:
    id: str
    label: str
    group: str
    pattern: str
    blurb: str  # one neutral sentence: what the class contains, never whether it works


GROUPS = [
    ("exercise", "Exercise and physical activity"),
    ("rehab", "Rehabilitation and therapy services"),
    ("breathing", "Breathing and respiratory training"),
    ("mindbody", "Mind-body and psychological approaches"),
    ("cognitive", "Cognitive training and education"),
    ("diet", "Diet, fasting and nutrition"),
    ("sleep", "Sleep and circadian approaches"),
    ("neuromod", "Neuromodulation and electrical stimulation"),
    ("physical", "Oxygen, light, temperature and manual therapies"),
    ("supplement", "Supplements and nutraceuticals"),
    ("otherdevice", "Other devices and digital tools"),
    ("care", "Care delivery and health services"),
]
GROUP_LABEL = dict(GROUPS)

# Order matters: the first match wins, so specific classes come before broad ones.
CLASSES: list[Klass] = [
    # breathing (before exercise: "breathing exercises")
    Klass("breathing-training", "Breathing and respiratory muscle training", "breathing",
          r"inspiratory|expiratory|respiratory muscle|carbon dioxide ramp|\bco2\b (training|ramp)|capnometry|diaphragm|breathing (exercise|training|retraining|technique|pattern)|pursed[- ]lip|diaphragmatic breath|resonan(ce|t) breathing|slow[- ]paced breathing|incentive spirometer|buteyko|singing for lung|\bbreath(work|ing)\b",
          "Structured breathing techniques and training of the breathing muscles."),
    Klass("pulmonary-rehab", "Pulmonary rehabilitation", "breathing", r"pulmonary rehab|respiratory rehab|cardiopulmonary rehab|cardio-?pulmonary rehab",
          "Supervised rehabilitation programmes for people with lung or breathing problems."),
    # neuromodulation (before "training")
    Klass("transcranial-stimulation", "Transcranial brain stimulation (tDCS, TMS)", "neuromod",
          r"transcrani|transcraneal|\btdcs\b|\brtms\b|\btms\b|theta[- ]burst|\bhd-?tdcs\b|\btacs\b|\btrns\b",
          "Non-invasive stimulation of the brain through the scalp with weak electrical currents or magnetic pulses."),
    Klass("vagus-stimulation", "Vagus and cranial nerve stimulation", "neuromod",
          r"vagus|vagal|\bt?a?vns\b|\btvns\b|auricular (nerve )?stim|trigeminal nerve stim|ear stimulation",
          "Stimulation of the vagus or other cranial nerves, usually through the ear or neck skin."),
    Klass("electrical-stimulation", "Peripheral electrical and electromagnetic stimulation", "neuromod",
          r"\btens\b|transcutaneous electrical|neuromuscular electrical|\bnmes\b|electro-?stimulation|electromyostimulation|pulsed electromagnetic|\bpemf\b|electrical stimulation|interferential|scrambler",
          "Electrical or electromagnetic stimulation applied to nerves or muscles outside the brain."),
    Klass("neuromodulation-other", "Other neuromodulation", "neuromod", r"neuromodulat|neurofeedback|neuro-?stimulat",
          "Other approaches that aim to change nervous-system activity with a device."),
    # oxygen, light, temperature, manual
    Klass("hyperbaric-oxygen", "Hyperbaric oxygen therapy", "physical", r"hyperbaric|\bhbot\b|\bhbo2?\b",
          "Breathing oxygen inside a pressurised chamber."),
    Klass("hypoxia-hyperoxia", "Intermittent hypoxia and hyperoxia", "physical", r"hypoxi|hyperoxi|altitude (training|tent)|\bihht\b|hi-?ox",
          "Controlled periods of breathing lower- or higher-oxygen air."),
    Klass("light-laser", "Light and laser therapy (photobiomodulation)", "physical",
          r"photobiomodulat|low[- ]level laser|\blllt\b|laser (therapy|treatment)|light therapy|bright light|red light|near[- ]infrared|phototherap|blue light",
          "Exposure of the body or eyes to specific wavelengths of light or low-power laser."),
    Klass("thermal-hydro", "Heat, cold and water therapies", "physical",
          r"sauna|cryotherap|cold[- ]water|cold exposure|cold immersion|whole[- ]body cryo|hydrotherap|balneo|spa therap|thermal therap|heat therap|hyperthermi|kneipp|aquatic",
          "Treatments using heat, cold or water, including sauna, cold immersion and spa therapy."),
    Klass("acupuncture", "Acupuncture and related techniques", "physical",
          r"acupunct|acupress|moxibustion|cupping|dry needling|auriculotherap",
          "Needling or pressure at specific body points, including electroacupuncture and acupressure."),
    Klass("manual-therapy", "Massage, osteopathy and manual therapy", "physical",
          r"massage|manual (therap|lymph)|osteopath|chiropract|spinal manipulat|myofascial|lymphatic drainage|reflexology|mobili[sz]ation|craniosacral",
          "Hands-on treatment such as massage, manipulation and lymphatic drainage."),
    Klass("shockwave-vibration", "Shock-wave and vibration therapy", "physical",
          r"shock ?wave|eswt|whole[- ]body vibration|vibration therap|focal vibration",
          "Mechanical shock waves or vibration applied to the body."),
    Klass("compression-devices", "Compression and counterpulsation", "physical", r"compression|counterpulsation|\beecp\b|abdominal binder",
          "Garments or devices that apply external pressure to the limbs or abdomen."),
    # exercise
    Klass("yoga-taichi-qigong", "Yoga, tai chi, qigong and pilates", "mindbody", r"\byoga\b|tai ?chi|taiji|qigong|qi gong|baduanjin|pilates",
          "Movement practices that combine posture, breathing and attention."),
    Klass("resistance-training", "Resistance and strength training", "exercise",
          r"resistance (exercise|training)|strength(ening)? (exercise|training)|weight training|muscle strengthening|power training",
          "Exercise against resistance to build muscle strength."),
    Klass("aerobic-exercise", "Aerobic and endurance exercise", "exercise",
          r"aerobic|endurance|\bhiit\b|high[- ]intensity interval|interval training|treadmill|cycl(e|ing) (exercise|training|ergometer)|ergometer|walking|nordic walk|running|jogging|swimming|dance",
          "Sustained or interval exercise that raises heart rate, such as walking, cycling and swimming."),
    Klass("pacing-activity", "Pacing and activity management", "exercise",
          r"pacing|energy (management|conservation)|activity management|graded activity|activity diary|sub-?symptom threshold",
          "Planning and limiting activity to stay within energy limits, or gradually adjusting it."),
    Klass("exercise-general", "Exercise programmes (mixed or unspecified)", "exercise",
          r"exercis|physical activity|physical training|training program|concurrent training|\bapa\b|adapted physical|fitness|sedentary|sitting|stretching|step count|movement",
          "Exercise programmes that combine several types of exercise or do not specify one."),
    # rehabilitation and therapy services
    Klass("physiotherapy", "Physiotherapy and physical therapy", "rehab", r"physiotherap|physical therap|kinesitherap|vestibular rehab|balance training|gait training",
          "Treatment and exercise prescribed and supervised by physiotherapists."),
    Klass("rehabilitation", "Multidisciplinary and other rehabilitation", "rehab",
          r"rehabilit|\brehab\b|telerehab|occupational therap|speech (and language )?therap|vocational|return to work|multidisciplinary|multimodal",
          "Rehabilitation programmes, including occupational, speech and multidisciplinary care."),
    # addiction-focused behavioural treatments
    Klass("substance-behavioural", "Behavioural treatment for alcohol, smoking and drug use", "mindbody",
          r"contingency management|motivational enhancement|brief (alcohol|intervention)|smoking cessation|quitline|tobacco|alcohol (use|intervention)|relapse prevention|harm reduction|12[- ]step",
          "Counselling and incentive-based programmes to reduce alcohol, tobacco or drug use."),
    # mind-body and psychological
    Klass("cbt", "Cognitive behavioural and related therapies", "mindbody",
          r"cognitive[- ]behavio|\bcbt\b|\bcbt-i\b|acceptance and commitment|\bact\b therapy|dialectical|problem[- ]solving therapy|behavio(u)?ral activation|compassion[- ]focused|metacognitive|schema therapy",
          "Structured talking therapies that work on thoughts and behaviours, delivered in person or online."),
    Klass("mindfulness-relaxation", "Mindfulness, meditation and relaxation", "mindbody",
          r"mindful|meditat|\bmbsr\b|\bmbct\b|relaxation|guided imagery|hypno|autogenic|progressive muscle|body scan|breathwork",
          "Attention and relaxation practices, including meditation, hypnosis and guided imagery."),
    Klass("biofeedback", "Biofeedback", "mindbody", r"biofeedback|heart rate variability|\bhrv\b",
          "Using real-time readings of body signals, such as heart rate variability, to learn self-regulation."),
    Klass("psychotherapy-support", "Psychotherapy, counselling and peer support", "mindbody",
          r"psychotherap|counsel|psycho-?education|support group|peer support|motivational interview|psycholog|amygdala|neural retraining|trauma|emdr|art therap|music therap|music|dance therap|creative",
          "Psychological support beyond structured CBT, including counselling, peer groups and creative therapies."),
    # cognitive and education
    Klass("cognitive-training", "Cognitive training and remediation", "cognitive",
          r"cognitive (training|rehab|remediation|stimulation|exercise)|brain (training|health|games)|memory training|attention training|processing speed|reaction time|computeri[sz]ed (cognitive|training)|brainhq",
          "Exercises, often computer-based, aimed at memory, attention and thinking speed."),
    Klass("education-self-management", "Education, coaching and self-management", "cognitive",
          r"educat|self[- ]management|self[- ]care|coaching|health literacy|decision aid|lifestyle (intervention|program|modification|medicine)|health promotion|case management|care pathway|nurse[- ]led|text messag|smartphone|mobile app|\bapp\b|web[- ]based|online program|internet[- ]delivered|telehealth|telemedicine|digital (program|intervention|therap)",
          "Programmes that teach or support people to manage a condition, including digital and remote ones."),
    # diet
    Klass("fasting", "Fasting and time-restricted eating", "diet",
          r"fasting|time[- ]restricted|eating window|caloric restriction|calorie restriction|fasting[- ]mimicking|buchinger",
          "Periods without food or with restricted eating times."),
    Klass("diet-pattern", "Dietary patterns and specific diets", "diet",
          r"\bdiet\b|dietary (intervention|pattern|advice|counsel|approach|program|modification|recommendation)|mediterranean|ketogenic|low[- ]carb|low[- ]fat|low[- ]sugar|low[- ]fodmap|gluten[- ]free|vegan|vegetarian|plant[- ]based|anti-?inflammatory diet|dash diet|paleo|elimination diet|meal replacement|formula diet|very low calorie|weight (loss|management) program",
          "Changes to what people eat, such as Mediterranean, ketogenic, low-FODMAP or plant-based diets."),
    Klass("nutrition-support", "Nutrition counselling and food-based products", "diet",
          r"nutrition(al)? (counsel|education|intervention|therap|support|program)|dietitian|oral nutrition|nutritional (blend|drink|formula)|functional food|fortified|hydrogen[- ]rich water|hydrogen water|juice|fiber|fibre|bran|oats|nuts|olive oil|cocoa|dark chocolate|green tea|coffee|honey|kefir|yogurt|fermented food",
          "Dietitian support and specific foods or food-based products."),
    Klass("airway-pressure", "Positive airway pressure and oral appliances", "sleep",
          r"cpap|apap|bipap|positive airway pressure|mandibular advancement|oral appliance|hypoglossal",
          "Machines that keep the airway open during sleep, and mouth splints for sleep apnoea."),
    # sleep
    Klass("sleep", "Sleep and circadian interventions", "sleep",
          r"sleep|insomnia|circadian|chronotherap|nap\b|bedtime|sleep hygiene",
          "Approaches that target sleep quality or timing, other than medicines."),
    # supplements (specific first)
    Klass("vitamin-d", "Vitamin D", "supplement", r"vitamin d\b|vitamin d3|vitamin d2|cholecalciferol|ergocalciferol|calcifediol|\b25-?oh",
          "Vitamin D taken as a supplement."),
    Klass("omega-3", "Omega-3 fatty acids and fish oil", "supplement", r"omega[- ]?3|fish oil|\bepa\b|\bdha\b|krill oil|eicosapentaenoic|docosahexaenoic|algal oil",
          "Omega-3 fatty acids from fish, krill or algae oil."),
    Klass("probiotics", "Probiotics, prebiotics and synbiotics", "supplement",
          r"probiotic|prebiotic|synbiotic|lactobacill|bifidobacter|saccharomyces|streptococcus thermophilus|postbiotic|\binulin\b|galacto-?oligosaccharide|fructo-?oligosaccharide",
          "Live bacteria or yeasts, and the fibres that feed them, taken to change the gut microbiome."),
    Klass("coq10", "Coenzyme Q10", "supplement", r"coenzyme q|\bcoq-?10\b|ubiquinol|ubiquinone|ubidecarenone",
          "Coenzyme Q10 (ubiquinone or ubiquinol) taken as a supplement."),
    Klass("nad-precursors", "NAD+ precursors (nicotinamide riboside, NMN)", "supplement",
          r"nicotinamide riboside|\bnmn\b|nicotinamide mononucleotide|\bnad\+?\b|niagen",
          "Supplements intended to raise NAD+ levels, such as nicotinamide riboside."),
    Klass("nac", "N-acetylcysteine", "supplement", r"n-?acetyl-?\s?l?-?cysteine|\bnac\b",
          "N-acetylcysteine (NAC) taken as a supplement."),
    Klass("magnesium", "Magnesium", "supplement", r"magnesium", "Magnesium taken as a supplement."),
    Klass("zinc", "Zinc", "supplement", r"\bzinc\b", "Zinc taken as a supplement."),
    Klass("melatonin", "Melatonin", "supplement", r"melatonin", "Melatonin taken as a supplement."),
    Klass("creatine", "Creatine", "supplement", r"creatine", "Creatine taken as a supplement."),
    Klass("vitamin-c", "Vitamin C", "supplement", r"vitamin c\b|ascorb", "Vitamin C taken as a supplement."),
    Klass("b-vitamins", "B vitamins and folate", "supplement",
          r"vitamin b|\bb12\b|cobalamin|folate|folic acid|thiamin|riboflavin|niacin\b|pyridox|\bb6\b|biotin|methylfolate",
          "B vitamins and folate taken as supplements."),
    Klass("curcumin-polyphenols", "Curcumin and other polyphenols", "supplement",
          r"curcumin|turmeric|quercetin|resveratrol|polyphenol|flavonoid|luteolin|\begcg\b|pycnogenol|anthocyanin|sulforaphane|hesperidin|\brutin\b",
          "Plant compounds such as curcumin, quercetin and resveratrol, taken as supplements."),
    Klass("amino-acids-protein", "Amino acids and protein supplements", "supplement",
          r"amino acid|arginine|citrulline|glutamine|glycine|taurine|carnitine|leucine|\bbcaa\b|whey|protein supplement|collagen|\bl-?serine\b|phosphoserine|tryptophan|ornithine|theanine",
          "Individual amino acids or protein powders taken as supplements."),
    Klass("herbal-tcm", "Herbal medicines and traditional formulas", "supplement",
          r"herbal|\bherb\b|traditional chinese|\btcm\b|granule|decoction|kampo|ayurved|extract|ginseng|ginkgo|ashwagandha|saffron|berberine|tincture|rhodiola|astragalus|echinacea|cannabidiol|velvet antler|mushroom|reishi|cordyceps|lion'?s mane",
          "Plant-based products and traditional formulas, including extracts and granules."),
    Klass("vitamins-minerals-other", "Other vitamins, minerals and multivitamins", "supplement",
          r"vitamin|multivitamin|mineral|selenium|iron\b|calcium|iodine|potassium|vitamin e\b|vitamin k|trace element|electrolyte",
          "Other vitamins and minerals, alone or as multivitamins."),
    Klass("supplement-other", "Other supplements and nutraceuticals", "supplement",
          r"supplement|nutraceutical|ketone ester|beta-?hydroxybutyrate|\bpea\b|palmitoylethanolamide|alpha-?lipoic|spermidine|d-?ribose|methylene|glutathione|lactoferrin",
          "Supplements that do not fit a more specific class."),
    # care delivery
    Klass("care-delivery", "Care coordination, navigation and outreach", "care",
          r"navigat|outreach|reminder|phone call|telephone|collaborative care|care coordinat|community health worker|chw|transition(al)? care|discharge|home visit|follow-up call|integrated care|stepped care|pharmacist|primary care",
          "Ways of organising care, such as patient navigators, reminders, outreach and collaborative care."),
    # devices and digital
    Klass("virtual-reality", "Virtual reality", "otherdevice", r"virtual reality|\bvr\b|immersive", "Treatment or training delivered in virtual reality."),
    Klass("wearables-monitoring", "Wearables and monitoring devices", "otherdevice",
          r"wearable|smartwatch|activity tracker|pedometer|accelerometer|continuous glucose monitor|\bcgm\b|remote monitoring|monitoring device",
          "Wearable or home devices that track the body, used as part of an intervention."),
]

FALLBACK_BY_TYPE = {
    "BEHAVIORAL": Klass("behavioural-other", "Other behavioural interventions", "cognitive", r"$^",
                        "Behavioural interventions registered as such that do not fit a more specific class."),
    "DIETARY_SUPPLEMENT": Klass("supplement-other", "Other supplements and nutraceuticals", "supplement", r"$^",
                                "Supplements that do not fit a more specific class."),
}

ALL_CLASSES = {k.id: k for k in CLASSES}
for _k in FALLBACK_BY_TYPE.values():
    ALL_CLASSES.setdefault(_k.id, _k)

_COMPILED = [(k, re.compile(k.pattern, re.I)) for k in CLASSES]

# Not interventions at all: controls, assessments, sampling, imaging, usual care.
EXCLUDE_NAME = re.compile(
    r"placebo|\bsham\b|usual care|standard (of )?care|standard (treatment|therapy)|treatment as usual|\btau\b|"
    r"wait[- ]?list|no intervention|no treatment|attention control|control (group|condition|arm)|^control$|"
    r"questionnaire|survey|interview\b|assessment|measurement|evaluation|screening|blood (draw|sample|test)|"
    r"sampl(e|ing)|biopsy|\bmri\b|\bct scan\b|\bpet\b|imaging|ultrasound(?! stimulation)|x-ray|ecg|\beeg\b|"
    r"spirometry\b|exercise test|stress test|tilt[- ]table test|cardiopulmonary exercise test|\bcpet\b|"
    r"observation|follow[- ]up|data collection|registry|cohort|diagnostic|^intervention( group)?$|^experimental$|"
    r"^device$|^dietary supplements?$|^behavioral$|^other$|^no\b|surgery|surgical|transplant|implant(ation)?\b|"
    r"injection|infusion|intravenous|vaccin|plasma|apheresis",
    re.I,
)
# Medicine-like names that sometimes arrive typed OTHER or DIETARY_SUPPLEMENT.
DRUG_NAME = re.compile(
    r"mab\b|nib\b|olol\b|pril\b|sartan\b|statin\b|azole\b|cycline\b|mycin\b|vir\b|parin\b|lukast\b|xaban\b|"
    r"gliptin\b|gliflozin\b|glutide\b|setron\b|tidine\b|semide\b|thiazide|naltrexone|metformin|ivermectin|prednis|"
    r"dexameth|budesonide|formoterol|salbutamol|albuterol|cetirizine|loratadine|antihistamin|nirmatrelvir|"
    r"remdesivir|colchicine|aspirin|ibuprofen|naproxen|ketamine|psilocybin|steroid|cortisone|midodrine|"
    r"ivabradine|pyridostigmine|immunoglobulin|\bivig\b|\b\d+(\.\d+)?\s?mg\b|\bmg/kg\b|tablet|capsule|hydrochloride",
    re.I,
)


# Supplement trials are often registered with type DRUG (vitamin D, melatonin, probiotics...).
# For these clearly named, specific supplement classes a DRUG/BIOLOGICAL registry type is accepted.
# Herbal extracts and "other supplements" registered as drugs are NOT, since those are often
# investigational botanical medicines.
# Not vitamin C, magnesium, zinc, NAC or amino acids: registered as drugs, those are often intravenous or
# prescription uses (magnesium sulfate for acute asthma, IV ascorbate in cancer, IV NAC), checked 2026-11-16.
SUPPLEMENT_OVERRIDE = {"vitamin-d", "omega-3", "probiotics", "coq10", "nad-precursors", "melatonin", "creatine",
                       "b-vitamins", "curcumin-polyphenols"}
# A drug-registered "supplement" is rejected if its name also names a medicine, a salt form or an injectable route.
OVERRIDE_REJECT = re.compile(r"sulfate|sulphate|chloride|intravenous|iv|infusion|injection|inject|nebuli|parenteral|"
                             r"\+|plus |with |combined|combination|and (?!fish)", re.I)


def classify(name: str, itype: str) -> Klass | None:
    """Return the non-drug class for one intervention, or None if it is not a non-drug intervention."""
    itype = (itype or "").upper()
    if itype in DRUG_TYPES:
        n = " ".join((name or "").split())
        if itype in ("DRUG", "BIOLOGICAL") and not EXCLUDE_NAME.search(n) and not DRUG_NAME.search(n) and not OVERRIDE_REJECT.search(n):
            for k, rx in _COMPILED:
                if k.id in SUPPLEMENT_OVERRIDE and rx.search(n):
                    return k
        return None
    n = " ".join((name or "").split())
    if len(n) < 3 or EXCLUDE_NAME.search(n):
        return None
    if DRUG_NAME.search(n) and itype != "DEVICE":
        return None
    for k, rx in _COMPILED:
        if rx.search(n):
            return k
    if itype in NON_DRUG_TYPES:
        return FALLBACK_BY_TYPE[itype]
    return None


def is_studied_arm(arm_roles: list[str]) -> bool:
    """True when the intervention is part of what the trial tests (not only a control arm)."""
    roles = {r for r in (arm_roles or []) if r}
    if not roles:
        return True  # single-group or roles not recorded
    return not roles <= CONTROL_ROLES
