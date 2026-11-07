"""Single source of truth for the ClearPath demo ADU submittal packet.

Every document, section and field lives here. build_packet.py renders this
into a fillable PDF and a JSON schema, so the PDF and the app's checklist
logic can never drift apart.

Field tuple shapes used in rows:
  ("text",     name, label, width_frac[, required])
  ("area",     name, label, width_frac[, required])      multi-line text
  ("choice",   name, label, [options], width_frac[, required])   pick one
  ("multi",    name, label, [options], width_frac[, required])   pick any
  ("yesno",    name, label, width_frac[, required])
  ("sign",     name, label, width_frac[, required])      signature line
"""

PACKET = {
    "packet_id": "clearpath-irvine-adu-abbrev",
    "version": "0.1.0",
    "title": "Abbreviated ADU Submittal Packet",
    "jurisdiction": "City of Irvine, CA (demo basis)",
    "project_type": "Accessory Dwelling Unit (ADU / JADU)",
    "disclaimer": (
        "ClearPath hackathon sample. Not an official City of Irvine document and "
        "not for submittal. Abbreviated from public City of Irvine and OCFA forms "
        "for software testing; field sets are condensed and staff-only content is "
        "simplified."
    ),
    "source_page": "https://cityofirvine.gov/building-permits-and-inspections/project-constructing-accessory-dwelling-unit-adu",
}

# Documents that are part of a real submittal but deliberately NOT reproduced
# as forms here. The app should still expect (or flag) them.
EXTERNAL_DOCUMENTS = [
    {"id": "PLAN-01", "title": "Architectural / structural plan set with City Standard Title Sheet as first page",
     "required": True, "completed_by": "Designer or pre-approved plan provider",
     "note": "Use a downloadable pre-approved plan set (e.g., Santa Ana or Laguna Hills) for demo uploads."},
    {"id": "PLAN-02", "title": "Site plan (property lines, setbacks, easements, parking, utilities)",
     "required": True, "completed_by": "Designer",
     "note": "Values must match DOC-02."},
    {"id": "EXT-01", "title": "Title 24 energy calculations", "required": True,
     "completed_by": "Energy consultant", "note": "Site-specific even for pre-approved plans."},
    {"id": "EXT-02", "title": "ADU covenant (notarized; recorded later with County Recorder)", "required": True,
     "completed_by": "Owner + notary", "note": "Obtained from Planning; recorded when the case planner says so."},
    {"id": "EXT-03", "title": "Developer Deposit Case Set-Up form", "required": True,
     "completed_by": "Owner / applicant", "note": "Online form in the real process; omitted here."},
    {"id": "EXT-04", "title": "Residential Take-Off Sheet (fixture counts)", "required": True,
     "completed_by": "Applicant", "note": "Omitted from the abbreviated packet."},
    {"id": "EXT-05", "title": "HOA / ARC approval letter", "required": False,
     "completed_by": "HOA", "note": "Conditional: only where an HOA or community association applies."},
]

