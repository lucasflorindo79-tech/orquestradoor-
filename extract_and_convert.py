# extract_and_convert.py
import zipfile
import os
from dbfread import DBF
import pandas as pd

DOWNLOAD_DIR = "./downloads"
OUT_DIR = "./output"
os.makedirs(OUT_DIR, exist_ok=True)

# procura zips
for fname in os.listdir(DOWNLOAD_DIR):
    if fname.lower().endswith(".zip"):
        zip_path = os.path.join(DOWNLOAD_DIR, fname)
        print("Extraindo:", zip_path)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(DOWNLOAD_DIR)

# procura DBF e converte
for root, _, files in os.walk(DOWNLOAD_DIR):
    for f in files:
        if f.lower().endswith(".dbf"):
            dbf_path = os.path.join(root, f)
            print("Convertendo DBF:", dbf_path)
            table = DBF(dbf_path, encoding="latin1")
            df = pd.DataFrame(iter(table))
            out_name = os.path.splitext(f)[0] + ".xlsx"
            out_path = os.path.join(OUT_DIR, out_name)
            df.to_excel(out_path, index=False)
            print("Salvo Excel:", out_path)
