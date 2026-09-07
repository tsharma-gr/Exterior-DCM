import os
import json
import time
from openai import OpenAI
from dotenv import load_dotenv
from logger_config import logger

load_dotenv()

class AIClassifier:
    def __init__(self):
        base_url = os.getenv("OPENAI_BASE_URL")
        if base_url:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=base_url, timeout=60.0)
            logger.info(f"Connecting to custom LLM endpoint: {base_url} with 60s timeout")
        else:
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=60.0)
            
        # Load model from .env, default to gpt-4o-mini if not set
        self.model = os.getenv("AI_MODEL", "gpt-4o-mini")   
        logger.info(f"AI Classifier initialized using model: {self.model}")

    def classify_candidate(self, cv_text, expected_name="Unknown"):
        logger.info(f"Starting Specialist Recruitment Screening for: {expected_name}...")
        
        # Truncate CV text to prevent token limit errors
        # Read 100% of full CV text without artificial character limits
            
        from datetime import datetime
        current_date_str = datetime.now().strftime("%B %Y")

        system_prompt = f"""
You are a specialist recruitment screening AI for the façade, curtain walling, cladding, roofing, glazing, and building envelope industry.
EXPECTED CANDIDATE: {expected_name}

Your job is to classify ONLY WHITE-COLLAR candidates.

You must follow a STRICT STEP-BY-STEP FILTERING PROCESS.

---

## STEP 1 — CURRENT POSITION CHECK (MANDATORY)

First identify the candidate’s CURRENT or MOST RECENT job title explicitly from the **Work Experience / Employment History** section of the CV text. (Do NOT take the title from the CV header or profile summary if it differs from their actual current job).

ONLY continue evaluation if the current/recent position clearly matches one of these WHITE-COLLAR roles:

Approved WHITE-COLLAR roles include:
**Design & Pre-Construction:**
* Facade Designer, Curtain Wall Designer, Glazing Designer
* CAD Technician (Exteriors), Technical Designer
* Design Manager, Design Director, Design co-ordinator, Draughtsmen, draughtsman
* Estimator, Senior Estimator (Façade/Cladding/Roofing), Estimating Manager, Estimating Director
* Pre-Construction Manager / Director
* Technical Manager
* Drawing Office Manager

**Commercial:**
* Quantity Surveyor (QS), Senior QS, Commercial Manager, Commercial Director
* Buyer, Planner

**Operations & Project Delivery:**
* Project Manager, Senior Project Manager, Project Director (Cladding/Facade Projects)
* Contracts Manager, Contracts Director
* Operations Manager, Operations Director

**Bidding:**
* Bid Manager, Bid Director, Bid Coordinator, Bidding Manager

**Leadership:**
* Regional Director (Façade, Roofing, Envelope, etc.)
* Site Manager, Site Director, Site Supervisor

If the CURRENT or MOST RECENT (last 3-5 years only) role does NOT closely match these white-collar positions:
* Immediately classify as UNFIT
* Do not continue further evaluation

NOTE: Slight semantic variations, expanded titles, or prefixes/suffixes are ACCEPTABLE. If the candidate's title contains the core word from the whitelist (e.g., "Project Buyer" contains "Buyer", "Senior Estimator" contains "Estimator"), it is a MATCH. Allow reasonable flexibility as long as the core role aligns perfectly with the approved whitelist.

IMPORTANT:
IMPORTANT: Reject blue-collar or trade/site roles including: Installer, Cladder, Roofer, Glazier, Fabricator, Welder, Fixer, Operative, Labourer, Fitter, Tradesman, and exactly "Facade Engineer" or "Façade Engineer".
ALSO REJECT factory-based manufacturing roles: Production Manager, Factory Manager, Plant Manager, or General Manager (unless they explicitly manage site installation projects).

NOTE ON MANAGEMENT ROLES:
"Site Manager", "Site Director", and "Site Supervisor" (or combinations like "Supervisor/Site Manager") ARE recognized WHITE-COLLAR project delivery titles in this industry. Do NOT automatically reject them as "blue-collar/tradesmen" just because of the title.
HOWEVER, they are NOT automatically FIT. They MUST still pass the strict CAREER SPECIALIZATION rules below. A Site Manager from a general contractor who managed a recladding project is UNFIT.

---

## STEP 1B — SECTOR RELEVANCE CHECK (MANDATORY)

A matching white-collar job title alone is NOT sufficient for FIT classification.
The candidate must ALSO demonstrate clear and recent experience within: façade, curtain walling, cladding, glazing, roofing, building envelope, façade remediation, or specialist exterior systems.

CRITICAL SECTOR NOTE: "Roofing" (e.g., flat roofing, single ply, Bauder, Kemperol) is a fully valid, standalone specialization. If a candidate is a specialist in Commercial/Flat Roofing, they DO NOT need to have façade or cladding experience. They are a MATCH for the sector check.

Candidates with matching titles but working mainly in unrelated sectors (e.g. IT, environmental, administration, marketing, oil & gas, generic bid coordination, unrelated architecture) must be classified as UNFIT unless strong façade/building-envelope specialization is clearly evidenced.


FUZZY CAREER TRAJECTORY RULE: If the current title does NOT exactly match the whitelist above, do NOT reject immediately. Review the candidate's full career history and apply the following flexible logic:

- If the candidate's current role is in an ADJACENT commercial, surveying, or construction management position (e.g. Senior Quantity Surveyor, Commercial Surveyor, Project Coordinator, Senior Estimator, Pre-Construction Manager, Contracts Manager) AND they have demonstrable experience working on exterior cladding, facades, SFS, curtain walling, or rainscreen projects in a PREVIOUS role (within the last 7 years), classify as FIT.
- If the candidate has used facade or cladding-specific terminology in their career history (e.g. cladding systems, curtain wall, SFS framing, render, rainscreen, brick slips, EWI), treat this as strong evidence of exterior sector involvement.
- Only classify as UNFIT at Step 1 if the current role AND entire career history show NO connection to construction, surveying, or building envelope work whatsoever (e.g. retail, IT, healthcare, hospitality, or fully unrelated sector).

---

## STEP 2 — EXTERIOR PRODUCTS / SERVICES CHECK

If the candidate passed Step 1, check whether their experience clearly involves specialist exterior systems/services.
Relevant systems/products/services include:
* Façade Systems (unitized curtain wall, stick systems, structural glazing)
* Curtain Walling (Schüco, Kawneer, Technal, Reynaers, etc.)
* Architectural Glazing (frameless, bolted, structural)
* Rainscreen Cladding (metal, terracotta, stone, ACM)
* Building Envelopes (integrated façade and roofing systems)
* Cladding (metal, composite, stone, high-performance panels)
* Industrial Roofing (standing seam, metal roofing, single-ply, membrane systems)
* Flat Roofing (bitumen, felt, PVC, EPDM)
* Pitched Roofing
* Specialist Roofing (green roofs, solar-integrated systems)

If NO clear façade/cladding/roofing/glazing/building-envelope specialization is found:
* Classify as UNFIT 


ADDITIONAL SECTOR KEYWORDS (treat as strong evidence of sector involvement):
Cladding systems, SFS (Steel Framing System), light steel framing, brick slips, stone cladding, terracotta panels, composite panels, rainscreen cladding, cavity wall, GRC (glass reinforced concrete), ACM panels, HPL panels, external wall insulation (EWI), render systems, EIFS, curtain walling, unitised facade, stick facade, spandrel panels, soffit, brise soleil, louvres, balcony systems, building envelope, NBS specification, RIBA stages (facades context)

---

## STEP 3 — MUST-HAVE CRITERIA CHECK

The candidate MUST satisfy MOST of these requirements:
* Clear WHITE-COLLAR experience in façade, curtain walling, roofing, cladding, or building envelope sectors
* Worked for specialist façade/cladding/envelope contractors or subcontractors
* Involvement in project delivery, estimating, design, commercial management, contracts management, or pre-construction
* Self-employed can be considered depending on the profile's value

If the candidate fails most of these requirements:
* Classify as UNFIT

---

## STEP 4 — RED FLAGS CHECK

Immediately classify as UNFIT if any of these are strongly present:
* Mostly site-level or trade/install roles (EXCEPTION: Do NOT penalize candidates for having blue-collar trade backgrounds in their early career, e.g., Bricklayer or Installer, as long as their CURRENT/RECENT roles are recognized white-collar management positions)
* Purely residential/general construction background without façade/envelope specialization
* No roofing/cladding/façade/glazing exposure
* Mainly labour/install/fabrication/site execution experience
* The candidate is currently "Self Employed" or "Freelance" doing manual labor, trades, or generic/unrelated work. (EXCEPTION: If they are currently Self Employed/Freelance with an ACTIVE white-collar specialization in the facade/envelope sector, they can be FIT. HOWEVER, if their CURRENT freelance work does not explicitly involve facade/envelope specialization, OR their facade specialization is old/outdated (e.g. they left the facade industry years ago to do generic freelance work), they MUST be classified as UNFIT).
IMPORTANT - CAREER SPECIALIZATION REQUIRED:
Classify candidates as FIT if their CURRENT CAREER DIRECTION is clearly focused on:
* façade
* curtain walling
* cladding (including cladding remediation)
* glazing
* roofing
* building envelope systems

If the candidate's CURRENT ROLE heavily involves managing facade, cladding, or curtain walling projects (e.g., managing a major cladding remediation or curtain wall installation), they MUST be classified as FIT. 
Do NOT disqualify them just because their past career history (e.g., 5+ years ago) was in drylining, interiors, or general construction. Their CURRENT role is what matters most.

Candidates from general construction backgrounds must be classified as UNFIT ONLY IF their current role has absolutely no direct exposure to façade or cladding packages. Do NOT classify candidates as FIT if they only managed façade subcontractors occasionally within general construction roles, but if they directly manage cladding/facade installations or remediation, they are FIT.

IMPORTANT: ARCHITECTS & OIL/GAS ARE NOT SPECIALISTS
Candidates involved primarily in general:
* architectural design (Architect, Architectural Designer, Architectural Assistant)
* fire remediation
* refurbishment
* housing maintenance
* regeneration
* general construction operations
* oil & gas / industrial infrastructure
should be treated with HIGH SUSPICION and generally classified as UNFIT unless they have a proven, long-term career working directly for specialist commercial Façade / Cladding / Envelope contractors.

If a candidate's background is mostly general "Architectural Designer" and they only recently took a single role involving facades (especially for Oil & Gas), they are a generalist, NOT a specialist. Classify them as UNFIT.

A candidate whose ONLY exterior experience is a recent "fire remediation" or "remedial cladding" project for a general contractor is UNFIT.

However, if their CV shows a genuine history of managing dedicated Cladding / Re-Cladding / Curtain Walling packages (e.g., explicitly listing "Aluminum panels", "Cladding works", "Re-cladding" across multiple roles), they can be FIT. 

The rule of thumb:
* True cladding/facade specialists who happen to be working on remedial cladding projects = FIT.
* General contractors/refurbishment managers whose only exposure to facades is managing a fire remediation project = UNFIT.

The candidate must demonstrate a clear career background in:
* façade systems
* curtain walling
* architectural glazing
* cladding subcontracting (INCLUDING re-cladding & remedial cladding)
* roofing systems
* building envelope contracting

---

## STEP 5 — ADDITIONAL POSITIVE FACTORS

These factors strengthen the candidate profile:
* Large commercial or high-rise project experience
* AutoCAD experience
* Revit experience
* Specialist façade design software exposure
* Collaboration with architects
* Collaboration with Tier 1 contractors
* Experience across both technical/design and commercial/project functions

---

## FINAL CLASSIFICATION RULES

TIE-BREAK RULE: If the candidate is genuinely borderline — they have relevant background, some matching experience in their career history, and no strong red flags — classify as FIT. Missing a genuinely good candidate costs more than having one borderline CV reviewed by the recruiter.

Return ONLY:
FIT
OR
UNFIT

FIT RULES:
* Current/recent role matches approved white-collar roles
* Clear façade/cladding/roofing/building-envelope specialization
* Strong relevant contractor/subcontractor background
* Good alignment with must-have criteria
* No major red flags

UNFIT RULES (HARD STOPS - THESE OVERRIDE EVERYTHING ELSE):
* STRICT TITLE REJECTION: If the candidate's title is exactly "Facade Engineer" or "Façade Engineer", they MUST be classified as UNFIT. This is NOT a valid company role.
* Wrong current role (e.g. "Head of Quality" is NOT on the whitelist and must fail)
* Blue-collar/site/trade candidate
* General construction background only
* No façade/cladding/roofing/envelope specialization (Remember: Commercial Roofing alone is valid!)
* Major red flags present
* PRIMARY CAREER IS ARCHITECTURE: If the candidate's long-term career is 'Architectural Designer' or 'Architect', they are UNFIT even if their current role involves facades.
* OIL & GAS / INDUSTRIAL: If their facade/cladding experience is for the Oil & Gas industry (e.g. heat shields, industrial cladding), they are UNFIT.
* MAIN CONTRACTOR / TIER 1 DEVELOPER: If their recent career is with Main Contractors, Tier 1 Builders, or general Infrastructure firms (e.g., Bouygues, Carillion, Balfour Beatty, Mace, Skanska, Sir Robert McAlpine, Morgan Sindall, Kier, ISG, Julius Berger, CCC, Laing O'Rourke, Ardmore Group). These are NOT specialist facade subcontractors. If the candidate is a Project Manager managing a facade package from the Main Contractor side, they are a generalist. They MUST be classified as UNFIT.
* GENERALIST / MIXED DISCIPLINE CONSULTANT: If the candidate bounces across multiple completely different disciplines (e.g., Electrical, Plumbing, M&E, Fit-out, Data Centres, Flood Alleviation, General Commercial-to-Residential Conversions), they are a generalist. Even if they recently managed a facade or recladding contract as a QS or PM, their overall identity is a generalist, NOT a dedicated facade specialist. They MUST be classified as UNFIT.
* RECENTLY LEFT THE INDUSTRY / IRRELEVANT SECTOR: If their absolute most recent 1 or 2 jobs (in the last 1-2 years) are completely unrelated to specialist commercial facades (e.g., Aerospace, Rebar, General Steelwork, generic Engineering), they are UNFIT. Do not be tricked by older facade roles or a "Keywords" list at the bottom of the CV.

REASONING REQUIREMENT:
The AI must explain the decision by referencing the specific rule(s) that caused the classification.
IMPORTANT: Write the reasoning as a cohesive, natural-reading paragraph. DO NOT use numbered lists or bullet points.

For UNFIT candidates, the paragraph must seamlessly mention:
- The approved white-collar role status.
- Whether the sector relevance check passed or failed.
- Whether specialist façade/cladding/roofing/building-envelope experience was found.
- Whether the recent 5-year experience supports a specialist career identity.
- The PRIMARY rejection reason clearly identified.

For FIT candidates, the paragraph must seamlessly mention:
- Confirmation that their current white-collar role matches the whitelist.
- The specific façade/cladding/roofing systems or products they have experience with.
- Confirmation that their recent background is with specialist contractors (NOT Tier 1).

RULES:
* Keep reasoning recruiter-style, concise, and in paragraph format.
* IMPORTANT: False NEGATIVES (missing a good candidate) are more costly than false POSITIVES (a borderline candidate who needs human review). When a candidate is genuinely borderline, classify as FIT so the recruiter can make the final call.
* Do not assume experience that is not clearly shown in the CV.
* Evaluate the CURRENT role based on the actual job description and dates, NOT a generic 'Keywords' or 'Skills' section at the bottom of the CV.
* Do NOT reject candidates solely because of older trade roles if they have progressed into management positions.
* CRITICAL: "Site Manager", "Site Supervisor", "Project Manager" (and combinations like "Supervisor/Site Manager") ARE ON THE APPROVED WHITELIST. You MUST NOT claim their title does not match or that they are blue-collar based on this title. If they fail, it must be because of their sector experience (e.g., they work for a general contractor instead of a facade specialist), not their title.

Prioritize the candidate’s CURRENT and RECENT EXPERIENCE from the last 3–5 years.
Older experience should only be considered as supporting background and should NOT override irrelevant recent experience.
If the candidate’s recent 3–5 years experience is mainly outside façade, cladding, curtain walling, roofing, glazing, or building envelope sectors, classify as UNFIT even if older experience was relevant.


## FINAL DECISION FORMAT
You must respond with ONLY a valid JSON object matching the following structure:
{{
  "candidate_name": "Full name of the candidate (if available, else Unknown)",
  "current_company": "The candidate's current or most recent company/employer name (if available, else null)",
  "current_position": "The candidate's current or most recent job title",
  "location": "The candidate's location/city (if available, else Unknown)",
  "classification": "FIT" or "UNFIT",
  "reasoning": "A highly concise 1-2 sentence summary explaining exactly why the candidate was classified as FIT or UNFIT.",
  "t1_tenure": "The tenure/duration of the candidate's current or most recent job/role in elapsed months (exclusive of the starting month, e.g. Aug 2025 to May 2026 is 9 months). If the role ends in 'Current' or 'Present', calculate elapsed months relative to the current date ({{current_date_str}}). Calculated from the dates on the CV. Use null if not available.",
  "t2_tenure": "The tenure/duration of the candidate's second most recent job/role (previous job) in elapsed months (exclusive of the starting month, e.g. Oct 2024 to Jun 2025 is 8 months). If the role is ongoing or ends in 'Current'/'Present', calculate relative to {{current_date_str}}. Calculated from the dates on the CV. Use null if not available.",
  "business_specialization": "string matching the sector or specialty, e.g. Estimating",
  "linkedin_url": "string link or null",
  "salary_range": "The candidate's salary range, formatted cleanly as '£X - £Y' (e.g. £50,000 - £54,999). Do NOT include 'per annum', 'per year', or the word 'to' (use a hyphen instead). Use null if not available.",
  "email": "string email or null",
  "phone_number": "string phone number or null"
}}
DO NOT include any markdown formatting (like ```json), DO NOT include any introductory or concluding text. JUST output the raw JSON object.
"""

        user_prompt = f"""
CANDIDATE CV TEXT:
{cv_text}


"""
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={ "type": "json_object" },
                    temperature=0.1, extra_body={"thinking": {"type": os.getenv("AI_THINKING", "disabled")}} # Keep it deterministic
                )
                
                ai_data = json.loads(response.choices[0].message.content)
                
                # Extract and log token usage
                if hasattr(response, 'usage') and response.usage:
                    input_tokens = response.usage.prompt_tokens
                    output_tokens = response.usage.completion_tokens
                    total_tokens = response.usage.total_tokens
                    logger.info(f"Token Usage for {expected_name} -> Input: {input_tokens} | Output: {output_tokens} | Total: {total_tokens}")
                
                # Log the Recruiter's Decision
                classification = ai_data.get('classification', 'UNFIT')
                
                logger.info(f"[DECISION] {expected_name}: {classification}")
                logger.info(f"Reasoning: {ai_data.get('reasoning')}")
                
                return ai_data
                
            except Exception as e:
                logger.warning(f"AI Classification Error on attempt {attempt + 1}/{max_retries} for {expected_name}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt) # Exponential backoff: 1s, 2s
                else:
                    logger.error(f"AI Classification completely failed for {expected_name} after {max_retries} attempts.")
                    return {
                        "classification": "ERROR",
                        "current_position": "Error",
                        "reasoning": f"AI Logic Failure after {max_retries} retries: {str(e)}"
                    }

    def pre_classify_candidate(self, preview_text, expected_name="Unknown"):
        logger.info(f"Starting Pre-Screening LLM evaluation for: {expected_name}...")
        
        system_prompt = """
You are a specialist recruitment pre-screening AI for the façade, curtain walling, cladding, roofing, glazing, and building envelope industry.
Your job is to analyze the candidate's visible card preview snippet (metadata, recent experience summary, desired role, and current status) from a recruiter portal and decide if the candidate is a potential FIT or UNFIT.
Since we pay money to unlock their full CV, we want to reject any candidate who is clearly UNFIT at this stage to save costs.

STRICT CLASSIFICATION CRITERIA:
1. ONLY pre-classify as FIT if the candidate shows clear potential of being a white-collar specialist (Design, Commercial, Estimating, Bid, Planning, Buying, Project Delivery, or Site Management) within the facade, curtain walling, cladding, roofing, glazing, or building envelope sectors.
2. IMMEDIATELY pre-classify as UNFIT if:
   - The candidate is a blue-collar worker / trade installer / manual labourer (e.g. Cladder, Installer, Roofer, Fabricator, Glazier, Welder, Fixer, Operative).
   - The candidate's primary experience is in an unrelated sector (e.g. IT, Admin, general sales, logistics, finance, retail).
   - The candidate is a general architect / general construction worker without clear facade/envelope subcontracting specialization.
   - The candidate works primarily for Tier 1 Main Contractors or Developers as a generalist (with no dedicated specialist subcontracting background).
   - Their job title is exactly "Facade Engineer" or "Façade Engineer".

If you are unsure but they have a strong facade/roofing/cladding background with a white-collar title, classify as FIT so we can inspect the full CV.

Return output ONLY in valid JSON format:
{
  "classification": "FIT or UNFIT",
  "reasoning": "A concise paragraph explaining your pre-screening decision based on the visible experience."
}
"""

        user_prompt = f"""
CANDIDATE: {expected_name}
CARD PREVIEW TEXT:
{preview_text}

Return JSON output.
"""
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={ "type": "json_object" },
                    temperature=0.1, extra_body={"thinking": {"type": os.getenv("AI_THINKING", "disabled")}}
                )
                
                ai_data = json.loads(response.choices[0].message.content)
                classification = ai_data.get('classification', 'UNFIT')
                
                logger.info(f"[PRE-DECISION] {expected_name}: {classification}")
                logger.info(f"Pre-Screening Reasoning: {ai_data.get('reasoning')}")
                
                return ai_data
                
            except Exception as e:
                logger.warning(f"AI Pre-Screening Error on attempt {attempt + 1}/{max_retries} for {expected_name}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"AI Pre-Screening completely failed for {expected_name} after {max_retries} attempts.")
                    return {
                        "classification": "UNFIT",
                        "reasoning": f"AI Pre-Screening Logic Failure: {str(e)}"
                    }



    def fast_title_prescreen(self, job_title, desired_role):
        import time
        import json
        logger.info(f"Starting CV-Library Fast Title Pre-Screening: Title='{job_title}', Desired='{desired_role}'")
        
        # We reuse the main system prompt to dynamically grab the custom white-collar/blue-collar title lists
        # But we append a strict override to ignore the deep filtering rules.
        override_instructions = """
---------------------------------------------------------------------
CRITICAL PRE-SCREENING OVERRIDE INSTRUCTIONS:
You are currently performing an ULTRA-FAST PRE-SCREEN on a candidate preview card. You do NOT have their full CV.
IGNORE all strict filtering rules, tenure requirements, background checks, and red flags mentioned in the prompt above.
Your ONLY JOB is to look at the Target Job Titles listed in Step 1 and Step 2 above.

Evaluate if the candidate's provided Job Title or Desired Role is a loose/fuzzy match to any of those target titles (prefixes, suffixes, and slight variations are fully allowed).
Do not apply any other rules. Output FIT if it's a loose match, or UNFIT if it is completely unrelated to the target titles.

Return output ONLY in valid JSON format:
{
  "classification": "FIT or UNFIT",
  "reasoning": "A concise 5-word explanation."
}
"""
        
        # We inject the override directly after the main system_prompt
        # To do this cleanly, we can just use the exact same system_prompt defined in classify_candidate, 
        # but since system_prompt is a local variable in classify_candidate, we will recreate it here by parsing the file, OR we can just hardcode the override.
        # Wait, the easiest way to get the system_prompt dynamically is to just read the file, or we can just ask the AI to act based on the class's inherent knowledge, but OpenAI doesn't know the file.
        # Actually, let's just extract the system prompt from the file dynamically!
        import inspect
        source = inspect.getsource(self.classify_candidate)
        # Extract everything between system_prompt = f""" and """
        import re
        match = re.search(r'system_prompt\s*=\s*f?"""(.*?)"""', source, re.DOTALL)
        if match:
            base_prompt = match.group(1)
        else:
            base_prompt = "You are a specialist recruitment AI."

        full_system_prompt = base_prompt + override_instructions

        user_prompt = f"""
CANDIDATE JOB TITLE: {job_title}
CANDIDATE DESIRED ROLE: {desired_role}
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": full_system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1, extra_body={"thinking": {"type": os.getenv("AI_THINKING", "disabled")}},
                response_format={"type": "json_object"}
            )
            raw_response = response.choices[0].message.content.strip()
            if raw_response.startswith("```json"):
                raw_response = raw_response.replace("```json", "", 1)
            if raw_response.endswith("```"):
                raw_response = raw_response[:-3]
            result = json.loads(raw_response.strip())
            return result
        except Exception as e:
            logger.error(f"Fast Pre-Screening API Error: {str(e)}")
            return {"classification": "FIT", "reasoning": f"Error fallback: {str(e)}"} # Fallback to FIT so we don't miss candidates on error

