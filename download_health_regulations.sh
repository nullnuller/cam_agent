#!/bin/bash
# This script creates a directory and downloads Australian health/medical regulations, ethical guidelines and codes of conduct.
# Run: bash download_health_regulations.sh

mkdir -p health_docs
cd health_docs

# Helper to download a PDF with optional fallback URLs.
download_pdf() {
  local output="$1"
  shift
  local urls=("$@")

  if [ "${#urls[@]}" -eq 0 ]; then
    echo "[download] ERROR: No URLs provided for $output" >&2
    FAILURES+=("$output (no URLs)")
    return
  fi

  for url in "${urls[@]}"; do
    echo "[download] Fetching $url -> $output"
    if wget -q -O "${output}.tmp" "$url"; then
      if [ -s "${output}.tmp" ] && head -c 4 "${output}.tmp" | grep -q "%PDF"; then
        mv "${output}.tmp" "$output"
        return
      else
        echo "[download] Warning: non-PDF or empty response for $output from $url" >&2
        rm -f "${output}.tmp"
      fi
    fi
    echo "[download] Warning: download from $url failed for $output" >&2
  done

  echo "[download] ERROR: Unable to download $output from provided URLs." >&2
  FAILURES+=("$output")
  rm -f "$output"
}

FAILURES=()

# 1. Health Practitioner Regulation National Law Act 2009 (current as at 1 July 2024) - Queensland version.
download_pdf "health_practitioner_regulation_national_law_act_2009.pdf" \
  "https://www.legislation.qld.gov.au/view/pdf/inforce/current/act-2009-045"

# 2. National Code of Conduct for Health Care Workers (Queensland)
download_pdf "national_code_health_workers_queensland.pdf" \
  "https://www.careers.health.qld.gov.au/__data/assets/pdf_file/0027/188442/national-code-conduct-health-workers.pdf"

# 3. AHPRA Regulatory Guide (Apr 2021) – full guide (hosted by AMA). The July 2024 version is not publicly accessible.
download_pdf "ahpra_regulatory_guide_full_2021.pdf" \
  "https://www.ama.com.au/sites/default/files/2022-03/Ahpra---Regulatory-guide---a-full-guide.PDF"

# 4. Good Medical Practice: A code of conduct for doctors in Australia (2009 version)
download_pdf "good_medical_practice_code_2009.pdf" \
  "https://www.ahpra.gov.au/documents/default.aspx?record=WD10/12752&dbid=AP&chksum=ZsYTGuMVhEvIfkB1SQWfmg%3D%3D"
# Note: The official code is often blocked behind dynamic pages; if this download fails,
# a commentary on the 2020 updates is available:
download_pdf "medical_board_code_of_conduct_2020_commentary.pdf" \
  "https://www.ama.com.au/sites/default/files/2022-03/MBA_Code_of_Conduct.pdf"

# 5. Australian Charter of Healthcare Rights (2019)
download_pdf "australian_charter_of_healthcare_rights.pdf" \
  "https://www.safetyandquality.gov.au/sites/default/files/2021-04/australian_charter_of_healthcare_rights_2020.pdf"

# 6. National Statement on Ethical Conduct in Human Research (2023)
download_pdf "national_statement_ethics_human_research_2023.pdf" \
  "https://www.nhmrc.gov.au/sites/default/files/documents/attachments/publications/National-Statement-Ethical-Conduct-Human-Research-2023.pdf"

# 7. National Safety and Quality Health Service (NSQHS) Standards (Second edition, 2021)
download_pdf "nsqhs_standards_second_edition_2021.pdf" \
  "https://www.safetyandquality.gov.au/sites/default/files/2021-05/national_safety_and_quality_health_service_nsqhs_standards_second_edition_-_updated_may_2021.pdf"

# 7b. AI clinical guidance (new documents)
download_pdf "ai_clinical_use_guide.pdf" \
  "https://www.safetyandquality.gov.au/sites/default/files/2025-08/ai-clinical-use-guide.pdf"
download_pdf "ai_safety_scenario_ambient_scribe.pdf" \
  "https://www.safetyandquality.gov.au/sites/default/files/2025-09/ai-safety-scenario-ambient-scribe.pdf"
download_pdf "ai_safety_scenario_medical_images.pdf" \
  "https://www.safetyandquality.gov.au/sites/default/files/2025-09/ai-safety-scenario-interpretation-of-medical-images.pdf"

# 8. International Council of Nurses (ICN) Code of Ethics for Nurses (2021 revision)
download_pdf "icn_code_of_ethics_nurses_2021.pdf" \
  "https://www.icn.ch/sites/default/files/2023-06/ICN_Code-of-Ethics_EN_Web.pdf"

# 9. World Medical Association International Code of Medical Ethics (2022 revision)
download_pdf "wma_international_code_medical_ethics_2022.pdf" \
  "https://www.med.or.jp/dl-med/wma/medical_ethics2022e.pdf"

# 10. World Medical Association Declaration of Helsinki (2013 revision)
download_pdf "wma_declaration_of_helsinki_2013.pdf" \
  "https://www.wma.net/wp-content/uploads/2016/11/DoH-Oct2013-JAMA.pdf"

# 11. National Code of Conduct for Nurses and Enrolled Nurse Standards (Allowah policy summarising NMBA code)
download_pdf "allowah_nursing_practice_standards_code_of_conduct_policy.pdf" \
  "https://www.allowah.org.au/wp-content/uploads/2023/06/Nursing-Practice-Standards-and-Code-of-Conduct-Policy-13-March-2023.pdf"

# Remove any zero-byte residuals (if wget created placeholders)
find . -maxdepth 1 -name "*.pdf" -size 0 -print -delete | while read -r file; do
  echo "[download] Removed zero-byte file: $file" >&2
done

if [ "${#FAILURES[@]}" -gt 0 ]; then
  echo ""
  echo "[download] Completed with ${#FAILURES[@]} issues:"
  for f in "${FAILURES[@]}"; do
    echo "  - $f"
  done
  echo ""
else
  echo "[download] All documents downloaded successfully."
fi

# Provide completion message
printf '\nDownload completed. Files saved in %s\n' "$(pwd)"
