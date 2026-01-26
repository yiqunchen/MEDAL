import fitz  # PyMuPDF
import re
import pandas as pd


def extract_strict_recommendation_blocks(pdf_path):
    doc = fitz.open(pdf_path)
    tables = []

    for page_num, page in enumerate(doc):
        text = page.get_text()
        if "COR" not in text or "LOE" not in text:
            continue

        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        i = 0

        while i < len(lines) - 2:
            cor_line = lines[i].strip().lower()

            if cor_line.startswith("3: no") and i + 1 < len(lines):
                next_line = lines[i + 1].strip().lower()
                if "benefit" in next_line:
                    cor_line = "3: no benefit"
                    i += 1

            cor_m = re.match(r"^(1|2a|2b|3(?::\s*(no benefit|harm))?)\b", cor_line)
            loe_line = lines[i + 1].strip()
            loe_m = re.match(r"^[A-C](?:-[A-Z]{1,2})?$", loe_line)
            reco_m = re.match(r"^\d+\.\s+", lines[i + 2]) if i + 2 < len(lines) else None

            if cor_m and loe_m and reco_m:
                cor = cor_m.group(0).strip().title()
                loe = loe_line.strip()
                reco = lines[i + 2]
                j = i + 3

                while j < len(lines):
                    line = lines[j].strip()
                    line_lower = line.lower()

                    if re.match(r"^\d+\.\s+", line) or re.match(r"^(1|2a|2b|3(?::.*)?)\b", line_lower):
                        break
                    if line == "":
                        break
                    if "synopsis" in line_lower:
                        break
                    if re.match(r"^[A-Z][^a-z]*[a-z]+", line) and line.endswith("."):
                        break

                    reco += " " + line
                    j += 1

                tables.append({
                    "Page": page_num + 1,
                    "COR": cor,
                    "LOE": loe,
                    "Recommendation": reco.strip()
                })
                i = j
            else:
                i += 1

    return pd.DataFrame(tables)


# if __name__ == "__main__":
#     pdf_path = "rao-et-al-2025-acc-aha-acep-naemsp-scai-guideline-for-the-management-of-patients-with-acute-coronary-syndromes-a-report.pdf"
#     df = extract_strict_recommendation_blocks(pdf_path)
#     df.to_csv("aha_guideline_evidence_table.csv", index=False)
#     print(f"Extracted {len(df)} recommendations -> aha_guideline_evidence_table.csv")