DOCUMENTS = [
    # ------------------------------------------------------------------ DOC-01
    {
        "id": "DOC-01",
        "title": "Building Permit Application (ADU)",
        "based_on": "City of Irvine Form 65-59 Building Permit Application; Form 41-60 Address Application",
        "completed_by": "Applicant",
        "required": True,
        "condition": "All ADU and JADU projects",
        "sections": [
            {"title": "For office use only", "staff": True, "rows": [
                [("text", "staff_plan_check_no", "Plan check no.", 0.34),
                 ("text", "staff_submittal_date", "Submittal date", 0.33),
                 ("text", "staff_target_date", "Target date", 0.33)],
            ]},
            {"title": "Project location", "rows": [
                [("text", "project_address", "Project address", 0.55, True),
                 ("text", "unit", "Unit / suite", 0.15),
                 ("text", "city", "City", 0.15, True),
                 ("text", "zip", "ZIP", 0.15, True)],
                [("text", "apn", "Assessor parcel number (APN)", 0.34, True),
                 ("text", "tract", "Tract", 0.22),
                 ("text", "lot", "Lot", 0.14),
                 ("text", "planning_area", "Planning area no. / name", 0.30)],
            ]},
            {"title": "Applicant", "rows": [
                [("text", "applicant_name", "Applicant / company name", 0.5, True),
                 ("text", "applicant_phone", "Phone", 0.2, True),
                 ("text", "applicant_email", "Email", 0.3, True)],
                [("text", "applicant_address", "Mailing address", 0.55),
                 ("text", "applicant_city", "City", 0.25),
                 ("text", "applicant_zip", "ZIP", 0.2)],
            ]},
            {"title": "Property owner", "rows": [
                [("text", "owner_name", "Owner name", 0.5, True),
                 ("text", "owner_phone", "Phone", 0.2, True),
                 ("text", "owner_email", "Email", 0.3, True)],
                [("text", "owner_address", "Mailing address", 0.55),
                 ("text", "owner_city", "City", 0.25),
                 ("text", "owner_zip", "ZIP", 0.2)],
            ]},
            {"title": "Project information", "rows": [
                [("choice", "adu_type", "ADU type",
                  ["Detached ADU", "Attached ADU", "Garage conversion", "JADU"], 1.0, True)],
                [("yesno", "uses_preapproved_plan", "Using a pre-approved ADU plan?", 0.4, True),
                 ("text", "preapproved_plan_id", "Pre-approved plan name / ID", 0.6)],
                [("multi", "permit_types", "Permit types applied for",
                  ["Building", "Plumbing", "Electrical", "Mechanical"], 1.0, True)],
                [("text", "adu_sqft", "ADU floor area (sq ft)", 0.25, True),
                 ("text", "bedrooms", "Bedrooms", 0.15, True),
                 ("text", "bathrooms", "Bathrooms", 0.15, True),
                 ("text", "stories", "Stories", 0.15, True),
                 ("text", "valuation", "Valuation ($)", 0.30, True)],
                [("yesno", "fire_sprinklers", "Fire sprinklers?", 0.33, True),
                 ("yesno", "solar_pv", "Solar PV included?", 0.33, True),
                 ("yesno", "new_address_needed", "New address needed?", 0.34, True)],
                [("area", "description_of_work", "Description of work", 1.0, True)],
            ]},
            {"title": "Certification", "rows": [
                [("sign", "applicant_signature", "Applicant signature", 0.45, True),
                 ("text", "applicant_print_name", "Print name", 0.35, True),
                 ("text", "applicant_sign_date", "Date", 0.20, True)],
            ]},
        ],
    },
    # ------------------------------------------------------------------ DOC-02
    {
        "id": "DOC-02",
        "title": "ADU Development Standards Checklist (Site Plan)",
        "based_on": "City of Irvine Form 67-01 Pre-Approved ADU Development Standards Checklist",
        "completed_by": "Applicant / designer",
        "required": True,
        "condition": "All ADU and JADU projects",
        "table": {
            "columns": ["Standard", "Requirement (summary)", "Proposed / shown", "Plan sheet"],
            "rows": [
                ("property_type", "Property type", "Single-family or multi-family, per ADU Verification Form (DOC-03)"),
                ("adu_type", "ADU type", "JADU (one per SFR; not for multi-family), attached, or detached"),
                ("units", "Units existing / proposed", "Confirm total units allowed with Planning"),
                ("property_lines", "Property lines", "Located, labeled and shown on site plan"),
                ("easements", "Easements", "Label and dimension width, or sign owner statement below"),
                ("side_setback_ft", "Side setback (ft)", "Minimum 4 ft from side property line"),
                ("rear_setback_ft", "Rear setback (ft)", "Minimum 4 ft from rear property line"),
                ("building_separation_ft", "Building separation (ft)", "Minimum 6 ft building to building"),
                ("primary_footprint_sqft", "Primary residence footprint (sq ft)", "Include existing accessory structures"),
                ("adu_size_sqft", "Proposed ADU size (sq ft)", "Detached up to 1,200; attached up to 1,200 or 50% of primary, whichever is less; JADU up to 500 (+150 for entry)"),
                ("garage_sqft", "Garage (sq ft)", "Depict and label garage"),
                ("lot_size_sqft", "Lot size (sq ft)", ""),
                ("lot_coverage_sqft", "Lot coverage (sq ft)", "May be exceeded to allow an 800 sq ft unit"),
                ("height_ft", "Building height (ft)", ""),
                ("adu_parking", "ADU parking", "1 space if 1+ bedrooms, unless a state exemption applies"),
                ("walls_fences", "Walls and fences", "Show existing / proposed; 2 ft from property line"),
                ("mechanical_equipment", "Mechanical equipment", "Show location; screen from off-site views"),
                ("waste_bins", "Solid waste bins", "Show collection bin location"),
            ],
        },
        "sections": [
            {"title": "Easement statement (complete only if no easements exist)", "rows": [
                [("text", "no_easement_owner_name", "Owner (or authorized agent) name", 0.45),
                 ("sign", "no_easement_signature", "Signature confirming no restricting easements", 0.55)],
            ]},
            {"title": "Prepared by", "rows": [
                [("text", "preparer_name", "Name", 0.4, True),
                 ("text", "preparer_firm", "Firm", 0.4),
                 ("text", "preparer_date", "Date", 0.2, True)],
            ]},
        ],
    },
    # ------------------------------------------------------------------ DOC-03
    {
        "id": "DOC-03",
        "title": "ADU Verification Form",
        "based_on": "City of Irvine ADU Verification Form (issued by Planning on request)",
        "completed_by": "Applicant (Part A) + City Planning staff (Part B)",
        "required": True,
        "condition": "All ADU and JADU projects; must be signed by Planning staff before submittal",
        "sections": [
            {"title": "Part A - Request (applicant)", "rows": [
                [("text", "property_address", "Property address", 0.6, True),
                 ("text", "apn", "APN", 0.4, True)],
                [("text", "owner_name", "Owner name", 0.5, True),
                 ("text", "contact_email", "Contact email", 0.5, True)],
                [("choice", "proposed_type", "Proposed unit type",
                  ["Detached ADU", "Attached ADU", "Garage conversion", "JADU"], 1.0, True)],
            ]},
            {"title": "Part B - Planning determination (City staff only)", "staff": True, "rows": [
                [("choice", "property_type", "Property type", ["Single-family", "Multi-family"], 0.5, True),
                 ("text", "zoning_district", "Zoning / planning area", 0.5, True)],
                [("yesno", "adu_eligible", "Eligible for ADU?", 0.33, True),
                 ("yesno", "jadu_eligible", "Eligible for JADU?", 0.33, True),
                 ("text", "max_units", "Max. ADU/JADU units", 0.34, True)],
                [("area", "planning_notes", "Notes / conditions", 1.0)],
                [("text", "planner_name", "Planner name", 0.35, True),
                 ("sign", "planner_signature", "Planner signature", 0.45, True),
                 ("text", "planner_date", "Date", 0.20, True)],
            ]},
        ],
    },
    # ------------------------------------------------------------------ DOC-04
    {
        "id": "DOC-04",
        "title": "Fire Authority Plan Submittal Criteria (Residential)",
        "based_on": "Orange County Fire Authority (OCFA) Plan Submittal Criteria Form, single-family / duplex",
        "completed_by": "Applicant",
        "required": True,
        "condition": "All ADU projects; any YES answer may trigger an OCFA plan review",
        "sections": [
            {"title": "Project information", "rows": [
                [("text", "address", "Address", 0.6, True),
                 ("text", "zip", "ZIP", 0.15, True),
                 ("text", "stories", "Stories", 0.25, True)],
                [("text", "existing_area_sqft", "Existing area (sq ft)", 0.34, True),
                 ("text", "added_area_sqft", "Area to be added (sq ft)", 0.33, True),
                 ("text", "total_area_sqft", "Total resulting area (sq ft)", 0.33, True)],
            ]},
            {"title": "Questionnaire (answer every item)", "rows": [
                [("yesno", "q_adu_sprinklered_house", "1. New ADU on a lot whose house has, or will get, fire sprinklers?", 1.0, True)],
                [("yesno", "q_distance_over_140ft", "2. Any part of the ADU more than 140 ft from the fire access roadway?", 1.0, True)],
                [("yesno", "q_total_area_threshold", "3. Total area over 3,600 sq ft (unsprinklered) or 6,200 sq ft (sprinklered)?", 1.0, True)],
                [("yesno", "q_gate", "4. Gate across a fire access driveway or road?", 1.0, True)],
                [("yesno", "q_methane", "5. Within 100 ft of an oil/gas field or well, 300 ft of a seep, or 1,000 ft of a landfill?", 1.0, True)],
                [("yesno", "q_vegetation", "6. Adjacent to wildland or open space, or in a Fire Hazard Severity Zone?", 1.0, True)],
            ]},
            {"title": "Applicant certification", "rows": [
                [("text", "cert_name", "Print name", 0.35, True),
                 ("sign", "cert_signature", "Signature", 0.45, True),
                 ("text", "cert_date", "Date", 0.20, True)],
                [("text", "cert_phone", "Phone", 0.4, True),
                 ("text", "cert_email", "Email", 0.6, True)],
            ]},
        ],
    },
    # ------------------------------------------------------------------ DOC-05
    {
        "id": "DOC-05",
        "title": "Fee Determinations: School Facilities and Transportation Corridor",
        "based_on": "City of Irvine Form 42-97 School Facilities Fee Determination; Form 66-92 TCA Residential Fee Determination",
        "completed_by": "Applicant (project info) + City staff (determination)",
        "required": True,
        "condition": "All ADU projects",
        "sections": [
            {"title": "A. School facilities fee - project information", "rows": [
                [("text", "sf_owner_name", "Property owner", 0.5, True),
                 ("text", "sf_owner_phone", "Phone", 0.5)],
                [("text", "sf_property_address", "Property address", 0.6, True),
                 ("text", "sf_adu_sqft", "ADU gross floor area (sq ft)", 0.4, True)],
                [("choice", "sf_school_district", "School district",
                  ["IUSD", "IUSD (CFD)", "Santa Ana USD", "Tustin USD", "Saddleback Valley USD"], 1.0, True)],
            ]},
            {"title": "A. School facilities fee - determination (City staff only)", "staff": True, "rows": [
                [("choice", "sf_determination", "Determination",
                  ["Fee required", "Exempt: ADU 749 sq ft or less", "Exempt: within CFD", "Exempt: other"], 1.0)],
                [("text", "sf_fee_amount", "Fee ($)", 0.3),
                 ("text", "sf_prepared_by", "Prepared by", 0.45),
                 ("text", "sf_date", "Date", 0.25)],
            ]},
            {"title": "B. Transportation corridor fee - unit information", "rows": [
                [("text", "tca_lot", "Lot", 0.15, True),
                 ("text", "tca_address", "Unit address", 0.55, True),
                 ("text", "tca_unit_sqft", "Unit sq ft (no garage)", 0.30, True)],
                [("yesno", "tca_detached", "Detached?", 0.33, True),
                 ("yesno", "tca_separate_lot", "On a separate lot?", 0.33, True),
                 ("yesno", "tca_over_1500", "1,500 sq ft or larger?", 0.34, True)],
            ]},
            {"title": "B. Transportation corridor fee - determination (City staff only)", "staff": True, "rows": [
                [("choice", "tca_class", "Unit classification", ["Single-family", "Multi-family"], 0.5),
                 ("choice", "tca_zone", "Corridor zone", ["Zone A", "Zone B"], 0.5)],
                [("text", "tca_fee_amount", "Fee ($)", 0.3),
                 ("text", "tca_prepared_by", "Prepared by", 0.45),
                 ("text", "tca_date", "Date", 0.25)],
            ]},
        ],
    },
    # ------------------------------------------------------------------ DOC-06
    {
        "id": "DOC-06",
        "title": "Owner Acknowledgments",
        "based_on": "City of Irvine Form 66-122A C&D Waste Assessment; Form 67-02 Hold Harmless Affidavit; Electronic/Digital Signature Disclosure",
        "completed_by": "Owner / applicant",
        "required": True,
        "condition": "Part B only when a pre-approved ADU plan is used (notarized in the real process)",
        "sections": [
            {"title": "A. Construction and demolition waste assessment", "rows": [
                [("yesno", "cd_new_residential", "New residential main or accessory building?", 1.0, True)],
                [("yesno", "cd_remodel_adds_area", "Remodel that adds conditioned area or volume?", 1.0, True)],
                [("text", "cd_name", "Name of person completing", 0.4, True),
                 ("text", "cd_company", "Company", 0.3),
                 ("text", "cd_date", "Date", 0.3, True)],
                [("sign", "cd_signature", "Signature", 1.0, True)],
            ]},
            {"title": "B. Pre-approved plan release (summary of hold-harmless terms)", "rows": [
                [("text", "hh_owner_name", "Owner name", 0.5),
                 ("text", "hh_apn", "APN", 0.5)],
                [("text", "hh_property_address", "Property address", 0.6),
                 ("text", "hh_owner_phone", "Phone", 0.4)],
                [("sign", "hh_owner_signature", "Owner signature", 0.6),
                 ("text", "hh_date", "Date", 0.4)],
                [("yesno", "hh_notarized", "Notary acknowledgment attached?", 1.0)],
            ]},
            {"title": "C. Electronic signature consent", "rows": [
                [("sign", "esig_signature", "Signature", 0.7, True),
                 ("text", "esig_date", "Date", 0.3, True)],
            ]},
        ],
        "notes": {
            "B. Pre-approved plan release (summary of hold-harmless terms)":
                "In plain terms: the owner accepts that using a pre-approved plan is at their own risk, "
                "uses it only for this property, and releases the City and the plan's designers from claims.",
            "C. Electronic signature consent":
                "In plain terms: an electronic signature on any submitted document binds the signer the same "
                "way a handwritten one does, and the City's stored copy is the official record.",
            "A. Construction and demolition waste assessment":
                "A YES to either question means a waste management plan and bond are required before permit issuance.",
        },
    },
]
