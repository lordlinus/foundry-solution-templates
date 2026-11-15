"""Generate the synthetic sample medical records (PDF) used to try the template.

Every name, clinic, date, and value here is fictional. Run: pip install -r requirements.txt; python generate.py
"""

from datetime import UTC, datetime
from pathlib import Path

from fpdf import FPDF

HERE = Path(__file__).resolve().parent

RECORDS = {
    "sample-01-hypertension.pdf": [
        (
            "Attending Physician Statement",
            [
                "Record ID: SYN-0001    Synthetic sample record - fictional data",
                "Applicant: Sample Applicant One    Sex: M    Date of birth: 14 Mar 1979",
                "Clinic: Northfield Family Practice (fictional)",
                "Diagnoses on file: Essential hypertension (I10); Hypercholesterolaemia (E78.0)",
                "Current medication: amlodipine 5 mg once daily; atorvastatin 20 mg once daily",
            ],
        ),
        (
            "Visit notes",
            [
                "02 Feb 2025  Clinic review. BP 152/96 mmHg. Started amlodipine 5 mg.",
                "11 May 2025  Clinic review. BP 138/86 mmHg. Tolerating treatment.",
                "20 Aug 2025  Clinic review. BP 134/84 mmHg. Continue current treatment.",
                "20 Aug 2025  Laboratory: total cholesterol 5.9 mmol/L; LDL 3.8 mmol/L; creatinine 82 umol/L (normal).",
                "Smoking status: never smoked.",
            ],
        ),
    ],
    "sample-02-diabetes.pdf": [
        (
            "Attending Physician Statement",
            [
                "Record ID: SYN-0002    Synthetic sample record - fictional data",
                "Applicant: Sample Applicant Two    Sex: F    Date of birth: 02 Sep 1971",
                "Clinic: Riverside Medical Centre (fictional)",
                "Diagnoses on file: Type 2 diabetes mellitus (E11.9); Hypertension (I10)",
                "Current medication: metformin 1000 mg twice daily; lisinopril 10 mg once daily",
            ],
        ),
        (
            "Visit notes",
            [
                "15 Jan 2025  Diabetes review. HbA1c 7.9%. BP 146/92 mmHg. Dietary advice given.",
                "09 Jul 2025  Diabetes review. HbA1c 7.6%. BP 144/90 mmHg. Foot check normal.",
                "09 Jul 2025  Urine albumin/creatinine ratio requested - result awaited.",
                "No retinal screening report on file.",
            ],
        ),
        (
            "Laboratory summary",
            [
                "15 Jan 2025  HbA1c 7.9 %   Fasting glucose 8.4 mmol/L",
                "09 Jul 2025  HbA1c 7.6 %   eGFR 78 mL/min/1.73m2",
                "09 Jul 2025  Urine albumin/creatinine ratio: sent, pending",
            ],
        ),
    ],
    "sample-03-thyroid.pdf": [
        (
            "Attending Physician Statement",
            [
                "Record ID: SYN-0003    Synthetic sample record - fictional data",
                "Applicant: Sample Applicant Three    Sex: F    Date of birth: 27 Nov 1988",
                "Clinic: Lakeview Endocrine Clinic (fictional)",
                "Diagnoses on file: Thyroid nodule (E04.1)",
            ],
        ),
        (
            "Visit notes",
            [
                "04 Mar 2025  Referred for neck swelling. TSH 1.9 mIU/L (normal).",
                "18 Mar 2025  Ultrasound: single 14 mm nodule, right lobe. Fine-needle biopsy recommended.",
                "02 Apr 2025  Fine-needle aspiration performed. Cytology sent - result pending.",
            ],
        ),
    ],
}


def render(pages: list[tuple[str, list[str]]], target: Path) -> None:
    pdf = FPDF(format="A4")
    pdf.set_creation_date(datetime(2026, 1, 1, tzinfo=UTC))  # Fixed date: deterministic output.
    for title, lines in pages:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 15)
        pdf.cell(0, 12, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=11)
        for line in lines:
            pdf.multi_cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(target))


if __name__ == "__main__":
    for name, pages in RECORDS.items():
        render(pages, HERE / name)
        print("wrote", name)
