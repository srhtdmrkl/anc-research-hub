import pdfplumber
import os
import re
import csv
import glob
from imputation_utils import ProbabilisticImputer

def parse_pdf_text(pdf_path, imputer=None):
    dosars = []
    print(f"Processing {pdf_path}...")
    
    # We want to match lines that look like:
    # 34/RD/2023 03.01.2023 142/P/2025 (Solution only)
    # 34/RD/2023 03.01.2023 10.03.2027 (Termen only)
    # 34/RD/2023 03.01.2023 10.03.2027 142/P/2025 (Termen and Solution)
    # We'll extract the first two parts and the remainder, then split the remainder.
    line_pattern = re.compile(r'^(\d+/[a-zA-Z]+/\d{4})\s+(\d{2}\.\d{2}\.\d{4})\s+(.+)$')
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text:
                    continue
                
                lines = text.split('\n')
                for line in lines:
                    match = line_pattern.match(line.strip())
                    if match:
                        nr_dosar = match.group(1).strip()
                        data_inreg = match.group(2).strip()
                        remainder = match.group(3).strip()
                        
                        termen = ''
                        solutie = ''
                        
                        # A remainder could be:
                        # "142/P/2025" -> Just Solution
                        # "10.03.2027" -> Just Termen
                        # "10.03.2027 142/P/ 25.04.2023" -> Termen + multi-part Solution
                        # "142/P/ 25.04.2023" -> multi-part Solution
                        
                        parts = remainder.split()
                        
                        if len(parts) == 0:
                            continue
                            
                        # If the first part does NOT have a slash, it is a Termen.
                        if '/' not in parts[0]:
                            termen = parts[0]
                            # Everything else that follows is the Solution
                            if len(parts) > 1:
                                solutie = ' '.join(parts[1:])
                        else:
                            # The first part HAS a slash, meaning there is no Termen. 
                            # The entire remainder is the Solution string.
                            solutie = ' '.join(parts)
                            
                        # Extract the exact date from the Solutie string (e.g. "975/P/29.07.2016" -> "29.07.2016")
                        if solutie:
                            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', solutie)
                            if date_match:
                                solutie = date_match.group(1)
                            else:
                                    if imputer:
                                        solutie = imputer.get_random_date(year_match.group(1), nr_dosar)
                                    else:
                                        solutie = f"01.07.{year_match.group(1)}"
                                    
                        # Also protect Termen dates just in case they are year-only
                        if termen:
                            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', termen)
                            if date_match:
                                termen = date_match.group(1)
                            else:
                                    if imputer:
                                        termen = imputer.get_random_date(year_match.group(1), nr_dosar)
                                    else:
                                        termen = f"01.07.{year_match.group(1)}"

                        dosars.append({
                            'NR. DOSAR': nr_dosar,
                            'DATA ÎNREGISTRĂRII': data_inreg,
                            'TERMEN': termen,
                            'SOLUȚIE': solutie
                        })
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
        
    return dosars

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '../../'))
    art10_dir = os.path.join(project_root, 'data', 'raw', 'article_10')
    output_csv = os.path.join(project_root, 'data', 'processed', 'dosare_art10.csv')
    
    all_dosars = []
    
    dist_csv = os.path.join(project_root, 'data', 'processed', 'dist_art10.csv')
    imputer = ProbabilisticImputer(dist_csv)
    
    if os.path.exists(art10_dir):
        for pdf_file in glob.glob(os.path.join(art10_dir, '*.pdf')):
            dosars = parse_pdf_text(pdf_file, imputer)
            all_dosars.extend(dosars)
            print(f"  Extracted {len(dosars)} dossiers from {os.path.basename(pdf_file)}")
            
        if all_dosars:
            keys = all_dosars[0].keys()
            with open(output_csv, 'w', newline='', encoding='utf-8') as output_file:
                dict_writer = csv.DictWriter(output_file, keys)
                dict_writer.writeheader()
                dict_writer.writerows(all_dosars)
            print(f"\nSuccessfully wrote {len(all_dosars):,} dossiers to {output_csv}")
        else:
            print("No dossiers extracted.")
    else:
        print(f"Directory not found: {art10_dir}")

if __name__ == "__main__":
    main()
